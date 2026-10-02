"""Live mesh geometry anchored to physics poses, including Fabric simulations."""
import numpy as np
from task.atomic.geometry import _rotation


def _reject_shear(matrix):
    linear=np.asarray(matrix,dtype=float)[:3,:3]
    gram=linear@linear.T
    if not np.isfinite(gram).all() or np.any(np.diag(gram)<=0) or not np.allclose(gram,np.diag(np.diag(gram)),rtol=1e-7,atol=1e-9*max(float(np.max(np.diag(gram))),1e-12)):
        raise RuntimeError('sheared or degenerate body transforms cannot use rotation-plus-scale surface templates')


class ObjectSurfaces:
    def __init__(self, env):
        self.env = env
        self.cache = {}

    def resolve(self, label, env_idx, pose):
        lm=self.env.scene_manager.layout_manager
        if hasattr(lm,'instance_type_by_env'):
            category=lm.instance_type_by_env[env_idx].get(lm.get_instance_name(env_idx,label))
            if category in ('garment','fluid'):
                raise RuntimeError('deforming material cannot use a cached rigid mesh footprint; use material selectors')
            if category=='articulation':
                return self._articulated(label,env_idx,pose)
        key = (env_idx, label)
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
            points, triangles = [], []
            for prim in Usd.PrimRange(root, Usd.TraverseInstanceProxies()):
                if not prim.IsA(UsdGeom.Mesh):
                    continue
                mesh = UsdGeom.Mesh(prim)
                values = mesh.GetPointsAttr().Get()
                if values is None or not len(values):
                    continue
                relative, _ = xforms.ComputeRelativeTransform(prim, root)
                base = len(points)
                points.extend((np.asarray(relative.Transform(Gf.Vec3d(*map(float, p)))) * scale).tolist() for p in values)
                indices = list(mesh.GetFaceVertexIndicesAttr().Get())
                offset = 0
                for count in mesh.GetFaceVertexCountsAttr().Get():
                    face = indices[offset:offset + count]
                    for j in range(1, count - 1):
                        triangles.append([base + face[0], base + face[j], base + face[j + 1]])
                    offset += count
            if not triangles:
                raise RuntimeError(f'no mesh surface available for footprint of {label}')
            self.cache[key] = (np.asarray(points), triangles, path)
        points, triangles, path = self.cache[key]
        vertices = points @ _rotation(pose[3:]).T + pose[:3]
        center = ((points.min(axis=0) + points.max(axis=0)) / 2) @ _rotation(pose[3:]).T + pose[:3]
        return {'position': center.tolist(), 'orientation': pose[3:].tolist(),
                'vertices': vertices.tolist(), 'triangles': triangles,
                'geometry_representation': 'union of projected USD mesh triangles', 'prim_path': path}

    def center_pose(self, label, env_idx, pose):
        lm=self.env.scene_manager.layout_manager
        if hasattr(lm,'instance_type_by_env') and lm.instance_type_by_env[env_idx].get(lm.get_instance_name(env_idx,label)) in ('garment','fluid'):
            raise RuntimeError('deforming material cannot use cached rigid mesh centers')
        key = (env_idx, label)
        if key not in self.cache:
            self.resolve(label, env_idx, pose)
        if isinstance(self.cache[key],dict):
            surface=self._articulated(label,env_idx,pose)
            return np.concatenate((surface['position'],pose[3:]))
        points = self.cache[key][0]
        center = _rotation(pose[3:]) @ ((points.min(axis=0) + points.max(axis=0)) / 2) + pose[:3]
        return np.concatenate((center, pose[3:]))

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
