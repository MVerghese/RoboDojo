"""Reconstruct supported-release stability from retained bounded pose windows."""
import math
import numpy as np
from task.atomic.geometry import _angular_error
from task.atomic.support_validation import validate_support_witness


def validate_settling(stage):
    c=stage.get('recognition') or {}
    if c.get('kind')!='supported_release':return {'status':'not_applicable'}
    event=stage.get('physical_events',{}).get('settled')
    if event is None:return {'status':'unobserved'}
    scope='retained supported-release pose window and named support snapshots; no future immobility or unsaved contact histories reconstructed'
    raw=event.get('settling_samples')
    if not raw:return {'status':'partial_evidence','unavailable':['settling_pose_window_absent'],'scope':scope}
    checks={};unavailable=[];metrics={}
    try:
        count=event['stable_steps'];steps=[s['physics_step'] for s in raw]
        checks['settling_contiguous_window']=(type(count) is int and count>=c['settle_steps']
            and len(raw)==c['settle_steps'] and all(type(s) is int and s>=0 for s in steps)
            and steps==list(range(steps[0],steps[-1]+1)) and steps[-1]==event['physics_step'])
        checks['settling_anchor_time']=(type(event['settle_anchor_step']) is int
            and event['settle_anchor_step']+count-1==event['physics_step']
            and event['settle_anchor_step']<=steps[0])
        anchor=np.asarray(event['settle_anchor_pose'],dtype=float);poses=np.asarray([s['pose'] for s in raw],dtype=float)
        if anchor.shape!=(7,) or poses.shape!=(len(raw),7) or not np.isfinite(anchor).all() or not np.isfinite(poses).all():
            raise ValueError('invalid settling pose window')
        distance=np.linalg.norm(poses[:,:3]-anchor[:3],axis=1)
        angles=[_angular_error(p[3:],anchor[3:]) for p in poses]
        delta=np.linalg.norm(np.diff(poses[:,:3],axis=0),axis=1)
        delta_angles=[_angular_error(a[3:],b[3:]) for a,b in zip(poses,poses[1:])]
        checks['settling_anchor_bounds']=bool(np.all(distance<=c['max_settle_displacement_m']) and
            all(a<=c['max_settle_angle_rad'] for a in angles))
        checks['settling_step_bounds']=bool(np.all(delta<=c['max_position_step_m']) and
            all(a<=c['max_angle_step_rad'] for a in delta_angles))
        checks['settling_final_pose']=bool(np.allclose(event['pose'],poses[-1],rtol=1e-7,atol=1e-9))
        checks['settling_final_residuals']=bool(np.isclose(event['settle_displacement_m'],distance[-1],rtol=1e-7,atol=1e-9)
            and np.isclose(event['settle_angle_rad'],angles[-1],rtol=1e-7,atol=1e-9))
        if event['settle_anchor_step']==steps[0]:
            checks['settling_anchor_pose']=bool(np.allclose(anchor,poses[0],rtol=1e-7,atol=1e-9))
        roots=[]
        for sample in raw:
            support=sample['support'];roots.append(support.get('object_root'))
            check=validate_support_witness({'support_contact':True,'support_contact_evidence':support})
            checks['settling_support_forces']=checks.get('settling_support_forces',True) and check['status']!='inconsistent_support_evidence'
            if check['status']=='partial_support_evidence':unavailable.extend(check['unavailable'])
            checks['settling_named_support']=checks.get('settling_named_support',True) and (
                support.get('object')==c['label'] and bool(support.get('contacts'))
                and all(r['support_label'] in c['support_labels'] for r in support['contacts']))
            checks['settling_recorded_robot_separation']=checks.get('settling_recorded_robot_separation',True) and sample['robot_touching'] is False
        checks['settling_same_root']=bool(roots) and all(root==event['support'].get('object_root') for root in roots)
        dts=[s.get('dt_s') for s in raw]
        if any(dt is None for dt in dts):unavailable.append('settling_physics_dt_absent')
        else:
            checks['settling_fixed_dt']=all(type(dt) in (int,float) and math.isfinite(dt) and dt>0 and dt==dts[0] for dt in dts)
            if checks['settling_fixed_dt']:metrics['observed_duration_s']=dts[0]*(len(raw)-1)
        metrics.update(max_position_step_m=float(max(delta,default=0)),max_angle_step_rad=float(max(delta_angles,default=0)),
            max_position_from_anchor_m=float(max(distance)),max_angle_from_anchor_rad=float(max(angles)))
    except (KeyError,ValueError,TypeError,IndexError,AttributeError):checks['settling_fields']=False
    failed=[k for k,v in checks.items() if not v]
    return {'status':'inconsistent_evidence' if failed else 'partial_evidence' if unavailable else 'consistent_evidence',
        'checks':{k:bool(v) for k,v in checks.items()},'failed_checks':failed,'unavailable':sorted(set(unavailable)),
        'metrics':metrics,'scope':scope}
