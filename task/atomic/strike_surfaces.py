"""Actual selected USD triangle regions for force-bearing tool contacts."""
from copy import deepcopy
import math
import numpy as np
from task.atomic.geometry import _rotation
from task.atomic.surface_distance import point_surface_distances


SOURCE='ObjectSurfaces.resolve selected scaled USD triangles anchored to actual task root'
SCOPE='selected live USD surface region; not cooked-collider part identity, exclusive impact, sound or timing'


def validate_definition(profile,config):
    if (set(profile)!={'kind','label','surface_tag','mesh_paths','models','distance_tolerance_m','require_contact'}
            or profile['kind']!='model_mesh_region' or profile['label']!=config['target_label']
            or config['target_point'].get('kind')!='functional_point'
            or profile['surface_tag']!=config['target_point'].get('tag')
            or config['target_point'].get('index',0)!=0 or type(profile['require_contact']) is not bool
            or type(profile['distance_tolerance_m']) not in (float,int)
            or not math.isfinite(profile['distance_tolerance_m']) or profile['distance_tolerance_m']<=0):
        raise ValueError('target surface needs a declared model/tag binding and positive distance tolerance')
    paths=profile['mesh_paths']
    if not isinstance(paths,list) or not paths or len(set(paths))!=len(paths) or any(
        not isinstance(p,str) or not p or p.startswith('/') or '..' in p.split('/') for p in paths):
        raise ValueError('target surface needs distinct root-relative mesh paths')
    if not isinstance(profile['models'],dict) or not profile['models']:raise ValueError('surface model bindings required')
    for model,row in profile['models'].items():
        if not {'asset_sha256','scaled_bounds_m','local_pose','calibration_id','triangle_indices','expected_triangles_m','landmark_root_pose'}<=set(row):
            raise ValueError('complete model/file/geometry surface calibration required')
        indices=np.asarray(row['triangle_indices']);triangles=np.asarray(row['expected_triangles_m'],dtype=float)
        bounds=np.asarray(row['scaled_bounds_m'],dtype=float);landmark=np.asarray(row['landmark_root_pose'],dtype=float)
        if (not isinstance(model,str) or not model or len(row['asset_sha256'])!=64
                or indices.ndim!=1 or not len(indices) or indices.dtype.kind not in 'iu'
                or indices.min()<0 or len(set(indices.tolist()))!=len(indices)
                or triangles.shape!=(len(indices),3,3) or not np.isfinite(triangles).all()
                or bounds.shape!=(2,3) or not np.isfinite(bounds).all()
                or landmark.shape!=(7,) or not np.isfinite(landmark).all()):
            raise ValueError('surface definition needs actual finite triangles, landmark and asset bounds')
        pose=np.asarray(row['local_pose'],dtype=float)
        if pose.shape!=(7,) or not np.isfinite(pose).all() or not isinstance(row['calibration_id'],str) or not row['calibration_id']:
            raise ValueError('finite model root pose and calibration identifier required')
        _rotation(landmark[3:]);_rotation(pose[3:])


def capture_surface(session,config):
    profile=config['target_surface'];label=profile['label'];step=session.env._atomic_contacts.steps
    packet={'label':label,'surface_tag':profile['surface_tag'],'environment_index':session.env_idx,
        'physics_step':step,'frame':'scaled_object_root_local','length_unit':'metres','source':SOURCE,'scope':SCOPE}
    try:
        from task.atomic.model_frames import resolve_model_frame
        root=np.asarray(session._object_pose(label));selector={'label':label,'models':profile['models']}
        _,proof=resolve_model_frame(session.env,selector,session.env_idx,root)
        row=profile['models'][proof['model']]
        geometry=session.env._atomic_surfaces.resolve(label,session.env_idx,root,mesh_paths=profile['mesh_paths'])
        local=(np.asarray(geometry['vertices'])-root[:3])@_rotation(root[3:])
        faces=np.asarray(geometry['triangles']);indices=np.asarray(row['triangle_indices'])
        triangles=local[faces[indices]]
        if not np.allclose(triangles,row['expected_triangles_m'],rtol=0,atol=1e-7):
            raise ValueError('selected actual USD triangles differ from reviewed calibration')
        landmark=np.asarray(session._resolve(config['target_point']));expected=np.asarray(row['landmark_root_pose'])
        if (not np.allclose(root[:3]+_rotation(root[3:])@expected[:3],landmark[:3],rtol=0,atol=1e-7)
                or not np.allclose(_rotation(root[3:])@_rotation(expected[3:]),_rotation(landmark[3:]),rtol=0,atol=1e-7)):
            raise ValueError('actual task landmark differs from surface calibration')
        packet.update(status='observed_model_mesh_region',object_root=geometry['prim_path'],
            model_frame_proof=proof,mesh_paths=geometry['selected_mesh_paths'],triangle_indices=indices.tolist(),
            local_triangles_m=triangles.tolist(),root_pose_at_capture=root.tolist(),landmark_pose_at_capture=landmark.tolist())
    except Exception as error:packet.update(status='unavailable',reason=type(error).__name__+': '+str(error))
    return packet


def validate_capture(packet,profile):
    if not packet or packet.get('status')=='unavailable':return {'status':'partial_evidence','unavailable':['live_target_surface_capture_unavailable'],'scope':SCOPE}
    checks={}
    try:
        proof=packet['model_frame_proof'];row=profile['models'][proof['model']]
        checks['surface_capture_source']=(packet['status']=='observed_model_mesh_region' and packet['source']==SOURCE
            and packet['frame']=='scaled_object_root_local' and packet['length_unit']=='metres'
            and type(packet['physics_step']) is int and packet['physics_step']>=0
            and type(packet['environment_index']) is int and packet['environment_index']>=0
            and isinstance(packet['object_root'],str) and packet['object_root'].startswith('/'))
        checks['surface_capture_binding']=(packet['label']==profile['label'] and packet['surface_tag']==profile['surface_tag']
            and packet['mesh_paths']==profile['mesh_paths'] and packet['triangle_indices']==row['triangle_indices']
            and proof['asset_sha256']==row['asset_sha256']
            and np.allclose(proof['scaled_bounds_m'],row['scaled_bounds_m'],rtol=0,atol=1e-7))
        triangles=np.asarray(packet['local_triangles_m']);expected=np.asarray(row['expected_triangles_m'])
        checks['surface_capture_triangles']=(triangles.shape==expected.shape and np.isfinite(triangles).all()
            and np.allclose(triangles,expected,rtol=0,atol=1e-7))
        root=np.asarray(packet['root_pose_at_capture']);landmark=np.asarray(packet['landmark_pose_at_capture']);local=np.asarray(row['landmark_root_pose'])
        checks['surface_capture_landmark']=(np.allclose(root[:3]+_rotation(root[3:])@local[:3],landmark[:3],rtol=0,atol=1e-7)
            and np.allclose(_rotation(root[3:])@_rotation(local[3:]),_rotation(landmark[3:]),rtol=0,atol=1e-7))
    except (KeyError,TypeError,ValueError,IndexError,AttributeError):checks['surface_capture_fields']=False
    failed=[k for k,v in checks.items() if not v]
    return {'status':'inconsistent_evidence' if failed else 'consistent_evidence','checks':checks,'failed_checks':failed,'scope':SCOPE}


def contact_surface(packet,profile,points,root_pose,step,origin):
    witness={'physics_step':step,'frame':'environment_local_world','root_pose':np.asarray(root_pose).tolist(),
        'environment_origin_world_m':deepcopy(origin),'all_contact_points':np.asarray(points).tolist(),
        'capture':deepcopy(packet),'scope':SCOPE}
    if packet['status']!='observed_model_mesh_region':
        witness.update(status='unavailable',reason=packet.get('reason'));return witness,np.zeros(len(points),dtype=bool)
    triangles=np.asarray(packet['local_triangles_m']);root=np.asarray(root_pose)
    local=(np.asarray(points)-root[:3])@_rotation(root[3:])
    distances=point_surface_distances(local,triangles.reshape(-1,3),np.arange(len(triangles)*3).reshape(-1,3))
    witness.update(status='observed_surface_distances',all_distances_m=distances.tolist())
    return witness,distances<=profile['distance_tolerance_m']


def validate_surface_event(config,event,capture):
    profile=config['target_surface'];w=event.get('target_surface_witness') or {};checks={};unavailable=[];metrics={}
    initial=validate_capture(capture,profile)
    checks.update(initial.get('checks',{}));unavailable.extend(initial.get('unavailable',[]))
    if initial.get('unavailable') and not profile['require_contact']:
        return {'status':'partial_evidence','checks':checks,'failed_checks':[],
            'unavailable':unavailable,'scope':SCOPE}
    try:
        checks['surface_event_capture_binding']=w['capture']==capture
        checks['surface_event_clock']=(type(w['physics_step']) is int and w['physics_step']==event['physics_step']
            and capture['physics_step']<=w['physics_step'] and w['frame']=='environment_local_world')
        triangles=np.asarray(capture['local_triangles_m']);root=np.asarray(w['root_pose']);points=np.asarray(w['all_contact_points'])
        local=(points-root[:3])@_rotation(root[3:])
        distances=point_surface_distances(local,triangles.reshape(-1,3),np.arange(len(triangles)*3).reshape(-1,3))
        checks['surface_distances_reproduced']=np.allclose(distances,w['all_distances_m'],rtol=1e-7,atol=1e-9)
        indices=w['selected_point_indices'];chosen=points[indices];own=distances[indices]
        checks['surface_selected_contacts']=(bool(indices) and len(set(indices))==len(indices)
            and all(type(i) is int and 0<=i<len(points) for i in indices)
            and np.allclose(chosen,event['contact_points'],rtol=0,atol=1e-9))
        if profile['require_contact']:checks['surface_contact_tolerance']=np.all(own<=profile['distance_tolerance_m'])
        origin=np.asarray(w['environment_origin_world_m']);rows=event['tool_target_contacts'];target=capture['object_root']
        checks['surface_force_positions']=(origin.shape==(3,) and np.isfinite(origin).all()
            and np.allclose(np.asarray([r['position_world'] for r in rows])-origin,chosen,rtol=0,atol=1e-7))
        checks['surface_force_clock_impulse']=(len(rows)==len(chosen) and len(rows)>0 and all(
            type(r['force_report_physics_step']) is int and r['force_report_physics_step']==event['physics_step']
            and np.asarray(r['impulse']).shape==(3,) and np.isfinite(r['impulse']).all()
            and np.linalg.norm(r['impulse'])>1e-9
            and np.asarray(r['normal_world']).shape==(3,) and np.isfinite(r['normal_world']).all()
            and np.isclose(np.linalg.norm(r['normal_world']),1,atol=1e-3,rtol=0) for r in rows))
        checks['surface_actor_binding']=all(any(r['actor'+str(i)]==target or r['actor'+str(i)].startswith(target+'/') for i in (0,1)) for r in rows)
        checks['surface_environment_binding']=event['held_contact']['environment_index']==capture['environment_index']
        local_landmark=np.asarray(profile['models'][capture['model_frame_proof']['model']]['landmark_root_pose'])
        checks['surface_event_root_landmark'] = np.allclose(root[:3]+_rotation(root[3:])@local_landmark[:3],
            event['target_landmark_position'],rtol=0,atol=1e-7)
        metrics={'selected_surface_distances_m':own.tolist(),'distance_tolerance_m':profile['distance_tolerance_m']}
    except (KeyError,TypeError,ValueError,IndexError,AttributeError):checks['surface_event_fields']=False
    failed=[k for k,v in checks.items() if not v]
    return {'status':'inconsistent_evidence' if failed else 'partial_evidence' if unavailable else 'consistent_evidence',
        'checks':{k:bool(v) for k,v in checks.items()},'failed_checks':failed,'unavailable':unavailable,
        'metrics':metrics if not failed else {},'scope':SCOPE}
