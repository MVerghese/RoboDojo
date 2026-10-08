"""Check retained qualification metadata at stage-success geometry events."""
import math
import numpy as np


def validate_stage_success(stage,measurement):
    if measurement.get('event',{}).get('kind')!='stage_success':return {'status':'not_applicable'}
    scope='retained completion flags, measurement clock and pick lift bounds; unsaved force/maintained-hold histories not reconstructed'
    event=measurement.get('event_evidence')
    if not isinstance(event,dict) or event.get('context')!='qualified_atomic_stage_success':
        return {'status':'partial_evidence','unavailable':['qualified_completion_metadata_absent'],'scope':scope}
    checks={};unavailable=[]
    try:
        checks['qualified_native_and_atomic_completion']=event['native_endpoint_passed'] is True and event['qualified_action_success'] is True
        checks['maintained_hold_failures_absent']=type(event['maintained_hold_failure_count']) is int and event['maintained_hold_failure_count']==0
        step=measurement.get('measurement_physics_step');clock=event.get('physics_step')
        if step is None or clock is None:unavailable.append('completion_physics_clock_absent')
        else:checks['completion_synchronized_measurement']=type(step) is int and type(clock) is int and step>=0 and step==clock
        config=stage.get('recognition') or {}
        checks['completion_recognizer_binding']=event['recognition_kind']==config.get('kind')
        if config:checks['completion_physical_interaction']=event['physical_interaction_observed'] is True
        if stage.get('family')=='pick' and config:
            displacement=np.asarray(event['contact_coupled_displacement_m'],dtype=float);threshold=event['required_held_lift_m']
            if (displacement.shape!=(3,) or not np.isfinite(displacement).all() or type(threshold) not in (int,float)
                    or not math.isfinite(threshold) or threshold<=0):raise ValueError('invalid held lift witness')
            declared=[config['motion_threshold_m']]+[c['args']['z_threshold'] for c in stage.get('recognition_checks',[])
                if c['name']=='is_lift' and 'z_threshold' in c['args']]
            checks['completion_held_lift_threshold']=threshold>=max(declared) and displacement[2]>=threshold
            checks['completion_current_grasp']=event['current_hold_observed'] is True
    except (KeyError,ValueError,TypeError,IndexError,AttributeError):checks['completion_fields']=False
    failed=[k for k,v in checks.items() if not v]
    return {'status':'inconsistent_evidence' if failed else 'partial_evidence' if unavailable else 'consistent_evidence',
            'checks':{k:bool(v) for k,v in checks.items()},'failed_checks':failed,'unavailable':unavailable,'scope':scope}
