"""Articulated link frames read from PhysX tensors, including Fabric scenes."""
import numpy as np


def matrix_quaternion(rotation):
    """Stable scalar-first unit quaternion for a physical 3x3 rotation."""
    # Eigenvector form avoids the zero-trace and pi-rotation branches.
    r = np.asarray(rotation, dtype=float)
    if r.shape != (3,3) or not np.isfinite(r).all():
        raise RuntimeError('invalid live rotation matrix')
    k = np.array([[r[0,0]-r[1,1]-r[2,2],r[0,1]+r[1,0],r[0,2]+r[2,0],r[2,1]-r[1,2]],
                  [r[0,1]+r[1,0],r[1,1]-r[0,0]-r[2,2],r[1,2]+r[2,1],r[0,2]-r[2,0]],
                  [r[0,2]+r[2,0],r[1,2]+r[2,1],r[2,2]-r[0,0]-r[1,1],r[1,0]-r[0,1]],
                  [r[2,1]-r[1,2],r[0,2]-r[2,0],r[1,0]-r[0,1],np.trace(r)]])
    _, vectors = np.linalg.eigh(k)
    return vectors[:, -1][[3,0,1,2]]


def live_link_pose(env, label, link, env_idx):
    poses,source=live_link_poses(env,label,[link],env_idx)
    return poses[link],{**source,'kind':'articulated_link_pose','link':link}


def live_link_poses(env, label, links, env_idx):
    """Read multiple child poses from one synchronized PhysX tensor snapshot."""
    lm = env.scene_manager.layout_manager
    name = lm.get_instance_name(env_idx=env_idx, label=label)
    obj = lm.get_scene_object(env_idx=env_idx, inst_name=name)
    view = getattr(obj, '_articulation_view', None)
    physics = getattr(view, '_physics_view', None)
    names = getattr(view, 'body_names', None)
    if physics is None or names is None or not hasattr(physics, 'get_link_transforms'):
        raise RuntimeError('articulated landmark requires initialized PhysX link transforms; USD xforms are not a live fallback')
    indices={}
    for link in links:
        matches = [i for i, name in enumerate(names) if name == link]
        if len(matches) != 1:
            raise ValueError(f'link {link!r} must resolve uniquely in {label} body_names')
        indices[link]=matches[0]
    values = physics.get_link_transforms()
    if hasattr(values, 'detach'):
        values = values.detach().cpu().numpy()
    values = np.asarray(values, dtype=float)
    if values.ndim != 3 or values.shape != (1,len(names),7):
        raise RuntimeError('expected a single-object PhysX articulation view [1, links, 7]')
    origin = env.sim.scene.env_origins[env_idx]
    if hasattr(origin, 'detach'):
        origin = origin.detach().cpu().numpy()
    poses={}
    for link,index in indices.items():
        row=values[0,index]
        pose = np.concatenate((row[:3] - np.asarray(origin), row[[6,3,4,5]]))
        if not np.isfinite(pose).all() or np.linalg.norm(pose[3:]) == 0:
            raise RuntimeError('invalid live PhysX articulated link pose')
        poses[link]=pose
    return poses, {'kind':'articulated_link_poses', 'label':label, 'links':list(links),
                  'backend':'PhysX articulation link transforms', 'quaternion_conversion':'xyzw to wxyz',
                  'frame':'environment_local_world'}
