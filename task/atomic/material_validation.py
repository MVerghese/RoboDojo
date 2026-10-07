"""Independent source-cohort and sampled flow witness checks.

Historical missing witnesses are partial evidence, not fabricated failures.
These checks do not reconstruct unsaved intermediate contacts or whole fluid volume.
"""
import math
import numpy as np
from task.atomic.geometry import _rotation


def initial_fluid_witness(config, initial):
    checks={};unavailable=[];ids=None;eligible=None
    source_frame=None
    if initial is None:
        return {'checks':{},'unavailable':['initial_region_witness_absent'],'ids':None,'eligible_ids':None,'source_frame':None}
    try:
        values=initial['ids'];points=np.asarray(initial['positions'],dtype=float)
        checks['persistent_population']=(all(type(i) is int and i>=0 for i in values)
            and len(set(values))==len(values) and bool(values)
            and points.shape==(len(values),3) and bool(np.isfinite(points).all()))
        if checks['persistent_population']:ids=set(values)
        frames=initial['region_frames'];masks=[]
        for name in ('source','target'):
            pose=np.asarray(frames[name],dtype=float)
            if pose.shape!=(7,) or not np.isfinite(pose).all():raise ValueError('invalid initial region frame')
            if name=='source':source_frame=pose
            local=(points-pose[:3])@_rotation(pose[3:])
            mask=np.all(np.abs(local)<=np.asarray(config[name+'_half_extents_m']),axis=1)
            recorded=initial['initial_in_'+name]
            checks[name+'_initial_mask']=(all(type(v) is bool for v in recorded)
                and recorded==mask.tolist())
            masks.append(mask)
        if ids is not None:
            eligible={i for i,a,b in zip(values,*masks) if a and not b}
    except KeyError as error:
        unavailable.append(str(error))
    except (TypeError,ValueError,IndexError) as error:
        checks['well_formed_initial_witness']=False;unavailable.append(str(error))
    return {'checks':checks,'unavailable':unavailable,'ids':ids,'eligible_ids':eligible,'source_frame':source_frame}


def validate_flow_witness(identifier, row, config, cohort=None):
    checks={};unavailable=[]
    def check(name,value):checks[name]=bool(value)
    try:
        p=row['source_exit_provenance'];before=row['before'];after=row['after']
        check('source_qualified',p.get('eligible') is True and p.get('exited_while_held_and_tilted') is True)
        if config.get('kind')=='rigid_material_transfer':
            check('initial_source_only',p.get('initial_in_source') is True and p.get('initial_in_target') is False)
        a,b=before['physics_step'],after['physics_step'];exit_step=p['exit_physics_step']
        check('adjacent_samples',type(a) is int and type(b) is int and 0<=a and b==a+1)
        check('exit_precedes_sampled_crossing',type(exit_step) is int and 0<=exit_step<=b)
        dt0,dt1=before['dt_s'],after['dt_s']
        check('fixed_positive_dt',type(dt0) in (int,float) and type(dt1) in (int,float)
              and math.isfinite(dt0) and dt0>0 and dt0==dt1)
        tilt=p['exit_tilt_rad']
        check('exit_tilt_threshold',type(tilt) in (int,float) and math.isfinite(tilt)
              and config['min_tilt_rad']<=tilt<=math.pi)
        if cohort is not None:
            checks.update(cohort['checks']);unavailable.extend(cohort['unavailable'])
            if cohort['ids'] is not None:check('initial_particle_identity',int(identifier) in cohort['ids'])
            if cohort['eligible_ids'] is not None:check('initial_source_only',int(identifier) in cohort['eligible_ids'])
        hold=p['exit_contact'];count=hold['consecutive_contact_steps'];start=hold['contact_interval_start_step']
        check('exit_hold_interval',type(count) is int and type(start) is int and start>=0
              and count>=config['min_contact_steps'] and start+count-1==exit_step
              and hold['physics_step']==exit_step)
        check('held_source_identity',hold['label']==config['label'])
        check('held_arm',bool(hold['resolved_arm']) and (config['arm']=='any' or hold['resolved_arm']==config['arm']))
        rows=hold['contacts'];fingers={r['finger_body'] for r in rows}
        check('distinct_force_fingers',len(fingers)>=2 and fingers==set(hold['finger_bodies']))
        check('synchronized_force_contacts',bool(rows) and all(
            r['force_report_physics_step']==exit_step and r['arm']==hold['resolved_arm']
            and np.asarray(r['impulse']).shape==(3,) and np.isfinite(r['impulse']).all()
            and np.linalg.norm(r['impulse'])>1e-9 for r in rows))
        initial=np.asarray(p['initial_source_frame']);current=np.asarray(p['exit_source_frame'])
        if initial.shape!=(7,) or current.shape!=(7,) or not np.isfinite(initial).all() or not np.isfinite(current).all():
            raise ValueError('invalid source tilt frame')
        calculated=float(np.arccos(np.clip(_rotation(current[3:])[:,2]@_rotation(initial[3:])[:,2],-1,1)))
        check('tilt_from_raw_frames',np.isclose(calculated,tilt,rtol=1e-7,atol=1e-9))
        if cohort is not None and cohort['source_frame'] is not None:
            check('initial_tilt_frame_binding',np.allclose(initial,cohort['source_frame'],rtol=1e-7,atol=1e-9))
        if config.get('kind')=='fluid_material_transfer':
            position=np.asarray(p['exit_position'],dtype=float)
            if position.shape!=(3,) or not np.isfinite(position).all():raise ValueError('invalid source-exit particle position')
            local=(position-current[:3])@_rotation(current[3:])
            check('outside_declared_source_core',not np.all(np.abs(local)<=np.asarray(config['source_half_extents_m'])))
        if 'source_exit' in config:
            from task.atomic.flow import score_source_exit
            mouth = p['source_mouth_crossing'];ma,mb=mouth['before'],mouth['after']
            check('source_mouth_adjacent_samples',type(ma['physics_step']) is int
                  and mb['physics_step']==ma['physics_step']+1 and mb['physics_step']==exit_step)
            check('source_mouth_fixed_dt',ma['dt_s']==mb['dt_s'] and mb['dt_s']==dt1)
            measured=score_source_exit(config['source_exit'],ma,mb)
            check('source_mouth_outward_aperture_crossing',measured['passed'] is True)
            saved=mouth['result']
            check('source_mouth_numerical_witness',saved.keys()==measured.keys() and all(
                np.allclose(saved[k],value,rtol=1e-7,atol=1e-9)
                if isinstance(value,(list,float)) else saved[k]==value
                for k,value in measured.items()))
            if config.get('kind')=='fluid_material_transfer':
                check('source_mouth_exit_position_binding',np.allclose(mb['position'],p['exit_position'],rtol=1e-7,atol=1e-9))
            source=mb['opening_source'];root=np.asarray(source['root_pose'],dtype=float)
            if root.shape!=(7,) or not np.isfinite(root).all():raise ValueError('invalid source mouth root witness')
            model_proof=source.get('model_frame_proof')
            for name,selector,pose in [('mouth',config['source_exit']['opening'],mb['opening']),
                                       ('core',config['source_frame'],current)]:
                if selector['kind']=='model_calibrated_frame':
                    model=model_proof['model'];definition=selector['models'][model]
                    check('source_'+name+'_asset_binding',definition['asset_sha256']==model_proof['asset_sha256']
                          and np.allclose(definition['scaled_bounds_m'],model_proof['scaled_bounds_m'],rtol=0,atol=1e-7))
                    local_pose=np.asarray(definition['local_pose'])
                elif selector['kind']=='object_pose':local_pose=np.asarray([0,0,0,1,0,0,0])
                else:local_pose=np.asarray(selector['local_pose'])
                pose=np.asarray(pose)
                check('source_'+name+'_frame_position_binding',np.allclose(
                    root[:3]+_rotation(root[3:])@local_pose[:3],pose[:3],rtol=1e-7,atol=1e-9))
                check('source_'+name+'_frame_rotation_binding',np.allclose(
                    _rotation(root[3:])@_rotation(local_pose[3:]),_rotation(pose[3:]),rtol=1e-7,atol=1e-9))
    except KeyError as error:
        unavailable.append(str(error))
    except (TypeError,ValueError,IndexError) as error:
        checks['well_formed_crossing_witness']=False;unavailable.append(str(error))
    failed=[name for name,value in checks.items() if not value]
    return {'status':'inconsistent_evidence' if failed else 'partial_evidence' if unavailable else 'consistent_source_evidence',
            'checks':checks,'failed_checks':failed,'unavailable':unavailable,
            'scope':'retained source-cohort, source-exit hold/tilt and adjacent sample witnesses; no unsaved force history or volume claim'}
