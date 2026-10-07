"""Independently verify retained force-bearing finger contact snapshots.

This checks raw identities/impulses and coordinates, not force closure or an
unsaved continuous grasp interval. Missing historical binding fields are partial.
"""
import numpy as np


def validate_contact_witness(source, measurement=None, measured=None):
    failed, unavailable = [], []
    scope = 'retained finger/object force snapshot; not force closure or intermediate persistence'
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
            if not np.isclose(np.linalg.norm(normal),1.,rtol=0,atol=1e-3):failed.append('unit_contact_normal')
            if 'force_report_physics_step' not in row:unavailable.append('raw_force_physics_step')
            elif row['force_report_physics_step']!=step:failed.append('synchronized_force_step')
        if actual_fingers!=set(fingers):failed.append('declared_finger_set')
        if measured is not None:
            origin=source.get('environment_origin_world_m')
            if origin is None:unavailable.append('environment_origin_world_m')
            else:
                origin=np.asarray(origin,dtype=float)
                if origin.shape!=(3,) or not np.isfinite(origin).all():raise ValueError('environment origin')
                points=np.asarray(positions)-origin
                actual=np.asarray(measured['points'],dtype=float)
                centroid=np.asarray(measured['position'],dtype=float)
                if (points.shape!=actual.shape or not np.allclose(points,actual,rtol=0,atol=1e-9)
                        or centroid.shape!=(3,) or not np.allclose(points.mean(axis=0),centroid,rtol=0,atol=1e-9)):
                    failed.append('contact_coordinate_reconstruction')
    except KeyError:
        unavailable.append('incomplete_contact_fields')
    except (ValueError, TypeError, IndexError, AttributeError):
        failed.append('malformed_contact_fields')
    return {'status':'inconsistent_contact_evidence' if failed else
            'partial_contact_evidence' if unavailable else 'consistent_contact_evidence',
            'failed_checks':sorted(set(failed)),'unavailable':sorted(set(unavailable)),'scope':scope}
