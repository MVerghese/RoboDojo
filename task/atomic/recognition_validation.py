"""Validate retained physical boundary identities, independently of recognizers.

Boundary witnesses cannot reconstruct unsaved intermediate contact histories.
These checks identify inconsistent archives, not general recognition accuracy.
"""
import math


WINDOWS = {
    'grip_transfer': ('giver_hold', 'overlap', 'receiver_only'),
    'supported_release': ('release', 'settled'),
    'held_insertion': ('entry', 'inserted'),
    'held_multi_tip_insertion': ('entry', 'inserted'),
    'button_press_cycle': ('press', 'release', 'cycle'),
}


def validate_recognition_window(stage):
    config = stage.get('recognition') or {}
    kind = config.get('kind')
    if kind not in WINDOWS:
        return {'status': 'not_applicable'}
    names = WINDOWS[kind]
    events = stage.get('physical_events', {})
    if not all(name in events for name in names):
        return {'status': 'unobserved', 'reason': 'complete_boundary_events_absent',
                'scope': 'retained boundary identities; intermediate persistence not reconstructed'}
    checks, invalid, unavailable, support_witness = {}, set(), [], None

    def check(name, passed, affected):
        checks[name] = bool(passed)
        if not passed:
            invalid.update(affected)

    def interval(hold):
        arm = hold['resolved_arm']; start = hold['contact_interval_start_step']
        count = hold['consecutive_contact_steps']
        if (not isinstance(arm, str) or not arm or type(start) is not int or start < 0
                or type(count) is not int or count < config['min_contact_steps']):
            raise ValueError('invalid retained hold identity or duration')
        return arm, start

    try:
        steps = [events[name]['physics_step'] for name in names]
        check('boundary_order', all(type(s) is int and s >= 0 for s in steps)
              and all(a <= b for a,b in zip(steps,steps[1:])), names)
        epochs = [events[name].get('attempt_index') for name in names]
        if any(e is not None for e in epochs):
            check('attempt_identity', all(type(e) is int and e >= 0 for e in epochs)
                  and len(set(epochs)) == 1, names)
        final = events[names[-1]]
        if kind == 'grip_transfer':
            giver = interval(final['giver_contact']); receiver = interval(final['receiver_contact'])
            check('giver_arm_binding', giver[0] == config['giver_arm'], names)
            check('receiver_arm_binding', receiver[0] == config['receiver_arm'], names)
            check('initial_giver_interval', interval(events['giver_hold']['contact']) == giver, ['giver_hold'])
            check('overlap_giver_interval', interval(events['overlap']['giver_contact']) == giver, ['overlap'])
            check('overlap_receiver_interval', interval(events['overlap']['receiver_contact']) == receiver, ['overlap'])
            check('receiver_retained_since_overlap', receiver[1] <= events['overlap']['physics_step'], ['overlap'])
            check('retention_thresholds', final['overlap_steps'] >= config['overlap_steps']
                  and final['receiver_only_steps'] >= config['receiver_steps'], [names[-1]])
        elif kind == 'supported_release':
            check('release_transport_interval', interval(events['release']['held_contact'])
                  == interval(final['held_contact']), ['release'])
            check('settling_threshold', final['stable_steps'] >= config['settle_steps'], ['settled'])
            check('release_precedes_transport_completion',
                  final['held_contact']['contact_interval_start_step'] <= events['release']['physics_step'], ['release'])
            values = [final['transport_m'], final['settle_displacement_m'], final['settle_angle_rad']]
            check('finite_completed_metrics', all(type(v) in (int,float) and math.isfinite(v) for v in values), names)
            check('nonnegative_completed_metrics', all(v >= 0 for v in values), names)
            check('transport_threshold', final['transport_m'] >= config['transport_threshold_m'], names)
            check('settling_displacement_bound', final['settle_displacement_m'] <= config['max_settle_displacement_m'], ['settled'])
            check('settling_angle_bound', final['settle_angle_rad'] <= config['max_settle_angle_rad'], ['settled'])
            support = final.get('support')
            if (not isinstance(support, dict) or not all(k in support for k in
                    ('object', 'object_root', 'support_roots', 'normal_axis_world', 'contacts'))):
                unavailable.append('settled: raw named-support evidence absent')
            else:
                from task.atomic.support_validation import validate_support_witness
                support_witness = validate_support_witness({'support_contact': True,
                                                            'support_contact_evidence': support})
                check('settled_support_force_signs', support_witness['status'] != 'inconsistent_support_evidence', ['settled'])
                if support_witness['status'] == 'partial_support_evidence':
                    unavailable.extend('settled support: ' + reason for reason in support_witness['unavailable'])
                if 'label' not in config or 'support_labels' not in config:
                    unavailable.append('settled: declared object/support binding absent')
                else:
                    check('settled_support_binding', support['object'] == config['label']
                          and bool(support['contacts']) and all(row['support_label'] in config['support_labels']
                                                               for row in support['contacts']), ['settled'])
            if 'separated_steps' not in final:
                unavailable.append('settled: separation interval absent')
            else:
                count, start = final['separated_steps'], final['separated_since_step']
                check('settled_separation_interval', type(count) is int and type(start) is int
                      and count >= final['stable_steps'] >= config['settle_steps']
                      and start + count - 1 == final['physics_step']
                      and start >= events['release']['physics_step'], ['settled'])
                check('settled_robot_separated', final.get('robot_touching') is False, ['settled'])
                recontacts = final.get('post_release_recontacts', {})
                if recontacts:
                    check('recontact_precedes_settling_separation',
                          events['release']['physics_step'] < recontacts['last_physics_step'] < start,
                          ['settled'])
                    contact = recontacts['last_contact']
                    fingers = contact['finger_bodies']
                    check('recontact_is_single_finger', isinstance(fingers,list) and len(set(fingers)) == 1
                          and contact['physics_step'] == recontacts['last_physics_step']
                          and type(recontacts['sampled_steps']) is int and recontacts['sampled_steps'] > 0,
                          ['settled'])
        elif kind == 'button_press_cycle':
            press,release=events['press'],events['release']
            check('press_contact_interval',interval(press['moving_link_contact']) == interval(final['press_contact']),['press'])
            check('initial_unpressed_ratio',math.isfinite(final['initial_ratio'])
                  and final['initial_ratio'] > config['initial_ratio'],names)
            check('pressed_ratio',math.isfinite(press['joint_ratio'])
                  and press['joint_ratio'] < config['pressed_ratio']
                  and press['joint_ratio'] == final['pressed_ratio'],['press'])
            check('released_ratio',math.isfinite(release['joint_ratio'])
                  and release['joint_ratio'] > config['released_ratio']
                  and release['joint_ratio'] == final['released_ratio'],['release','cycle'])
            check('moving_body_identity',press['moving_body'] == release['moving_body'] == final['moving_body'],names)
            for name in names:
                event=events[name];joint=event.get('joint_state')
                if joint is None:
                    unavailable.append(name+': raw joint state absent')
                else:
                    values=[joint[k] for k in ('position','lower','upper')]
                    valid=all(type(v) in (int,float) and math.isfinite(v) for v in values) and joint['upper'] > joint['lower']
                    ratio=event['released_ratio'] if name=='cycle' else event['joint_ratio']
                    check(name+'_raw_joint_ratio',valid and math.isclose(
                        (joint['position']-joint['lower'])/(joint['upper']-joint['lower']),ratio,
                        rel_tol=1e-9,abs_tol=1e-9),[name])
            for name in ('release','cycle'):
                if 'robot_touching' not in events[name]:unavailable.append(name+': separation observation absent')
                else:check(name+'_robot_separated',events[name]['robot_touching'] is False,[name])
            initial=press.get('initial_unpressed_sample');arming=press.get('arming_contact')
            if initial is None or arming is None:
                unavailable.append('initial unpressed/arming state absent')
            else:
                sample_step=initial['physics_step'];arm_step=arming['physics_step']
                count=arming['consecutive_contact_steps'];start=arming['contact_interval_start_step']
                check('arming_within_pressed_hold',type(count) is int and count >= 1
                    and type(start) is int and type(arm_step) is int
                    and start+count-1==arm_step
                    and (arming['resolved_arm'],start) == interval(final['press_contact']),names)
                check('requested_arm',config['arm']=='any' or arming['resolved_arm']==config['arm'],names)
                check('unpressed_sample_time',type(sample_step) is int and type(arm_step) is int
                    and 0 <= sample_step <= arm_step <= press['physics_step']
                    and arm_step-sample_step in (0,1),names)
                check('preceding_sample_uncontacted',sample_step==arm_step or initial['robot_touching'] is False,names)
                check('initial_sample_identity',initial==final['initial_unpressed_sample']
                    and initial['moving_body']==final['moving_body']
                    and initial['joint_ratio']==final['initial_ratio'],names)
                joint=initial['joint_state']
                values=[joint[k] for k in ('position','lower','upper')]
                valid=all(type(v) in (int,float) and math.isfinite(v) for v in values) and joint['upper'] > joint['lower']
                check('initial_raw_joint_ratio',valid and math.isclose(
                    (joint['position']-joint['lower'])/(joint['upper']-joint['lower']),initial['joint_ratio'],
                    rel_tol=1e-9,abs_tol=1e-9),names)
        else:
            arm,start = interval(final['held_contact'])
            check('entry_during_completed_hold', start <= events['entry']['physics_step'], ['entry'])
            check('requested_arm', config['arm'] == 'any' or arm == config['arm'], names)
    except (KeyError, TypeError, ValueError, IndexError) as error:
        unavailable.append(f'{type(error).__name__}: {error}')
    failed = [name for name,passed in checks.items() if not passed]
    return {'status': 'inconsistent_evidence' if failed else 'partial_evidence' if unavailable else 'consistent_boundary_evidence',
            'checks': checks, 'failed_checks': failed, 'invalid_event_names': sorted(invalid),
            'unavailable': unavailable,
            'settled_support_witness': support_witness,
            'scope': 'retained boundary identities and declared thresholds; intermediate contact/force persistence not reconstructed'}
