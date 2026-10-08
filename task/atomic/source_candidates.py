"""Reproduce sampled mouth candidates without promoting them to action success."""
from collections import Counter
import math
import numpy as np
from task.atomic.geometry import _rotation
from task.atomic.flow import score_source_exit


def _equal(a,b):
    if isinstance(a,dict) and isinstance(b,dict):
        return a.keys()==b.keys() and all(_equal(a[k],b[k]) for k in a)
    if isinstance(a,list) and isinstance(b,list):
        return len(a)==len(b) and all(_equal(x,y) for x,y in zip(a,b))
    if type(a) in (float,int) and type(b) in (float,int):return bool(np.isclose(a,b,rtol=1e-7,atol=1e-9))
    return type(a)==type(b) and a==b


def _pose(value):
    value=np.asarray(value,dtype=float)
    if value.shape!=(7,) or not np.isfinite(value).all():raise ValueError('invalid candidate pose')
    _rotation(value[3:])
    return value


def validate_candidate(row,config,bounds=None,cohort=None):
    checks={};unavailable=[];result=None;contact=None
    def check(name,value):checks[name]=bool(value)
    try:
        before,after=row['before'],row['after'];ident=row['material_id'];step=after['physics_step']
        check('adjacent_physics_samples',type(step) is int and type(before['physics_step']) is int
            and before['physics_step']>=0 and step==before['physics_step']+1)
        dt=after['dt_s'];check('fixed_positive_dt',type(dt) in (float,int) and math.isfinite(dt)
            and dt>0 and dt==before['dt_s'])
        result=score_source_exit(config['source_exit'],before,after)
        check('candidate_geometry_reproduced',_equal(result,row['result']))
        q=row['qualification'];check('qualification_context',q['context']=='source_exit_candidate_qualification')
        flags=('initial_cohort_eligible','inside_source','reentered_source','already_qualified_before','eligible_for_source_exit')
        check('qualification_boolean_fields',all(type(q[k]) is bool for k in flags))
        initial,current=_pose(q['initial_source_frame']),_pose(q['source_frame'])
        tilt=float(np.arccos(np.clip(_rotation(current[3:])[:,2]@_rotation(initial[3:])[:,2],-1,1)))
        check('tilt_from_source_frames',type(q['tilt_rad']) in (float,int)
            and math.isfinite(q['tilt_rad']) and np.isclose(q['tilt_rad'],tilt,rtol=1e-7,atol=1e-9))
        source=after.get('opening_source',{});root=source.get('root_pose')
        if root is None:unavailable.append('mouth_root_frame_binding_absent')
        else:
            root=_pose(root)
            for name,selector,pose in [('mouth',config['source_exit']['opening'],after['opening']),
                                        ('core',config['source_frame'],current)]:
                if selector['kind']=='model_calibrated_frame':
                    proof=source['model_frame_proof'];model=selector['models'][proof['model']]
                    check(name+'_asset_binding',model['asset_sha256']==proof['asset_sha256']
                        and np.allclose(model['scaled_bounds_m'],proof['scaled_bounds_m'],rtol=0,atol=1e-7))
                    local=_pose(model['local_pose'])
                elif selector['kind']=='calibrated_frame':local=_pose(selector['local_pose'])
                elif selector['kind']=='object_pose':local=np.array([0,0,0,1,0,0,0])
                else:unavailable.append(name+'_calibrated_frame_reconstruction_unavailable');continue
                pose=_pose(pose)
                check(name+'_frame_binding',np.allclose(root[:3]+_rotation(root[3:])@local[:3],pose[:3],rtol=1e-7,atol=1e-9)
                    and np.allclose(_rotation(root[3:])@_rotation(local[3:]),_rotation(pose[3:]),rtol=1e-7,atol=1e-9))
        hold=q['held_contact']
        if hold is not None:
            from task.atomic.contact_validation import validate_contact_witness
            contact=validate_contact_witness(hold,{'label':config['label'],'arm':config['arm'],'min_finger_bodies':2})
            check('retained_source_contact_consistent',contact['status']!='inconsistent_contact_evidence')
            if contact['status']=='partial_contact_evidence':unavailable.append('partial_source_contact_binding')
            count,start=hold['consecutive_contact_steps'],hold['contact_interval_start_step']
            check('same_step_sustained_hold',type(count) is int and type(start) is int and start>=0
                and count>=config['min_contact_steps'] and start+count-1==step and hold['physics_step']==step)
        position=np.asarray(after['position'],dtype=float)
        if position.shape!=(3,) or not np.isfinite(position).all():raise ValueError('invalid candidate center')
        if config['kind']=='fluid_material_transfer':
            vertices=position[None,:]
            if cohort is not None:
                checks.update({'cohort_'+k:bool(v) for k,v in cohort['checks'].items()})
                unavailable.extend(cohort['unavailable'])
            if cohort is not None and cohort.get('eligible_ids') is not None:
                check('initial_particle_cohort',int(ident) in cohort['eligible_ids'] and q['initial_cohort_eligible'])
                if cohort.get('source_frame') is not None:check('initial_source_frame_binding',np.allclose(initial,cohort['source_frame'],rtol=1e-7,atol=1e-9))
            else:unavailable.append('initial_particle_cohort_absent')
        else:
            check('declared_rigid_material',ident in config['material_labels'])
            bound=after.get('material_bound')
            if bound is None or bound.get('status')=='unavailable' or after.get('material_pose') is None:
                unavailable.append('finite_source_containment_geometry_absent');vertices=None
            else:
                from task.atomic.finite_material import validate_material_bound
                validate_material_bound(bound);pose=_pose(after['material_pose'])
                check('same_initial_material_bound',bool(bounds) and bound==bounds.get(ident)
                    and bound['label']==ident and bound['physics_step']<=step)
                vertices=np.asarray(bound['local_vertices_m'])@_rotation(pose[3:]).T+pose[:3]
                center=np.asarray(bound['local_center_m'])@_rotation(pose[3:]).T+pose[:3]
                check('material_center_binding',np.allclose(center,position,rtol=1e-7,atol=1e-9))
                if hold is not None:
                    if 'environment_index' not in hold:unavailable.append('source_contact_environment_absent')
                    else:check('material_environment_binding',bound['environment_index']==hold['environment_index'])
        if vertices is not None:
            inside=bool(np.all(np.abs((vertices-current[:3])@_rotation(current[3:]))<=np.asarray(config['source_half_extents_m'])))
            check('source_containment_from_geometry',inside==q['inside_source'])
        expected=bool(q['initial_cohort_eligible'] and not q['inside_source'] and not q['reentered_source']
            and not q['already_qualified_before'] and result['passed'] is True and hold is not None and tilt>=config['min_tilt_rad'])
        check('qualification_decision',q['eligible_for_source_exit']==expected)
    except (KeyError,TypeError,ValueError,IndexError,AttributeError) as error:
        checks['candidate_fields']=False;unavailable.append(str(error))
    failed=[k for k,v in checks.items() if not v]
    return {'material_id':row.get('material_id'),'physics_step':row.get('after',{}).get('physics_step'),
        'status':'inconsistent_evidence' if failed else 'partial_evidence' if unavailable else 'consistent_evidence',
        'checks':checks,'failed_checks':failed,'unavailable':unavailable,'result':result,
        'qualification':row.get('qualification'),'required_tilt_rad':config.get('min_tilt_rad'),
        'contact_witness':contact}


def audit_source_candidates(stage):
    config=stage.get('recognition') or {}
    if config.get('kind') not in ('rigid_material_transfer','fluid_material_transfer') or 'source_exit' not in config:
        return {'status':'not_applicable'}
    raw=(stage.get('physical_metrics') or {}).get('source_mouth_sampling',{})
    scope=('bounded source-mouth candidates and same-step recorded qualification gates; diagnostic only, '
        'not destination transfer, whole fluid volume, continuous finite-body passage or independent proof of absent contact')
    if 'candidate_witnesses' not in raw:
        return {'status':'partial_evidence','unavailable':['raw_candidate_history_absent'],
            'candidate_crossings':raw.get('candidate_crossings'),'candidate_outcomes':raw.get('candidate_outcomes',{}),'scope':scope}
    cohort=None
    if config['kind']=='fluid_material_transfer':
        from task.atomic.material_validation import initial_fluid_witness
        cohort=initial_fluid_witness(config,stage.get('material_transfer_initial_state'))
    rows=[validate_candidate(row,config,stage.get('material_bounds'),cohort) for row in raw['candidate_witnesses']]
    keys=[(r['material_id'],r['physics_step']) for r in rows]
    count=raw.get('candidate_crossings');limit=raw.get('candidate_witness_limit');truncated=raw.get('candidate_history_truncated')
    valid=(type(count) is int and type(limit) is int and limit==32 and count>=0
        and len(rows)==min(count,limit) and len(set(keys))==len(rows)
        and type(truncated) is bool and truncated==(count>len(rows)))
    outcomes=Counter('inside_aperture' if r['result']['passed'] is True else 'outside_aperture'
        if r['result']['passed'] is False else r['result']['status'] for r in rows if r['result'] is not None)
    saved=raw.get('candidate_outcomes',{})
    valid=valid and (all(outcomes[k]<=saved.get(k,0) for k in outcomes) if truncated else dict(outcomes)==saved)
    status=('inconsistent_evidence' if not valid or any(r['status']=='inconsistent_evidence' for r in rows)
        else 'unobserved' if not rows else 'partial_evidence' if truncated or any(r['status']=='partial_evidence' for r in rows)
        else 'consistent_evidence')
    return {'status':status,'history_counts_consistent':valid,'candidate_crossings':count,
        'candidate_outcomes':saved,'retained_candidates':len(rows),'history_truncated':truncated,
        'candidates':rows,'scope':scope}
