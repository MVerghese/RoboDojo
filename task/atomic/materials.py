"""Live material coordinates with explicit identities and backend/frame contracts."""
import numpy as np
import hashlib

from task.atomic.landmarks import matrix_quaternion


def _array(value):
    if hasattr(value,'detach'):value=value.detach().cpu().numpy()
    return np.asarray(value)


def material_state(env,label,kind,env_idx):
    # Production cache is invalidated before every PhysX step and episode reset.
    # It never substitutes constructor geometry for a live solver readback.
    cache=getattr(getattr(env,'_atomic_contacts',None),'material_states',None)
    key=(env_idx,label,kind)
    if cache is not None and key in cache:return cache[key]
    lm=env.scene_manager.layout_manager
    name=lm.get_instance_name(env_idx=env_idx,label=label)
    if name is None:raise ValueError('unknown material label '+label)
    category=lm.instance_type_by_env[env_idx].get(name)
    expected='garment' if kind=='cloth' else 'fluid'
    if category!=expected:raise ValueError(f'{label} must be {expected}, not {category}')
    obj=lm.get_scene_object(env_idx=env_idx,inst_name=name)
    method='get_atomic_vertex_state' if kind=='cloth' else 'get_atomic_particle_state'
    if not hasattr(obj,method):raise RuntimeError(f'{label} has no live atomic {kind} backend')
    raw=getattr(obj,method)()
    if raw.get('requires_fabric_disabled') and getattr(env, 'use_fabric', None) is not False:
        raise RuntimeError('CPU cloth USD readback requires explicit use_fabric=False; stale USD coordinates are forbidden')
    ids=_array(raw['ids'])
    if ids.ndim!=1 or ids.dtype.kind not in 'iu' or len(set(ids.tolist()))!=len(ids) or np.any(ids<0):
        raise RuntimeError('material IDs must be unique persistent nonnegative integers')
    origin=_array(env.sim.scene.env_origins[env_idx]).astype(float)
    if origin.shape!=(3,) or not np.isfinite(origin).all():raise RuntimeError('invalid material environment origin')
    if kind=='cloth':
        positions=_array(raw['positions_world']).astype(float)-origin
        mass=None
    else:
        local=_array(raw['positions_local']).astype(float)
        transform=_array(raw['local_to_world_row_matrix']).astype(float)
        if transform.shape!=(4,4) or not np.isfinite(transform).all() or not np.allclose(transform[:,3],[0,0,0,1]):
            raise RuntimeError('fluid requires an affine USD row-vector local-to-world matrix')
        if local.ndim!=2 or local.shape[1]!=3:raise RuntimeError('fluid coordinates must be Nx3')
        # USD matrices transform row vectors; include authored scale, rotation
        # and translation exactly once, then remove the environment origin.
        positions=(np.column_stack((local,np.ones(len(local))))@transform)[:,:3]-origin
        if isinstance(raw['nominal_particle_mass_kg'],bool):raise RuntimeError('fluid nominal mass cannot be boolean')
        mass=float(raw['nominal_particle_mass_kg'])
        if not np.isfinite(mass) or mass<=0:raise RuntimeError('fluid nominal particle mass must be finite and positive')
    if positions.shape!=(len(ids),3) or not len(ids) or not np.isfinite(positions).all():
        raise RuntimeError('material positions must be finite nonempty Nx3 and match persistent IDs')
    result={'ids':ids.astype(np.int64),'positions':positions,'nominal_mass_kg':mass,
            'triangles': raw.get('triangles'),
            'source':{'label':label,'kind':kind,'backend':raw['backend'],'identity':raw['identity'],
                      'frame':'environment_local_world','mass_semantics':'configured nominal particle mass, not measured density' if kind=='fluid' else None}}
    if kind=='cloth' and raw.get('triangles') is not None:
        result['topology_sha256']=hashlib.sha256(np.asarray(raw['triangles'],dtype='<i8').tobytes()).hexdigest()
    if cache is not None:cache[key]=result
    return result


def resolve_material(env,selector,env_idx):
    if selector['kind'] == 'cloth_model_curve':
        selected, proof = resolve_model_curve(env, selector, env_idx)
        value, source = resolve_material(env, selected, env_idx)
        return value, {**source, 'calibrated_model_curve': proof}
    if selector['kind']=='cloth_model_patch':
        selected,proof=resolve_model_patch(env,selector,env_idx)
        value,source=resolve_material(env,selected,env_idx)
        return value,{**source,'calibrated_model_patch':proof}
    if selector['kind']=='cloth_line_frame':
        label=selector['label']
        a,sa=resolve_material(env,{'kind':'cloth_landmark','label':label,'tag':selector['tag_a']},env_idx)
        b,sb=resolve_material(env,{'kind':'cloth_landmark','label':label,'tag':selector['tag_b']},env_idx)
        normal,sn=resolve_material(env,{'kind':'cloth_tag_frame','label':label,'tag':selector['normal_tag']},env_idx)
        a,b=np.asarray(a['position']),np.asarray(b['position']);x=b-a
        if np.linalg.norm(x)<=1e-10:raise RuntimeError('cloth crease endpoints coincide')
        x=x/np.linalg.norm(x)
        from task.atomic.geometry import _rotation
        z=_rotation(normal[3:])[:,2];z=z-x*(z@x)
        if np.linalg.norm(z)<=1e-10:raise RuntimeError('cloth crease normal is parallel to the line')
        z=z/np.linalg.norm(z);y=np.cross(z,x)
        return np.concatenate(((a+b)/2,matrix_quaternion(np.column_stack((x,y,z))))),{
            **selector,'frame':'environment_local_world','crease_length_m':float(np.linalg.norm(b-a)),
            'endpoint_sources':[sa,sb],'endpoints_m':[a.tolist(),b.tolist()],
            'line_representation':'finite chord between persistent material-tag mean endpoints; not a curved crease','normal_source':sn,'material_kind':'cloth'}
    kind='fluid' if selector['kind']=='fluid_points' else 'cloth'
    state=material_state(env,selector['label'],kind,env_idx)
    if selector['kind'] in ('cloth_landmark', 'cloth_tag_frame'):
        lm=env.scene_manager.layout_manager
        metadata=lm.get_instance_metadata(env_idx=env_idx,label=selector['label'])
        ids=metadata.get('passive',{}).get('functional',{}).get(selector['tag'],{}).get('id')
        if not isinstance(ids,list) or not ids or any(type(i) is not int or i<0 for i in ids) or len(set(ids))!=len(ids):
            raise ValueError('cloth tag must annotate distinct explicit material vertex IDs')
        if selector['kind'] == 'cloth_tag_frame':
            triangles = state.get('triangles')
            if triangles is None: raise RuntimeError('a cloth tag frame requires actual material mesh topology')
            triangles = np.asarray(triangles)
            adjacent = [face.tolist() for face in triangles if ids[0] in face]
            if not adjacent: raise ValueError('cloth landmark has no incident material triangle')
            face = adjacent[0]; start = face.index(ids[0]); ids = face[start:]+face[:start]
    elif selector['kind'] in ('cloth_patch_frame','cloth_patch_surface'):
        ids=[selector[k] for k in ('origin_id','x_id','y_id')]
    else:ids=selector['ids']
    lookup={int(ident):i for i,ident in enumerate(state['ids'])}
    if set(ids)-lookup.keys():raise ValueError('requested material IDs are missing from live state')
    points=state['positions'][[lookup[i] for i in ids]]
    source={**state['source'],**selector,'material_kind':kind,'material_ids':list(ids)}
    if selector['kind'] == 'cloth_curve':
        triangles = np.asarray(state.get('triangles'))
        if triangles.ndim != 2 or triangles.shape[1] != 3:
            raise RuntimeError('material curve requires live topology to verify connected edges')
        edges = {tuple(sorted((int(a), int(b)))) for face in triangles
                 for a, b in zip(face, np.roll(face, -1))}
        if any(tuple(sorted((a,b))) not in edges for a,b in zip(ids, ids[1:])):
            raise RuntimeError('curve IDs are not an ordered connected material-edge path')
        from task.atomic.curves import curve_points
        curve_points(points)
        return {'polyline_m': points.tolist()}, {
            **source, 'representation': 'ordered persistent mesh-edge material path; not a detected crease'}
    if selector['kind'] in ('cloth_patch_frame', 'cloth_tag_frame','cloth_patch_surface'):
        x,y=points[1]-points[0],points[2]-points[0]
        if np.linalg.norm(x)<=1e-10 or np.linalg.norm(y)<=1e-10:
            raise RuntimeError('cloth tangent frame is degenerate')
        x=x/np.linalg.norm(x);z=np.cross(x,y)
        if np.linalg.norm(z)<=1e-10*np.linalg.norm(y):raise RuntimeError('cloth tangent frame is collinear')
        z=z/np.linalg.norm(z);y=np.cross(z,x)
        return np.concatenate((points[0],matrix_quaternion(np.column_stack((x,y,z))))),source
    measured={'position':points.mean(axis=0).tolist(),'points':points.tolist(),'point_kind':kind}
    if kind=='fluid':source['selected_nominal_mass_kg']=len(points)*state['nominal_mass_kg']
    return measured,source


def resolve_patch_surface(env,selector,env_idx):
    """Explicit topology faces follow persistent material IDs through deformation."""
    if selector['kind']=='cloth_model_patch':
        selected,proof=resolve_model_patch(env,selector,env_idx)
        surface=resolve_patch_surface(env,selected,env_idx)
        return {**surface,'calibrated_model_patch':proof}
    state=material_state(env,selector['label'],'cloth',env_idx)
    faces=np.asarray(state.get('triangles'))
    requested=np.asarray(selector['face_ids'])
    if faces.ndim!=2 or faces.shape[1]!=3 or faces.dtype.kind not in 'iu' or requested.max()>=len(faces):
        raise RuntimeError('material patch requires the explicitly selected live topology faces')
    selected=faces[requested];ids=np.unique(selected)
    lookup={int(ident):i for i,ident in enumerate(state['ids'])}
    if set(ids.tolist())-lookup.keys():raise RuntimeError('material patch topology references missing persistent vertex IDs')
    remap={int(ident):i for i,ident in enumerate(ids)}
    points=state['positions'][[lookup[int(i)] for i in ids]]
    pose,source=resolve_material(env,selector,env_idx)
    return {'position':pose[:3].tolist(),'orientation':pose[3:].tolist(),
        'vertices':points.tolist(),'triangles':[[remap[int(i)] for i in face] for face in selected],
        'geometry_representation':'explicit persistent material topology faces transformed by live solver vertices',
        'material_vertex_ids':ids.tolist(),'material_face_ids':requested.tolist(),'material_source':source}


def resolve_model_patch(env,selector,env_idx):
    """Choose immutable faces from the actual asset model, never live proximity."""
    row, model = _verified_material_model(env, selector, env_idx)
    selected={'kind':'cloth_patch_surface','label':selector['label'],**{k:row[k] for k in ('face_ids','origin_id','x_id','y_id')}}
    return selected,{'model':model,'asset_sha256':row['asset_sha256'],'topology_sha256':row['topology_sha256'],
                    'selection_semantics':'explicit pre-policy model-bound material faces; not nearest live vertices'}


def resolve_model_curve(env, selector, env_idx):
    row, model = _verified_material_model(env, selector, env_idx)
    return {'kind': 'cloth_curve', 'label': selector['label'], 'ids': row['ids']}, {
        'model': model, 'asset_sha256': row['asset_sha256'], 'topology_sha256': row['topology_sha256'],
        'selection_semantics': 'explicit pre-policy model-bound ordered material edges; not live nearest vertices'}


def _verified_material_model(env, selector, env_idx):
    from pathlib import Path
    lm=env.scene_manager.layout_manager;label=selector['label']
    metadata=lm.get_instance_metadata(env_idx=env_idx,label=label)
    model=f"{metadata.get('model_name')}/{int(metadata.get('model_id',-1)):05d}"
    row=selector['models'].get(model)
    if row is None:raise RuntimeError('no calibrated cloth material region for actual asset model '+model)
    state=material_state(env,label,'cloth',env_idx)
    if state.get('topology_sha256')!=row['topology_sha256']:
        raise RuntimeError('live cloth topology differs from the calibrated persistent face IDs')
    obj=lm.get_scene_object(env_idx=env_idx,inst_name=lm.get_instance_name(env_idx=env_idx,label=label))
    path=getattr(obj,'usd_path',None)
    if not path:raise RuntimeError('calibrated cloth patch cannot verify the actual asset file')
    asset=Path(path);stat=asset.stat();identity=(str(asset),stat.st_size,stat.st_mtime_ns)
    if getattr(obj,'_atomic_verified_asset_file',None)!=identity:
        obj._atomic_verified_asset_sha256=hashlib.sha256(asset.read_bytes()).hexdigest()
        obj._atomic_verified_asset_file=identity
    if obj._atomic_verified_asset_sha256!=row['asset_sha256']:
        raise RuntimeError('live cloth asset file differs from the reviewed patch calibration')
    return row, model
