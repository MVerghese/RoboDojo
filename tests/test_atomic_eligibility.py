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

    def test_insertion_reports_alignment_and_contact_without_certifying_insertion(self):
        w=World();s=AtomicSession(w.env,stage('held_insertion'),0)
        w.poses['object'][0]=.02;w.poses['object'][2]=-.01;w.tick(s)
        row=s.summary()['physical_metrics']['eligibility']['current']
        self.assertFalse(row['gates']['lateral_alignment'])
        self.assertFalse(row['gates']['target_contact'])
        self.assertTrue(row['gates']['insertion_depth'])
        self.assertAlmostEqual(row['measurements']['lateral_error_m'],.02)
        self.assertFalse(s.success)

    def test_release_diagnostics_preserve_gradual_jaw_release_and_settling_gates(self):
        w=World();s=AtomicSession(w.env,stage('supported_release'),0)
        w.hold();w.tick(s,2);w.poses['object'][0]=.03;w.tick(s)
        w.hold(fingers=1);w.tick(s)
        row=s.summary()['physical_metrics']['eligibility']['current']
        self.assertTrue(row['gates']['transported_while_held'])
        self.assertFalse(row['gates']['robot_separated'])
        w.release();w.tick(s)
        self.assertFalse(s.summary()['physical_metrics']['eligibility']['current']['gates']['settling_interval_long_enough'])
        self.assertTrue(w.tick(s,2))
        self.assertTrue(s.summary()['physical_metrics']['eligibility']['current']['gates']['settling_interval_long_enough'])

    def test_strike_completion_does_not_reuse_stale_hold_as_a_current_observation(self):
        from test_atomic_paths_selection import strike_world,strike_stage,impact
        w=strike_world();w.goal=False;s=AtomicSession(w.env,strike_stage(),0)
        impact(w,s);w.contacts.pairs=False;w.poses['object'][2]=.04;w.tick(s,2)
        w.release();w.tick(s)
        row=s.summary()['physical_metrics']['eligibility']['current']
        self.assertIsNone(row['gates']['sustained_hold'])
        self.assertIsNone(row['gates']['tool_target_contact'])
        self.assertTrue(row['gates']['retracted'])

    def test_pick_and_push_diagnostics_distinguish_absent_contact_from_absent_support(self):
        from test_atomic_recognition import environment,config
        from task.atomic.spec import AtomicStage
        for family in ('pick','push'):
            env,pose,contacts=environment();s=AtomicSession(env,AtomicStage.from_dict(config(family=family)),0)
            contacts.steps=1;s.observe_events()
            row=s.summary()['physical_metrics']['eligibility']['current']
            self.assertFalse(row['gates']['finger_contact'])
            self.assertIsNone(row['gates']['contact_coupled_motion'])
            contacts.present=True;contacts.steps=2;s.observe_events()
            contacts.steps=3;pose[0 if family=='push' else 2]=.03;s.observe_events()
            row=s.summary()['physical_metrics']['eligibility']['current']
            self.assertTrue(row['gates']['contact_coupled_motion'])
            if family=='pick':self.assertFalse(row['gates']['required_held_lift'])
            else:
                contacts.support=False;contacts.steps=4;s.observe_events()
                row=s.summary()['physical_metrics']['eligibility']['current']
                self.assertTrue(row['gates']['finger_contact'])
                self.assertFalse(row['gates']['support_contact'])
                self.assertIsNone(row['measurements']['displacement_m'])


if __name__ == '__main__':
    unittest.main()
