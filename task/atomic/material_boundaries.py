"""Independently qualify geometry sampled at named source exit/transfer boundaries."""
from copy import deepcopy
import numpy as np
from task.atomic.geometry import _rotation
from task.atomic.material_validation import initial_fluid_witness,validate_flow_witness
from task.atomic.contact_validation import validate_contact_witness

SCOPE='retained source qualification and sampled transfer-core geometry; not unsaved contact persistence, settled full quantity or fluid volume'


def _frame(selector,pose,source,step):
    pose=np.asarray(pose,dtype=float);root=np.asarray(source['root_pose'],dtype=float)
    if pose.shape!=(7,) or root.shape!=(7,) or not np.isfinite(pose).all() or not np.isfinite(root).all():return False
    if source['label']!=selector['label'] or source['physics_step']!=step:return False
    if selector['kind']=='model_calibrated_frame':
        proof=source['model_frame_proof'];row=selector['models'][proof['model']]
        if proof['asset_sha256']!=row['asset_sha256'] or not np.allclose(proof['scaled_bounds_m'],row['scaled_bounds_m'],atol=1e-7,rtol=0):return False
        local=np.asarray(row['local_pose'])
    elif selector['kind']=='calibrated_frame':local=np.asarray(selector['local_pose'])
    elif selector['kind']=='object_pose':local=np.array([0,0,0,1,0,0,0])
    else:raise ValueError('unsupported transfer-core selector')
    return bool(np.allclose(root[:3]+_rotation(root[3:])@local[:3],pose[:3],rtol=0,atol=1e-7)
        and np.allclose(_rotation(root[3:])@_rotation(local[3:]),_rotation(pose[3:]),rtol=0,atol=1e-7))


def validate_material_event(stage,name):
    config=stage.get('recognition') or {}
    if config.get('kind') not in ('fluid_material_transfer','rigid_material_transfer') or name not in ('source_exit','first_transfer'):
        return {'status':'not_applicable'}
    events=stage.get('physical_events',{});event=events.get(name)
    if event is None:return {'status':'unobserved','scope':SCOPE}
    checks={};unavailable=[]
    try:
        key='particle_id' if config['kind']=='fluid_material_transfer' else 'material_label'
        identifier=event[key];step=event['physics_step']
        checks['material_event_identity']=((type(identifier) is int and identifier>=0) if key=='particle_id'
            else identifier in config['material_labels'])
        checks['material_event_clock']=type(step) is int and step>=0
        provenance=event.get('source_exit') if name=='first_transfer' else event.get('source_exit_provenance')
        # An older source-exit event can bind to the retained same-material transfer copy.
        if provenance is None and name=='source_exit':
            transfer=events.get('first_transfer') or {};p=transfer.get('source_exit') or {}
            if transfer.get(key)==identifier and p.get('exit_physics_step')==step:provenance=p
        if provenance is None:
            unavailable.append('source_exit_provenance_absent')
        else:
            exit_step=provenance['exit_physics_step']
            checks['material_event_source_order']=type(exit_step) is int and exit_step>=0 and (
                step==exit_step if name=='source_exit' else step>=exit_step)
            hold=provenance['exit_contact'];force=validate_contact_witness(hold,
                {'label':config['label'],'arm':config['arm'],'min_finger_bodies':2})
            checks['material_source_force_binding']=force['status']!='inconsistent_contact_evidence'
            unavailable.extend(force.get('unavailable',[]))
            mouth=provenance.get('source_mouth_crossing')
            if mouth is None:
                unavailable.append('sampled_source_mouth_window_absent')
            else:
                # Use the actual source-mouth window for the existing source witness checker.
                # It is not relabeled as, or used to score, a destination crossing.
                source_config=deepcopy(config);source_config.pop('flow',None)
                cohort=initial_fluid_witness(config,stage.get('material_transfer_initial_state')) if key=='particle_id' else None
                source=validate_flow_witness(str(identifier),{'source_exit_provenance':provenance,
                    'before':mouth['before'],'after':mouth['after']},source_config,cohort,stage.get('material_bounds'))
                checks.update({'material_source_'+k:v for k,v in source['checks'].items()})
                unavailable.extend(source['unavailable'])
                history=(stage.get('physical_metrics') or {}).get('source_mouth_sampling',{}).get('candidate_witnesses',[])
                matching=[r for r in history if r.get('material_id')==str(identifier)
                    and r.get('after',{}).get('physics_step')==exit_step]
                if len(matching)==1:
                    from task.atomic.source_candidates import validate_candidate
                    candidate=validate_candidate(matching[0],config,stage.get('material_bounds'),cohort)
                    checks.update({'material_candidate_'+k:v for k,v in candidate['checks'].items()})
                    unavailable.extend(candidate['unavailable']);q=matching[0]['qualification']
                    checks['material_qualified_candidate_binding']=(q['eligible_for_source_exit'] is True
                        and q['held_contact']==hold and np.isclose(q['tilt_rad'],provenance['exit_tilt_rad'],rtol=1e-7,atol=1e-9))
                elif history or config.get('kind')=='rigid_material_transfer':
                    unavailable.append('matching_source_candidate_not_retained')
            if name=='source_exit':
                if 'held_contact' in event:checks['material_exit_hold_copy']=event['held_contact']==hold
                if 'tilt_rad' in event:checks['material_exit_tilt_copy']=np.isclose(event['tilt_rad'],provenance['exit_tilt_rad'],rtol=1e-7,atol=1e-9)
        if name=='first_transfer':
            if not {'current_region_frames','current_region_sources'}<=event.keys():
                unavailable.append('same_step_transfer_core_frames_absent')
            else:
                frames=event['current_region_frames'];sources=event['current_region_sources']
                if provenance is not None and 'environment_index' in provenance['exit_contact']:
                    checks['material_transfer_environment']=event['environment_index']==provenance['exit_contact']['environment_index']
                else:unavailable.append('material_transfer_environment_binding_absent')
                for region in ('source','target'):
                    checks['material_current_'+region+'_frame']=_frame(config[region+'_frame'],frames[region],sources[region],step)
                if key=='particle_id':
                    points=np.asarray(event['position'],dtype=float)[None,:]
                    if points.shape!=(1,3) or not np.isfinite(points).all():raise ValueError('invalid transfer particle')
                else:
                    from task.atomic.finite_material import validate_material_bound
                    bound=(stage.get('material_bounds') or {}).get(identifier)
                    if bound is None or bound.get('status')=='unavailable':
                        unavailable.append('whole_rigid_transfer_mesh_absent');points=None
                    else:
                        validate_material_bound(bound);pose=np.asarray(event['material_pose'])
                        if pose.shape!=(7,) or not np.isfinite(pose).all():raise ValueError('invalid current material root pose')
                        points=np.asarray(bound['local_vertices_m'])@_rotation(pose[3:]).T+pose[:3]
                        checks['material_transfer_mesh_identity']=bound['label']==identifier and bound['physics_step']<=step
                        checks['material_transfer_mesh_environment']=bound['environment_index']==event['environment_index']
                if points is not None:
                    for region,inside in (('source',False),('target',True)):
                        frame=np.asarray(frames[region]);value=bool(np.all(np.abs((points-frame[:3])@_rotation(frame[3:]))<=np.asarray(config[region+'_half_extents_m'])))
                        checks['material_current_'+region+'_containment']=value==inside
    except (KeyError,TypeError,ValueError,IndexError,AttributeError) as error:
        checks['material_event_fields']=False;unavailable.append(str(error))
    failed=[k for k,v in checks.items() if not v]
    return {'status':'inconsistent_evidence' if failed else 'partial_evidence' if unavailable else 'consistent_evidence',
        'checks':{k:bool(v) for k,v in checks.items()},'failed_checks':failed,'unavailable':unavailable,'scope':SCOPE}
