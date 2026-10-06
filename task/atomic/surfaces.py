"""Live mesh geometry anchored to physics poses, including Fabric simulations."""
import numpy as np
from task.atomic.geometry import _rotation


def _reject_shear(matrix):
    linear=np.asarray(matrix,dtype=float)[:3,:3]
    gram=linear@linear.T
    if not np.isfinite(gram).all() or np.any(np.diag(gram)<=0) or not np.allclose(gram,np.diag(np.diag(gram)),rtol=1e-7,atol=1e-9*max(float(np.max(np.diag(gram))),1e-12)):
        raise RuntimeError('sheared or degenerate body transforms cannot use rotation-plus-scale surface templates')


def _transformed_points(mesh,relative,scale):
    """Vectorized USD row transform, checked against actual Gf witnesses."""
    from pxr import Gf
    raw=mesh.GetPointsAttr().Get()
    if raw is None or not len(raw):return None
    values=np.asarray(raw,dtype=float);matrix=np.asarray(relative,dtype=float)
    if values.ndim!=2 or values.shape[1]!=3 or matrix.shape!=(4,4) or not np.isfinite(matrix).all() or not np.allclose(matrix[:,3],[0,0,0,1]):
        raise RuntimeError('actual material points need a finite affine USD row transform')
    points=(values@matrix[:3,:3]+matrix[3,:3])*scale
    for i in sorted(set([0,len(values)//2,len(values)-1])):
        expected=np.asarray(relative.Transform(Gf.Vec3d(*map(float,values[i]))))*scale
        if not np.allclose(points[i],expected,atol=1e-10,rtol=1e-12):
            raise RuntimeError('vectorized USD material transform disagrees with actual Gf witnesses')
    if not np.isfinite(points).all():raise RuntimeError('nonfinite actual material points')
    return points


def _triangle_faces(mesh,base):
    counts=np.asarray(mesh.GetFaceVertexCountsAttr().Get(),dtype=np.int64)
    indices=np.asarray(mesh.GetFaceVertexIndicesAttr().Get(),dtype=np.int64)
    if counts.ndim!=1 or indices.ndim!=1 or counts.sum()!=len(indices) or (counts<0).any():
        raise RuntimeError('invalid authored material face counts')
    if (counts==3).all():return (indices.reshape(-1,3)+base).tolist()
    faces=[];offset=0
    for count in counts:
        face=indices[offset:offset+count];offset+=count
        faces.extend([[base+int(face[0]),base+int(face[j]),base+int(face[j+1])] for j in range(1,count-1)])
    return faces


class ObjectSurfaces:
    def __init__(self, env):
        self.env = env
        self.cache = {}
        self.centers = {}
        self.bounds = {}

    def resolve(self, label, env_idx, pose, mesh_paths=None):
        lm=self.env.scene_manager.layout_manager
        if hasattr(lm,'instance_type_by_env'):
            category=lm.instance_type_by_env[env_idx].get(lm.get_instance_name(env_idx,label))
            if category in ('garment','fluid'):
                raise RuntimeError('deforming material cannot use a cached rigid mesh footprint; use material selectors')
            if category=='articulation':
                if mesh_paths:raise RuntimeError('selected root-relative material meshes require a rigid object')
                return self._articulated(label,env_idx,pose)
        key = (env_idx, label) if mesh_paths is None else (env_idx,label,tuple(mesh_paths))
        if key not in self.cache:
            import omni.usd
            from pxr import Gf, Usd, UsdGeom
            lm = self.env.scene_manager.layout_manager
            obj = lm.get_scene_object(env_idx, lm.get_instance_name(env_idx, label))
            path = getattr(obj, 'usd_prim_path', None) or getattr(obj, 'prim_path', None)
            stage = omni.usd.get_context().get_stage()
            root = stage.GetPrimAtPath(path)
            xforms = UsdGeom.XformCache()
            _reject_shear(xforms.GetLocalToWorldTransform(root))
            scale = np.asarray(Gf.Transform(xforms.GetLocalToWorldTransform(root)).GetScale(), dtype=float)
            points, triangles, selected = [], [], []
            for prim in Usd.PrimRange(root, Usd.TraverseInstanceProxies()):
                if not prim.IsA(UsdGeom.Mesh):
                    continue
                relative_path=str(prim.GetPath())[len(str(root.GetPath()))+1:]
                if mesh_paths is not None and relative_path not in mesh_paths:continue
                selected.append(relative_path)
                mesh = UsdGeom.Mesh(prim)
                relative, _ = xforms.ComputeRelativeTransform(prim, root)
                values = _transformed_points(mesh,relative,scale)
                if values is None:continue
                base = len(points);points.extend(values.tolist())
                triangles.extend(_triangle_faces(mesh,base))
            if mesh_paths is not None and set(selected)!=set(mesh_paths):
                raise RuntimeError(f'calibrated material mesh missing from {label}: {set(mesh_paths)-set(selected)}')
            if not triangles:
                raise RuntimeError(f'no mesh surface available for footprint of {label}')
            self.cache[key] = (np.asarray(points), triangles, path)
            if mesh_paths is None:
                self.centers[key]=(self.cache[key][0].min(axis=0)+self.cache[key][0].max(axis=0))/2
                self.bounds[key]={'bounds':[self.cache[key][0].min(axis=0).tolist(),self.cache[key][0].max(axis=0).tolist()],
                    'triangles':len(triangles),'geometry_representation':'actual scaled root-relative USD mesh vertices'}
        points, triangles, path = self.cache[key]
        vertices = points @ _rotation(pose[3:]).T + pose[:3]
        center = ((points.min(axis=0) + points.max(axis=0)) / 2) @ _rotation(pose[3:]).T + pose[:3]
        return {'position': center.tolist(), 'orientation': pose[3:].tolist(),
                'vertices': vertices.tolist(), 'triangles': triangles,
                'geometry_representation': ('calibrated material mesh triangles' if mesh_paths else 'union of projected USD mesh triangles'),
                'selected_mesh_paths':mesh_paths, 'prim_path': path}

    def center_pose(self, label, env_idx, pose):
        lm=self.env.scene_manager.layout_manager
        if hasattr(lm,'instance_type_by_env') and lm.instance_type_by_env[env_idx].get(lm.get_instance_name(env_idx,label)) in ('garment','fluid'):
            raise RuntimeError('deforming material cannot use cached rigid mesh centers')
        key = (env_idx, label)
        if key in self.cache:
            if isinstance(self.cache[key],dict):
                surface=self._articulated(label,env_idx,pose)
                return np.concatenate((surface['position'],pose[3:]))
            if key not in self.centers:
                points=self.cache[key][0];self.centers[key]=(points.min(axis=0)+points.max(axis=0))/2
            center=self.centers[key]
        elif hasattr(lm,'instance_type_by_env') and lm.instance_type_by_env[env_idx].get(lm.get_instance_name(env_idx,label))=='articulation':
            surface=self._articulated(label,env_idx,pose)
            return np.concatenate((surface['position'],pose[3:]))
        else:
            if key not in self.centers:
                import omni.usd
                from pxr import Gf,Usd,UsdGeom
                obj=lm.get_scene_object(env_idx,lm.get_instance_name(env_idx,label))
                path=getattr(obj,'usd_prim_path',None) or getattr(obj,'prim_path',None)
                root=omni.usd.get_context().get_stage().GetPrimAtPath(path);xforms=UsdGeom.XformCache()
                transform=xforms.GetLocalToWorldTransform(root);_reject_shear(transform)
                scale=np.asarray(Gf.Transform(transform).GetScale(),dtype=float)
                low=np.full(3,np.inf);high=np.full(3,-np.inf);face_count=0
                for prim in Usd.PrimRange(root,Usd.TraverseInstanceProxies()):
                    if not prim.IsA(UsdGeom.Mesh):continue
                    mesh=UsdGeom.Mesh(prim);relative,_=xforms.ComputeRelativeTransform(prim,root)
                    points=_transformed_points(mesh,relative,scale)
                    if points is None:continue
                    low=np.minimum(low,points.min(axis=0));high=np.maximum(high,points.max(axis=0))
                    face_count+=sum(max(int(count)-2,0) for count in mesh.GetFaceVertexCountsAttr().Get())
                if not face_count or not np.isfinite([low,high]).all():raise RuntimeError('no actual material mesh for object centre')
                self.centers[key]=(low+high)/2
                self.bounds[key]={'bounds':[low.tolist(),high.tolist()],'triangles':face_count,
                    'geometry_representation':'actual scaled root-relative USD mesh vertices'}
            center=self.centers[key]
        return np.concatenate((_rotation(pose[3:])@center+pose[:3],pose[3:]))

    def local_mesh_summary(self,label,env_idx,pose):
        """Actual rigid bounds/count, without a world-vertex JSON export."""
        self.center_pose(label,env_idx,pose);key=(env_idx,label)
        if key not in self.bounds:
            template=self.cache.get(key)
            if not isinstance(template,tuple):raise RuntimeError('local material summary requires a rigid mesh')
            points,triangles,_=template
            self.bounds[key]={'bounds':[points.min(axis=0).tolist(),points.max(axis=0).tolist()],
                'triangles':len(triangles),'geometry_representation':'actual scaled root-relative USD mesh vertices'}
        return dict(self.bounds[key])

    def resolve_link(self,label,link,env_idx):
        from task.atomic.landmarks import live_link_pose
        pose,_=live_link_pose(self.env,label,link,env_idx)
        return self._articulated(label,env_idx,pose,only_link=link)

    def _load_articulated(self,label,env_idx):
        import omni.usd
        from pxr import Gf,Usd,UsdGeom,UsdPhysics
        lm=self.env.scene_manager.layout_manager
        obj=lm.get_scene_object(env_idx,lm.get_instance_name(env_idx,label))
        path=getattr(obj,'usd_prim_path',None) or getattr(obj,'prim_path',None)
        root=omni.usd.get_context().get_stage().GetPrimAtPath(path)
        xforms=UsdGeom.XformCache();parts=[]
        for prim in Usd.PrimRange(root,Usd.TraverseInstanceProxies()):
            if not prim.IsA(UsdGeom.Mesh):continue
            mesh=UsdGeom.Mesh(prim);values=mesh.GetPointsAttr().Get()
            if values is None or not len(values):continue
            body=prim
            while body and body.GetPath()!=root.GetPath() and not body.HasAPI(UsdPhysics.RigidBodyAPI):
                body=body.GetParent()
            if not body or not body.HasAPI(UsdPhysics.RigidBodyAPI):
                raise RuntimeError(f'{label} mesh {prim.GetPath()} lacks an explicit rigid link; no root-frame fallback')
            relative,_=xforms.ComputeRelativeTransform(prim,body)
            _reject_shear(xforms.GetLocalToWorldTransform(body))
            scale=np.asarray(Gf.Transform(xforms.GetLocalToWorldTransform(body)).GetScale(),dtype=float)
            points=np.asarray([np.asarray(relative.Transform(Gf.Vec3d(*map(float,p))))*scale for p in values])
            triangles=[];indices=list(mesh.GetFaceVertexIndicesAttr().Get());offset=0
            for count in mesh.GetFaceVertexCountsAttr().Get():
                face=indices[offset:offset+count]
                triangles.extend([[face[0],face[j],face[j+1]] for j in range(1,count-1)])
                offset+=count
            if triangles:
                parts.append({'link':body.GetName(),'prim_path':str(body.GetPath()),'points':points,'triangles':triangles})
        if not parts:raise RuntimeError(f'no rigid-link mesh geometry for {label}')
        return {'parts':parts,'prim_path':path}

    def _articulated(self,label,env_idx,pose,only_link=None):
        from task.atomic.landmarks import live_link_poses
        key=(env_idx,label)
        if key not in self.cache:self.cache[key]=self._load_articulated(label,env_idx)
        template=self.cache[key]
        if not isinstance(template,dict):raise RuntimeError('geometry category changed without resetting surface templates')
        parts=[p for p in template['parts'] if only_link is None or p['link']==only_link]
        if not parts:raise RuntimeError('selected link has no calibrated mesh geometry')
        poses,source=live_link_poses(self.env,label,sorted({p['link'] for p in parts}),env_idx)
        vertices=[];triangles=[];count=0
        for part in parts:
            link_pose=poses[part['link']]
            values=np.asarray(part['points'])@_rotation(link_pose[3:]).T+link_pose[:3]
            vertices.append(values);triangles.extend([[i+count for i in triangle] for triangle in part['triangles']]);count+=len(values)
        vertices=np.concatenate(vertices)
        local=(vertices-pose[:3])@_rotation(pose[3:])
        center=((local.min(axis=0)+local.max(axis=0))/2)@_rotation(pose[3:]).T+pose[:3]
        return {'position':center.tolist(),'orientation':pose[3:].tolist(),'vertices':vertices.tolist(),'triangles':triangles,
                'geometry_representation':'rigid-link mesh triangles transformed by live PhysX child poses',
                'prim_path':parts[0]['prim_path'] if only_link else template['prim_path'],
                'live_link_source':source,'live_link_poses':{link:value.tolist() for link,value in poses.items()}}
