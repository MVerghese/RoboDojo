"""Live material coordinates with explicit identities and backend/frame contracts."""
import numpy as np

from task.atomic.landmarks import matrix_quaternion


def _array(value):
    if hasattr(value,'detach'):value=value.detach().cpu().numpy()
    return np.asarray(value)


def material_state(env,label,kind,env_idx):
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
    return {'ids':ids.astype(np.int64),'positions':positions,'nominal_mass_kg':mass,
            'source':{'label':label,'kind':kind,'backend':raw['backend'],'identity':raw['identity'],
                      'frame':'environment_local_world','mass_semantics':'configured nominal particle mass, not measured density' if kind=='fluid' else None}}


def resolve_material(env,selector,env_idx):
    kind='fluid' if selector['kind']=='fluid_points' else 'cloth'
    state=material_state(env,selector['label'],kind,env_idx)
    if selector['kind']=='cloth_landmark':
        lm=env.scene_manager.layout_manager
        metadata=lm.get_instance_metadata(env_idx=env_idx,label=selector['label'])
        ids=metadata.get('passive',{}).get('functional',{}).get(selector['tag'],{}).get('id')
        if not isinstance(ids,list) or not ids or any(type(i) is not int or i<0 for i in ids) or len(set(ids))!=len(ids):
            raise ValueError('cloth tag must annotate distinct explicit material vertex IDs')
    elif selector['kind']=='cloth_patch_frame':
        ids=[selector[k] for k in ('origin_id','x_id','y_id')]
    else:ids=selector['ids']
    lookup={int(ident):i for i,ident in enumerate(state['ids'])}
    if set(ids)-lookup.keys():raise ValueError('requested material IDs are missing from live state')
    points=state['positions'][[lookup[i] for i in ids]]
    source={**state['source'],**selector,'material_kind':kind,'material_ids':list(ids)}
    if selector['kind']=='cloth_patch_frame':
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
