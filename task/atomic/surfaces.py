"""Live mesh geometry anchored to physics poses, including Fabric simulations."""
import numpy as np
from task.atomic.geometry import _rotation


class ObjectSurfaces:
    def __init__(self, env):
        self.env = env
        self.cache = {}

    def resolve(self, label, env_idx, pose):
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
        key = (env_idx, label)
        if key not in self.cache:
            self.resolve(label, env_idx, pose)
        points = self.cache[key][0]
        center = _rotation(pose[3:]) @ ((points.min(axis=0) + points.max(axis=0)) / 2) + pose[:3]
        return np.concatenate((center, pose[3:]))
