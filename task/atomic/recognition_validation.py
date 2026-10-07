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
    checks, invalid, unavailable = {}, set(), []

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
            check('transport_threshold', final['transport_m'] >= config['transport_threshold_m'], names)
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
            'scope': 'retained boundary identities and declared thresholds; intermediate contact/force persistence not reconstructed'}
