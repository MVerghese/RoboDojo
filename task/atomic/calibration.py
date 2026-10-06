"""Read-only live asset evidence for selecting and reviewing geometric bindings."""
from collections.abc import Mapping
import numpy as np


def primitive(value):
    if hasattr(value, 'detach'):
        value = value.detach().cpu().numpy()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Mapping):
        return {str(k): primitive(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [primitive(v) for v in value]
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    return str(value)


def snapshot_scene(session):
    """Export initial live frames, material IDs and asset annotations, not targets.

    This diagnostic does not establish contact, cavity geometry, or action
    recognition. Errors are retained per asset; they never become measurements.
    """
    env, idx = session.env, session.env_idx
    lm = env.scene_manager.layout_manager
    if not hasattr(lm, 'get_labels_by_prefix'):
        return {'status': 'unavailable', 'reason': 'layout inventory unavailable', 'objects': {}}
    labels = sorted(lm.get_labels_by_prefix(env_idx=idx, prefix=''))
    objects = {}
    for label in labels:
        row = {'label': label, 'errors': [], 'landmarks': {}}
        objects[label] = row
        try:
            name = lm.get_instance_name(env_idx=idx, label=label)
            category = lm.instance_type_by_env[idx][name]
            metadata = lm.get_instance_metadata(env_idx=idx, label=label)
            row.update(instance=name, category=category, metadata=primitive(metadata))
            if category in ('garment', 'fluid'):
                from task.atomic.materials import material_state
                state = material_state(env, label, 'cloth' if category == 'garment' else 'fluid', idx)
                row['material'] = {'ids': state['ids'].tolist(),
                                   'initial_positions': state['positions'].tolist(),
                                   'triangles': state.get('triangles'),
                                   'source': state['source'], 'nominal_mass_kg': state['nominal_mass_kg']}
                obj = lm.get_scene_object(env_idx=idx, inst_name=name)
                view = getattr(obj, '_cloth_prim_view', None)
                row['backend_contact_methods'] = [key for key in dir(view) if 'contact' in key or 'force' in key]
            else:
                pose = session._object_pose(label)
                row['initial_root_pose'] = pose.tolist()
                if getattr(env, '_atomic_surfaces', None) is not None:
                    surface = env._atomic_surfaces.resolve(label, idx, pose)
                    vertices = np.asarray(surface['vertices'])
                    from task.atomic.geometry import _rotation
                    local = (vertices - pose[:3]) @ _rotation(pose[3:])
                    row['local_mesh_bounds_m'] = [local.min(axis=0).tolist(), local.max(axis=0).tolist()]
                    row['surface_representation'] = surface['geometry_representation']
                    if label != 'camera_stand' and len(surface['triangles']) <= 100000:
                        row['local_mesh'] = {'vertices': local.tolist(), 'triangles': surface['triangles'],
                                             'frame': 'object_root',
                                             'interpretation': 'actual outer/material surface; not an interior annotation'}
                for role in ('active', 'passive'):
                    for category_name, kind in (('functional', 'functional_point'), ('support', 'support_point')):
                        for tag, item in metadata.get(role, {}).get(category_name, {}).items():
                            count = len(item.get('frame' if kind == 'functional_point' else 'center', []))
                            for index in range(count):
                                selector = {'kind': kind, 'label': label, 'tag': tag, 'type': role, 'index': index}
                                try:
                                    value, source = session._resolve_with_source(selector)
                                    row['landmarks'][f'{role}/{category_name}/{tag}/{index}'] = {
                                        'selector': selector, 'pose': primitive(value), 'source': primitive(source)}
                                except Exception as error:
                                    row['errors'].append(f'{tag}/{index}: {type(error).__name__}: {error}')
        except Exception as error:
            row['errors'].append(f'{type(error).__name__}: {error}')
    return {'status': 'captured', 'physics_step': getattr(getattr(env, '_atomic_contacts', None), 'steps', None),
            'coordinate_frame': 'environment_local_world', 'quaternion_order': 'wxyz',
            'objects': objects, 'interpretation': 'asset/frame evidence; cavity and contact calibration remain separate'}
