"""Reviewed rigid frame alternatives selected by actual asset identity."""
import hashlib
from pathlib import Path

import numpy as np


def resolve_model_frame(env, selector, env_idx, root_pose):
    lm = env.scene_manager.layout_manager
    label = selector['label']
    metadata = lm.get_instance_metadata(env_idx=env_idx, label=label)
    model = f"{metadata.get('model_name')}/{int(metadata.get('model_id', -1)):05d}"
    row = selector['models'].get(model)
    if row is None:
        raise RuntimeError('no reviewed rigid frame for actual asset model ' + model)
    name = lm.get_instance_name(env_idx=env_idx, label=label)
    if str(lm.instance_type_by_env[env_idx].get(name)).lower() not in ('rigid', 'geometry'):
        raise RuntimeError('model frame requires a rigid/static asset')
    obj = lm.get_scene_object(env_idx=env_idx, inst_name=name)
    path = getattr(obj, 'usd_path', None)
    if not path:
        raise RuntimeError('model frame cannot verify the actual asset file')
    asset = Path(path)
    stat = asset.stat()
    identity = (str(asset), stat.st_size, stat.st_mtime_ns)
    if getattr(obj, '_atomic_model_frame_file', None) != identity:
        obj._atomic_model_frame_sha256 = hashlib.sha256(asset.read_bytes()).hexdigest()
        obj._atomic_model_frame_file = identity
    if obj._atomic_model_frame_sha256 != row['asset_sha256']:
        raise RuntimeError('rigid frame asset file differs from reviewed calibration')
    bounds = env._atomic_surfaces.local_mesh_summary(label, env_idx, root_pose)['bounds']
    if not np.allclose(bounds, row['scaled_bounds_m'], atol=1e-7, rtol=0):
        raise RuntimeError('rigid frame scaled material bounds differ from reviewed calibration')
    model_name, model_id = model.rsplit('/', 1)
    selected = {'kind': 'calibrated_frame', 'label': label,
                'local_pose': row['local_pose'], 'calibration_id': row['calibration_id'],
                'asset_model': {'name': model_name, 'index': int(model_id)}}
    return selected, {'model': model, 'asset_sha256': row['asset_sha256'],
                      'scaled_bounds_m': bounds,
                      'selection_semantics': 'actual model/file/scale, not nearest live geometry'}
