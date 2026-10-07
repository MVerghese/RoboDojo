"""Independently verify retained force-bearing finger contact snapshots.

This checks raw identities/impulses and coordinates, not force closure or an
unsaved continuous grasp interval. Missing historical binding fields are partial.
"""
import numpy as np


def _result(failed, unavailable, scope):
    return {'status':'inconsistent_contact_evidence' if failed else
            'partial_contact_evidence' if unavailable else 'consistent_contact_evidence',
            'failed_checks':sorted(set(failed)),'unavailable':sorted(set(unavailable)),'scope':scope}


def _coordinates(source, measured, positions, failed, unavailable):
    if measured is None:return
    origin=source.get('environment_origin_world_m')
    if origin is None:unavailable.append('environment_origin_world_m');return
    origin=np.asarray(origin,dtype=float)
    if origin.shape!=(3,) or not np.isfinite(origin).all():raise ValueError('environment origin')
    points=np.asarray(positions)-origin
    actual=np.asarray(measured['points'],dtype=float);centroid=np.asarray(measured['position'],dtype=float)
    if (points.shape!=actual.shape or not np.allclose(points,actual,rtol=0,atol=1e-9)
            or centroid.shape!=(3,) or not np.allclose(points.mean(axis=0),centroid,rtol=0,atol=1e-9)):
        failed.append('contact_coordinate_reconstruction')


def _object_pair(source, measurement, measured):
    failed,unavailable=[],[];scope='retained named object-pair force snapshot; not held tool or active-part identity'
    try:
        roots=source['object_roots'];rows=source['contacts'];step=source['physics_step'];positions=[]
        if (not isinstance(roots,list) or len(roots)!=2 or roots[0]==roots[1]
                or any(not isinstance(r,str) or not r.startswith('/') for r in roots)
                or type(step) is not int or step<0):raise ValueError('object pair')
        if not rows:failed.append('force_contacts_absent')
        if measurement and any(source.get(k)!=measurement.get(k) for k in ('label','other_label')):
            failed.append('requested_object_pair')
        if 'force_eligibility' not in source:unavailable.append('recorded_impulse_threshold')
        elif source['force_eligibility']!={'min_impulse_norm_ns':1e-9}:failed.append('impulse_threshold')
        def inside(row,index,root):
            return any(p==root or p.startswith(root+'/') for p in (row[f'actor{index}'],row[f'collider{index}']))
        for row in rows:
            if not ((inside(row,0,roots[0]) and inside(row,1,roots[1])) or
                    (inside(row,1,roots[0]) and inside(row,0,roots[1]))):failed.append('named_object_pair')
            position,normal,impulse=[np.asarray(row[k],dtype=float) for k in ('position_world','normal_world','impulse')]
            if any(v.shape!=(3,) or not np.isfinite(v).all() for v in (position,normal,impulse)):
                failed.append('finite_contact_vectors');continue
            positions.append(position)
            if np.linalg.norm(impulse)<=1e-9:failed.append('force_bearing_impulse')
            if not np.isclose(np.linalg.norm(normal),1.,rtol=1e-5,atol=1e-3):failed.append('unit_contact_normal')
            if 'force_report_physics_step' not in row:unavailable.append('raw_force_physics_step')
            elif row['force_report_physics_step']!=step:failed.append('synchronized_force_step')
        _coordinates(source,measured,positions,failed,unavailable)
    except KeyError:unavailable.append('incomplete_contact_fields')
    except (ValueError,TypeError,IndexError,AttributeError):failed.append('malformed_contact_fields')
    return _result(failed,unavailable,scope)


def _oriented_contact(source, measurement, measured):
    underlying=source.get('contact_source');result=validate_contact_witness(underlying,measurement,measured)
    failed=list(result.get('failed_checks',[]));unavailable=list(result.get('unavailable',[]))
    try:
        frame=source['orientation_frame_source'];pose=np.asarray(source['orientation_frame_pose'],dtype=float)
        if pose.shape!=(7,) or not np.isfinite(pose).all():raise ValueError('physical frame pose')
        from task.atomic.geometry import _quaternion
        q=_quaternion(pose[3:])
        step=source['physics_step']
        if type(step) is not int or frame['physics_step']!=step or underlying['physics_step']!=step:
            failed.append('synchronized_orientation_frame')
        if frame.get('frame')!='environment_local_world':failed.append('orientation_coordinate_frame')
        if source['kind']=='contact_pose':
            if (frame.get('kind')!='robot_ee_pose' or frame.get('resolved_arm')!=underlying['resolved_arm']
                    or not frame.get('ee_link_name')):failed.append('contacting_arm_frame')
        elif frame.get('label')!=underlying['label'] or frame.get('kind') not in (
                'object_pose','functional_point','calibrated_frame','model_calibrated_frame'):
            failed.append('contacting_object_frame')
        if measurement and source.get('orientation_frame')!=measurement.get('orientation_frame'):
            failed.append('requested_orientation_frame')
        if measured is not None:
            actual=_quaternion(measured['orientation'])
            if measured.get('oriented_contact_frame') is not True or not np.isclose(abs(q@actual),1.,rtol=0,atol=1e-9):
                failed.append('orientation_reconstruction')
    except KeyError:unavailable.append('incomplete_orientation_frame_fields')
    except (ValueError,TypeError,IndexError,AttributeError):failed.append('malformed_orientation_frame')
    return _result(failed,unavailable,'retained contact positions and named same-step physical-frame axes; not surface normals or force closure')


def validate_contact_witness(source, measurement=None, measured=None):
    failed, unavailable = [], []
    scope = 'retained finger/object force snapshot; not force closure or intermediate persistence'
    if isinstance(source,dict) and source.get('kind') in ('contact_pose','object_contact_pose'):
        return _oriented_contact(source,measurement,measured)
    if isinstance(source,dict) and source.get('kind')=='object_contact_points':
        return _object_pair(source,measurement,measured)
    if not isinstance(source, dict) or source.get('kind') != 'contact_points':
        return {'status':'partial_contact_evidence','unavailable':['raw_contact_source'],'scope':scope}
    try:
        rows, fingers, arm = source['contacts'], source['finger_bodies'], source['resolved_arm']
        count, step = source['min_finger_bodies'], source['physics_step']
        if (not isinstance(rows,list) or not isinstance(fingers,list) or not isinstance(arm,str)
                or not arm or type(count) is not int or count < 1 or type(step) is not int or step < 0):
            raise ValueError('contact declaration')
        if not rows:failed.append('force_contacts_absent')
        if len(set(fingers)) < count or len(set(fingers)) != len(fingers):failed.append('distinct_fingers')
        if source.get('arm','any') not in ('any','nearest',arm):failed.append('requested_arm')
        if measurement:
            if source.get('label') != measurement.get('label'):failed.append('requested_object_label')
            requested = measurement.get('min_finger_bodies',1)
            if len(set(fingers)) < requested:failed.append('requested_finger_count')
            if measurement.get('arm','any') not in ('any','nearest',arm):failed.append('measurement_arm')
        root, contact_scope = source.get('object_root'), source.get('object_contact_scope')
        if root is None or contact_scope is None:unavailable.append('object_root_and_contact_scope')
        elif (not isinstance(root,str) or not root.startswith('/') or not isinstance(contact_scope,str)
              or not (contact_scope == root or contact_scope.startswith(root+'/'))):
            failed.append('object_scope_binding')
        elif source.get('body_path') and source['body_path'] != contact_scope:
            failed.append('moving_body_binding')
        bindings, env_index = source.get('finger_body_bindings'), source.get('environment_index')
        if bindings is None or env_index is None:unavailable.append('finger_environment_bindings')
        elif type(env_index) is not int or env_index < 0 or not isinstance(bindings,dict):
            failed.append('environment_binding')
        eligibility=source.get('force_eligibility')
        if eligibility is None:unavailable.append('recorded_impulse_threshold')
        elif eligibility != {'min_impulse_norm_ns':1e-9}:failed.append('impulse_threshold')
        actual_fingers, positions = set(), []
        for row in rows:
            finger=row['finger_body'];actual_fingers.add(finger)
            indices=[i for i in (0,1) if row[f'actor{i}']==finger]
            if len(indices)!=1:failed.append('finger_actor_identity');continue
            if row['arm']!=arm:failed.append('same_arm_contacts')
            if bindings is not None and bindings.get(finger)!=[env_index,arm]:failed.append('finger_environment_binding')
            if contact_scope is not None:
                other=1-indices[0]
                if not any(p==contact_scope or p.startswith(contact_scope+'/') for p in
                           (row[f'actor{other}'],row[f'collider{other}'])):
                    failed.append('named_object_contact')
            values=[np.asarray(row[k],dtype=float) for k in ('position_world','normal_world','impulse')]
            if any(v.shape!=(3,) or not np.isfinite(v).all() for v in values):
                failed.append('finite_contact_vectors');continue
            position,normal,impulse=values;positions.append(position)
            if np.linalg.norm(impulse)<=1e-9:failed.append('force_bearing_impulse')
            if not np.isclose(np.linalg.norm(normal),1.,rtol=1e-5,atol=1e-3):failed.append('unit_contact_normal')
            if 'force_report_physics_step' not in row:unavailable.append('raw_force_physics_step')
            elif row['force_report_physics_step']!=step:failed.append('synchronized_force_step')
        if actual_fingers!=set(fingers):failed.append('declared_finger_set')
        _coordinates(source,measured,positions,failed,unavailable)
    except KeyError:
        unavailable.append('incomplete_contact_fields')
    except (ValueError, TypeError, IndexError, AttributeError):
        failed.append('malformed_contact_fields')
    return _result(failed,unavailable,scope)
