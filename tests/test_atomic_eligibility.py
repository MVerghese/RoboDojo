"""Missing physical prerequisites remain distinct from unmeasured geometry."""
import unittest

from test_atomic_physical_runtime import World, stage
from task.atomic.session import AtomicSession


class EligibilityTests(unittest.TestCase):
    def test_push_identifies_contact_support_and_motion_without_borrowing_history(self):
        w = World(); s = AtomicSession(w.env, stage('held_tool_push'), 0)
        w.contacts.pairs = True; w.tick(s)
        d = s.summary()['physical_metrics']['eligibility']
        self.assertFalse(d['current']['gates']['two_finger_contact'])
        self.assertTrue(d['current']['gates']['tool_target_contact'])
        self.assertIsNone(d['current']['gates']['target_planar_motion'])
        w.hold(); w.contacts.pairs = False; w.tick(s, 2)
        self.assertTrue(s.summary()['physical_metrics']['eligibility']['current']['gates']['sustained_hold'])
        w.contacts.pairs = True; w.contacts.support = False; w.tick(s)
        self.assertFalse(s.summary()['physical_metrics']['eligibility']['current']['gates']['target_support_contact'])
        w.contacts.support = True; w.tick(s, 2)
        gates = s.summary()['physical_metrics']['eligibility']['current']['gates']
        self.assertTrue(gates['contact_interval_long_enough'])
        self.assertFalse(gates['target_planar_motion'])
        w.poses['object'][0] = .03; w.poses['target'][0] = .03
        self.assertTrue(w.tick(s))
        d = s.summary()['physical_metrics']['eligibility']
        self.assertTrue(all(d['current']['gates'].values()))
        self.assertAlmostEqual(d['current']['measurements']['target_planar_displacement_m'], .03)
        self.assertEqual(d['gate_counts']['target_support_contact']['false'], 1)

    def test_counters_deduplicate_observation_and_mark_sampling_gaps(self):
        w = World(); s = AtomicSession(w.env, stage('held_tool_push'), 0)
        w.tick(s); s.observe_events(); s.step()
        d = s.summary()['physical_metrics']['eligibility']
        self.assertEqual(d['sampled_steps'], 1)
        w.contacts.steps += 3; w.tick(s)
        d = s.summary()['physical_metrics']['eligibility']
        self.assertEqual(d['sampled_steps'], 2)
        self.assertEqual(d['sampling_discontinuities'], 1)
        for counts in d['gate_counts'].values():
            self.assertEqual(sum(counts.values()), 2)

    def test_touch_distinguishes_wrong_parts_resting_contact_and_low_impulse(self):
        w = World(); s = AtomicSession(w.env, stage('held_tool_contact'), 0)
        w.hold(); w.tick(s, 2)
        w.contacts.pairs = True; w.contacts.target_suffix = 'key1'; w.tick(s)
        gates = s.summary()['physical_metrics']['eligibility']['current']['gates']
        self.assertTrue(gates['new_encounter']); self.assertFalse(gates['declared_parts_contact'])
        w.contacts.target_suffix = 'key0'; w.tick(s)
        gates = s.summary()['physical_metrics']['eligibility']['current']['gates']
        self.assertFalse(gates['new_encounter']); self.assertTrue(gates['declared_parts_contact'])
        self.assertFalse(s.success)
        w.contacts.pairs = False; w.tick(s)
        w.contacts.pairs = True; w.contacts.impulse = .0001; w.tick(s)
        self.assertFalse(s.summary()['physical_metrics']['eligibility']['current']['gates']['minimum_impulse'])
        self.assertFalse(s.success)

    def test_joint_motion_reports_live_motion_only_inside_contact_interval(self):
        w = World(); s = AtomicSession(w.env, stage('contact_joint_motion'), 0)
        w.joint = -.1; w.tick(s)
        d = s.summary()['physical_metrics']['eligibility']['current']
        self.assertIsNone(d['measurements']['signed_travel'])
        self.assertFalse(d['gates']['moving_link_contact'])
        w.hold(fingers=1); w.tick(s, 2)
        d = s.summary()['physical_metrics']['eligibility']['current']
        self.assertEqual(d['measurements']['signed_travel'], 0.)
        self.assertFalse(d['gates']['minimum_travel'])
        w.joint -= .006; self.assertTrue(w.tick(s))
        self.assertAlmostEqual(s.summary()['physical_metrics']['eligibility']['current']['measurements']['signed_travel'], .006)


if __name__ == '__main__':
    unittest.main()
