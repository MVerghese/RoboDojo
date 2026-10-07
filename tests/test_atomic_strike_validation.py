"""Reject tampered/gapped physical witnesses without trusting summary flags."""
import unittest

from scripts.atomic.validate_strike_evidence import validate_strike
from scripts.atomic.audit_scores import apply_recognition_validation


def retained_strike():
    tool = {'kind': 'functional_point', 'label': 'mallet', 'tag': 'beat', 'type': 'active'}
    target = {'kind': 'functional_point', 'label': 'keys', 'tag': 'hit_0', 'type': 'passive'}
    frame = [0, 0, 0, 1, 0, 0, 0]

    def hold(step):
        return {'resolved_arm': 'left', 'finger_bodies': ['f0', 'f1'],
            'consecutive_contact_steps': step-98+1, 'contact_interval_start_step': 98,
            'contacts': [{'finger_body': f, 'arm': 'left', 'force_report_physics_step': step,
                'impulse': [0, 0, .01]} for f in ('f0', 'f1')]}

    impact = {'name': 'impact', 'physics_step': 101, 'held_contact': hold(101),
        'approach_samples': [{'physics_step': n, 'dt_s': .01,
            'tool_pose': [0, 0, z, 1, 0, 0, 0], 'target_pose': frame,
            'relative_position': [0, 0, z]} for n, z in ((99, .02), (100, .01))],
        'relative_velocity_m_s': [0, 0, -1], 'toward_surface_speed_m_s': 1.,
        'contact_points': [[0, 0, 0]], 'tool_landmark_position': [0, 0, 0],
        'target_landmark_position': [0, 0, 0], 'tool_landmark_distances_m': [0],
        'target_landmark_distances_m': [0], 'total_impulse_ns': .01,
        'tool_target_contacts': [{'impulse': [0, 0, .01], 'normal_world': [0, 0, 1],
            'force_report_physics_step': 101}]}
    final = {'name': 'strike', 'physics_step': 105, 'held_contact': hold(105),
        'rise_m': .03, 'separated_steps': 2, 'elapsed_physics_steps': 4}
    return {'recognition': {'kind': 'held_tool_strike', 'min_contact_steps': 2,
        'max_retraction_steps': 10, 'min_retraction_steps': 2, 'min_retraction_m': .025,
        'min_approach_speed_m_s': .1, 'tool_radius_m': .04, 'target_radius_m': .04,
        'min_impulse_ns': .005, 'tool_point': tool, 'target_point': target},
        'physical_events': {'impact': impact, 'strike': final, 'retracted': {
            'name': 'retracted', 'physics_step': 105, 'rise_m': .03, 'separated_steps': 2}},
        'trajectories': {'path': {'condition': {'measurement': tool, 'reference': target,
            'start_event': {'kind': 'recognition_event', 'name': 'impact'},
            'end_event': {'kind': 'recognition_event', 'name': 'strike'}},
            'complete': True, 'failures': [], 'samples': [{'physics_step': n, 'dt_s': .01,
                'measured_state': [0, 0, .03*(n-101)/4, 1, 0, 0, 0],
                'reference_state': frame} for n in range(101, 106)]}}}


class StrikeValidationTests(unittest.TestCase):
    def test_incompatible_cached_window_is_excluded_but_numerical_result_is_retained(self):
        stage=retained_strike()
        stage['conditions']=[{'id':'contact','event':{'kind':'recognition_event','name':'impact'}},
                             {'id':'final','event':{'kind':'attempt_end'}}]
        stage['physical_events']['strike']['elapsed_physics_steps']=2
        score={'conditions':{'contact':{'status':'reproduced','recorded_result':{'error':.003}},
                             'final':{'status':'reproduced'}},
               'trajectories':{'path':{'status':'reproduced'}}}
        apply_recognition_validation(stage,score)
        self.assertEqual(score['conditions']['contact']['status'],'invalid_recognition_window')
        self.assertEqual(score['conditions']['contact']['numerical_reproduction_status'],'reproduced')
        self.assertEqual(score['conditions']['contact']['recorded_result']['error'],.003)
        self.assertEqual(score['conditions']['final']['status'],'reproduced')
        self.assertEqual(score['trajectories']['path']['status'],'invalid_recognition_window')
        self.assertIn('elapsed_steps',score['recognition_witness']['failed_checks'])

    def test_valid_witness_reconstructs_speed_and_retraction(self):
        result = validate_strike(retained_strike())
        self.assertEqual(result['status'], 'consistent_evidence')
        self.assertAlmostEqual(result['metrics']['approach_speed_m_s'], 1.)
        self.assertAlmostEqual(result['metrics']['retraction_m'], .03)

    def test_changed_velocity_contact_interval_and_pose_fail(self):
        for change, failed in (
            (lambda s: s['physical_events']['impact'].__setitem__('toward_surface_speed_m_s', 5.), 'approach_speed'),
            (lambda s: s['physical_events']['impact']['approach_samples'][0].__setitem__('physics_step', 97), 'contiguous_preimpact_samples'),
            (lambda s: s['physical_events']['strike']['held_contact'].__setitem__('contact_interval_start_step', 104), 'same_arm_hold_interval'),
            (lambda s: s['trajectories']['path']['samples'][-1]['measured_state'].__setitem__(2, .005), 'retraction_rise_from_raw_poses'),
            (lambda s: s['trajectories']['path']['samples'].pop(2), 'contiguous_retraction_samples'),
        ):
            with self.subTest(failed=failed):
                stage = retained_strike(); change(stage)
                result = validate_strike(stage)
                self.assertEqual(result['status'], 'inconsistent_evidence')
                self.assertIn(failed, result['failed_checks'])

    def test_absent_poses_and_events_are_not_invented(self):
        stage = retained_strike(); stage['trajectories'] = {}
        self.assertEqual(validate_strike(stage)['status'], 'partial_evidence')
        stage['physical_events'].pop('strike')
        self.assertEqual(validate_strike(stage)['status'], 'unobserved')
        self.assertEqual(validate_strike({'recognition': None})['status'], 'not_applicable')


if __name__ == '__main__':
    unittest.main()
