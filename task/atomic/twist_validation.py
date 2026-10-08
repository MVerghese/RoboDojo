"""Retained relative rotation and force-bound twist interval checks."""
from copy import deepcopy
import math
import numpy as np
from task.atomic.geometry import _rotation
from task.atomic.landmarks import matrix_quaternion


def rotation_sample(step,pose,pivot,hold,pair):
    """Keep one raw force row per finger and one constraint row, plus live poses."""
    def force_rows(rows,key=None):
        selected=[];seen=set()
        for row in rows:
            identity=row.get(key) if key else 'pair'
            if identity in seen:continue
            selected.append(deepcopy(row));seen.add(identity)
        return selected
    held={k:deepcopy(v) for k,v in hold.items() if k in
        ('label','resolved_arm','finger_bodies','physics_step','consecutive_contact_steps',
         'contact_interval_start_step','object_root','environment_index')}
    held['contacts']=force_rows(hold.get('contacts',[]),'finger_body')
    constrained={k:deepcopy(v) for k,v in pair.items() if k in ('object_roots','physics_step','environment_index')}
    constrained['contacts']=force_rows(pair.get('contacts',[]))
    return {'physics_step':step,'object_pose':np.asarray(pose).tolist(),'pivot_pose':np.asarray(pivot).tolist(),
            'held_contact':held,'constraint_contact':constrained}


def validate_twist(stage,require_completion=True):
    config=stage.get('recognition') or {}
    if config.get('kind')!='contact_constrained_twist':return {'status':'not_applicable'}
    event=stage.get('physical_events',{}).get('rotation')
    if event is None:return {'status':'unobserved'}
    samples=event.get('rotation_samples')
    scope='retained relative rotation samples and selected raw force rows; no torque, thread engagement or unsaved contact manifold reconstruction'
    if not samples or event.get('rotation_history_truncated'):
        return {'status':'partial_evidence','unavailable':['complete_rotation_sample_history_absent'],'scope':scope}
    checks={};unavailable=[];angle=0.;off_axis=0.;previous=None;arms=[];starts=[]
    def force(row,step):
        impulse=np.asarray(row['impulse'],dtype=float)
        return (row['force_report_physics_step']==step and impulse.shape==(3,)
            and np.isfinite(impulse).all() and np.linalg.norm(impulse)>1e-9)
    def under(path,root):return path==root or path.startswith(root.rstrip('/')+'/')
    try:
        axis=np.asarray(config['axis'],dtype=float);axis/=np.linalg.norm(axis)
        steps=[s['physics_step'] for s in samples]
        checks['rotation_contiguous_samples']=(len(samples)>=2 and all(type(n) is int and n>=0 for n in steps)
            and steps==list(range(steps[0],steps[-1]+1)) and steps[-1]==event['physics_step'])
        for sample in samples:
            step=sample['physics_step'];pose=np.asarray(sample['object_pose']);pivot=np.asarray(sample['pivot_pose'])
            if pose.shape!=(7,) or pivot.shape!=(7,) or not np.isfinite(pose).all() or not np.isfinite(pivot).all():
                raise ValueError('invalid retained twist poses')
            rotation=_rotation(pivot[3:]).T@_rotation(pose[3:])
            if previous is not None:
                # Quaternion axis-angle reconstruction independently checks the
                # recognizer's matrix-log accumulated signed/off-axis increments.
                q=matrix_quaternion(rotation@previous.T)
                if q[0]<0:q=-q
                length=float(np.linalg.norm(q[1:]));theta=2*math.atan2(length,float(q[0]))
                checks['rotation_unaliased_substeps']=checks.get('rotation_unaliased_substeps',True) and theta<math.pi-1e-4
                vector=np.zeros(3) if length<1e-12 else q[1:]*theta/length
                signed=float(vector@axis);angle+=signed;off_axis+=float(np.linalg.norm(vector-signed*axis))
            previous=rotation
            local=_rotation(pivot[3:]).T@(pose[:3]-pivot[:3]);depth=-float(local@axis)
            radius=float(np.linalg.norm(local-(local@axis)*axis))
            checks['rotation_constraint_geometry']=checks.get('rotation_constraint_geometry',True) and (
                radius<=config['max_radius_m'] and config['min_depth_m']<=depth<=config['max_depth_m'])
            hold=sample['held_contact'];arms.append(hold['resolved_arm']);starts.append(hold['contact_interval_start_step'])
            checks['rotation_hold_counts']=checks.get('rotation_hold_counts',True) and (
                type(hold['consecutive_contact_steps']) is int and type(starts[-1]) is int
                and starts[-1]>=0 and hold['consecutive_contact_steps']>=1
                and starts[-1]+hold['consecutive_contact_steps']-1==step)
            if 'label' not in hold:unavailable.append('sampled_held_label_absent')
            else:checks['rotation_held_label']=checks.get('rotation_held_label',True) and hold['label']==config['label']
            rows=hold.get('contacts',[]);fingers={r.get('finger_body') for r in rows}
            if not rows:
                unavailable.append('sampled_finger_force_rows_absent')
            else:
                checks['rotation_finger_forces']=checks.get('rotation_finger_forces',True) and (
                    len(fingers)>=2 and fingers==set(hold['finger_bodies'])
                    and all(force(r,step) and r['arm']==arms[-1] for r in rows))
                root=hold.get('object_root')
                if root is None:unavailable.append('sampled_finger_actor_root_absent')
                else:
                    checks['rotation_finger_actor_binding']=checks.get('rotation_finger_actor_binding',True) and all(
                        any(under(r['actor'+str(i)],root) and r['actor'+str(1-i)]==r['finger_body'] for i in (0,1)) for r in rows)
            pair=sample['constraint_contact'];rows=pair.get('contacts',[])
            checks['rotation_constraint_forces']=checks.get('rotation_constraint_forces',True) and bool(rows) and all(force(r,step) for r in rows)
            roots=pair.get('object_roots')
            if roots is None:unavailable.append('sampled_constraint_actor_roots_absent')
            else:
                checks['rotation_constraint_actor_binding']=checks.get('rotation_constraint_actor_binding',True) and (
                    len(roots)==2 and roots[0]!=roots[1] and all(any(
                        under(r['actor'+str(i)],roots[0]) and under(r['actor'+str(1-i)],roots[1]) for i in (0,1)) for r in rows)
                    and (hold.get('object_root') is None or roots[0]==hold['object_root']))
        checks['rotation_same_hold_interval']=(len(set(arms))==1 and len(set(starts))==1
            and (config['arm']=='any' or arms[0]==config['arm'])
            and event['held_contact']['resolved_arm']==arms[-1]
            and event['held_contact']['contact_interval_start_step']==starts[-1])
        checks['rotation_final_hold_threshold']=samples[-1]['held_contact']['consecutive_contact_steps']>=config['min_contact_steps']
        checks['rotation_signed_angle']=bool(np.isclose(event['signed_angle_rad'],angle,rtol=1e-7,atol=1e-9))
        checks['rotation_off_axis_angle']=bool(np.isclose(event['off_axis_rotation_rad'],off_axis,rtol=1e-7,atol=1e-9))
        checks['rotation_final_constraints']=bool(np.isclose(event['radius_m'],radius,rtol=1e-7,atol=1e-9)
            and np.isclose(event['depth_m'],depth,rtol=1e-7,atol=1e-9))
        checks['rotation_off_axis_limit']=off_axis<=config['max_off_axis_rad']+1e-9
        if require_completion:
            checks['rotation_declared_thresholds']=config['direction']*angle>=config['min_angle_rad']-1e-9
    except (KeyError,ValueError,TypeError,IndexError,AttributeError,ZeroDivisionError):checks['rotation_fields']=False
    failed=[k for k,v in checks.items() if not v]
    return {'status':'inconsistent_evidence' if failed else 'partial_evidence' if unavailable else 'consistent_evidence',
        'checks':{k:bool(v) for k,v in checks.items()},'failed_checks':failed,'unavailable':sorted(set(unavailable)),
        'metrics':{'signed_angle_rad':angle,'off_axis_rotation_rad':off_axis},'scope':scope}


def validate_twist_diagnostic(stage):
    interval=stage.get('twist_rotation_diagnostic')
    if interval is None:return {'status':'unobserved'}
    result=validate_twist({'recognition':stage.get('recognition'),
                          'physical_events':{'rotation':interval}},require_completion=False)
    result['scope']='retained net rotation of a valid held/constraint interval; diagnostic only, not completed action or native success'
    return result
