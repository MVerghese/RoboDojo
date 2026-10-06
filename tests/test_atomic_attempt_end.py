"""Final-state scores remain available for unsuccessful and earlier-completed actions."""
from copy import deepcopy
import unittest
from dataclasses import replace

from task.atomic.session import AtomicSession
from task.atomic.sequence import AtomicSequence
from task.atomic.spec import AtomicProgram, AtomicStage
from test_atomic_physical_runtime import World, stage


def definition():
    original = stage('supported_release')
    condition = {'id': 'end_goal', 'slot': 'goal', 'kind': 'point',
                 'measurement': {'kind': 'object_position', 'label': 'object'},
                 'expected': [.1, 0, 0], 'tolerance': .001,
                 'event': {'kind': 'attempt_end'}, 'track_closest': False}
    return replace(original, geometry=(condition,))


class AttemptEndTests(unittest.TestCase):
    def test_failed_action_has_continuous_error_without_fabricated_interaction(self):
        w = World(); s = AtomicSession(w.env, definition(), 0)
        w.tick(s, 3)
        self.assertFalse(s.success)
        self.assertFalse(s.results)
        s.finalize()
        self.assertFalse(s.success)
        self.assertAlmostEqual(s.results['end_goal']['result']['components']['position_m'], .1)
        self.assertFalse(s.summary()['interaction_observed'])
        snapshot = deepcopy(s.summary())
        w.poses['object'][0] = .1
        s.finalize()
        self.assertEqual(s.summary(), snapshot)

    def test_completed_stage_endpoint_is_episode_end_and_unstarted_stage_stays_missing(self):
        w = World()
        first = definition()
        later = replace(first, id='unstarted', success_checks=({'name': 'never', 'args': {}},))
        p = AtomicProgram('t', (first, later), stage_dependencies={first.id: [], 'unstarted': [first.id]})
        blocked = AtomicSequence(World().env, p, 0)
        blocked.finalize()
        missing = next(r for r in blocked.summary()['stages'] if r['stage_id'] == 'unstarted')
        self.assertFalse(missing['reached'])
        self.assertEqual(missing['geometry'], {})
        seq = AtomicSequence(w.env, p, 0)
        w.hold()
        for _ in range(2): w.contacts.steps += 1; seq.observe_events()
        w.poses['object'][0] = .02; w.contacts.steps += 1; seq.observe_events()
        w.release()
        for _ in range(3): w.contacts.steps += 1; seq.observe_events()
        self.assertIn(first.id, seq.completed)
        w.poses['object'][0] = .07
        seq.finalize()
        rows = {r['stage_id']: r for r in seq.summary()['stages']}
        self.assertTrue(rows[first.id]['action_success'])
        self.assertAlmostEqual(rows[first.id]['geometry']['end_goal']['result']['components']['position_m'], .03)
        self.assertEqual(rows[first.id]['end_boundary']['physics_step'], 6)

    def test_terminal_sample_cannot_rescue_an_unobserved_lift_event(self):
        w = World(); first = definition()
        lift = deepcopy(first.geometry[0]); lift.update(id='lift_goal', event={'kind':'first_lift','label':'object','threshold':.025})
        s = AtomicSession(w.env, replace(first, geometry=first.geometry + (lift,)), 0)
        w.tick(s)
        w.poses['object'][2] = .1
        s.finalize()
        self.assertNotIn('lift_goal', s.results)

    def test_final_contact_is_rejected_as_a_past_interaction_proxy(self):
        s = definition()
        raw = {'id': s.id, 'family': s.family, 'instruction': s.instruction,
               'recognition': s.recognition, 'success_checks': list(s.success_checks),
               'geometry': [dict(s.geometry[0], measurement={'kind':'contact_points','label':'object'})]}
        with self.assertRaisesRegex(ValueError, 'final state'):
            AtomicStage.from_dict(raw)


if __name__ == '__main__': unittest.main()
