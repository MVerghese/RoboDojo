"""Unit separation, shared-event comparisons and missing evidence in reports."""
from copy import deepcopy
import math
import unittest

from scripts.atomic.continuous_report import (
    arm_summary, component_names, condition_parameters, measurement_row, report_html, report_markdown,
    shared_summary,
    collect_events, component_unit,
)


def event(components=None, status='reproduced'):
    score = {'status': status, 'kind': 'relative_displacement', 'slot': 'grasp_region'}
    if components is not None:
        # The report must use physical components, not this composite error.
        score['recorded_result'] = {'components': components, 'error': 999, 'tolerance': 1}
    return {'family': 'pick', 'score': score}


class ContinuousReportTests(unittest.TestCase):
    def test_flow_path_and_selected_referent_keep_units_and_exclude_unscored_crossing(self):
        rows={'atomic_scores':[{'stage_id':'s','family':'pour','conditions':{},
            'material_flow':{'crossings':{
                '0':{'status':'reproduced','recorded_result':{'status':'scored','components':{
                    'crossing_position_error_m':.004,'velocity_angle_rad':.2,'relative_speed_m_s':.3}}},
                '1':{'status':'reproduced','recorded_result':{'status':'opening_rotation_sampling_limit'}}}},
            'trajectories':{'p':{'status':'reproduced','condition':{'slot':'path'},
                'recorded_result':{'status':'scored','max_deviation_m':.006,'duration_s':1.5}}},
            'selection':{'status':'reproduced','target_status':'resolved',
                'observed':{'contacts':[{'label':'wrong'}]},'candidates':{
                    'right':{'c':{'status':'reproduced','recorded_result':{'components':{'position_m':0}}}},
                    'wrong':{'c':{'status':'reproduced','recorded_result':{'components':{'position_m':.1}}}}}}}]}
        events=collect_events(rows); summary=arm_summary(events.values())
        self.assertEqual(summary['observed'],3)
        self.assertEqual(summary['components']['position_m']['mean'],.1)
        self.assertEqual(summary['components']['duration_s']['mean'],1.5)
        self.assertEqual(component_unit('relative_speed_m_s'),('relative speed (mm/s)',1000))
        self.assertEqual(component_unit('duration_s'),('duration (s)',1))

    def test_delta_compares_shared_events_not_different_observed_populations(self):
        a = {('a', 'c'): event({'displacement_m': .001}),
             ('b', 'c'): event({'displacement_m': .009}),
             ('c', 'c'): event(status='event_not_observed')}
        b = {('a', 'c'): event({'displacement_m': .002}),
             ('b', 'c'): event(status='event_not_observed'),
             ('c', 'c'): event({'displacement_m': .030})}
        self.assertAlmostEqual(arm_summary(a.values())['components']['displacement_m']['mean'], .005)
        self.assertAlmostEqual(arm_summary(b.values())['components']['displacement_m']['mean'], .016)
        shared = shared_summary(a, b, True)
        self.assertEqual(shared['n_events'], 1)
        self.assertAlmostEqual(shared['components']['displacement_m']['delta']['mean'], .001)
        self.assertEqual(shared_summary(a, b, False)['components'], {})

    def test_pose_reports_translation_mm_and_rotation_degrees_separately(self):
        a = {('s', 'c'): event({'position_m': .001, 'orientation_rad': math.pi / 2})}
        b = {('s', 'c'): event({'position_m': .003, 'orientation_rad': math.pi / 3})}
        c = {'kind': 'pose', 'family': 'push', 'condition_id': 'goal',
             'baseline': arm_summary(a.values()), 'conditioned': arm_summary(b.values()),
             'shared': shared_summary(a, b, True)}
        self.assertEqual(component_names(c), ['orientation_rad', 'position_m'])
        position = measurement_row(c, 'position_m')
        angle = measurement_row(c, 'orientation_rad')
        self.assertEqual(position[2:4], ['position (mm)', '1.000 / 1.000'])
        self.assertEqual(position[-1], '2.000')
        self.assertEqual(angle[2:4], ['orientation (deg)', '90.000 / 90.000'])
        self.assertEqual(angle[-1], '-30.000')

    def test_missing_and_unreproduced_components_are_not_zero_error(self):
        a = {('s', 'c'): event(status='event_not_observed')}
        b = {('s', 'c'): event({'position_m': 0}, status='score_mismatch')}
        c = {'kind': 'pose', 'family': 'push', 'condition_id': 'goal',
             'baseline': arm_summary(a.values()), 'conditioned': arm_summary(b.values()),
             'shared': shared_summary(a, b, True)}
        self.assertEqual(c['baseline']['declared'], 1)
        self.assertEqual(c['baseline']['observed'], 0)
        self.assertEqual(measurement_row(c, 'position_m')[3:], ['N/A', 0, 'N/A', 0, 0, 'N/A'])

    def test_rendering_keeps_conditioning_definitions_and_escapes_html(self):
        a = {('pick', 'grasp'): event({'displacement_m': .002})}
        summary = arm_summary(a.values())
        condition = {'family': 'pick', 'condition_id': 'grasp', 'kind': 'relative_displacement',
            'slot': 'grasp_region', 'definitions': [{'stage_id': 'pick', 'condition': {
                'measurement': {'kind': 'contact_points', 'label': 'object'},
                'reference': {'kind': 'object_center_pose', 'label': 'object'},
                'expected': [0, 0, 0], 'axes': [2], 'tolerance': .01,
                'event': {'kind': 'first_lift', 'threshold': .025}}}],
            'baseline': summary, 'conditioned': deepcopy(summary), 'shared': shared_summary(a, a, True)}
        task = {'task': 'example<&>', 'checkpoint_id': 'cp', 'matched': True,
                'exclusions': [], 'conditions': [condition], 'baseline': summary, 'conditioned': summary,
                'actual_layouts': {'baseline': [0], 'conditioned': [0]},
                'conditioning_prompt': '<script>alert(1)</script>',
                'delivered_prompts': {'baseline': ['native'], 'conditioned': ['native geometry']}}
        data = {'valid_episodes': 2, 'included_tasks': 1, 'catalog_tasks': 1, 'matched_pairs': 1,
                'total_pairs': 1, 'updated_at': 'now', 'reproduced_event_scores': 2, 'score_mismatches': 0,
                'method': 'Physical units only.', 'summary': [dict(condition, checkpoint_id='cp')],
                'tasks': [task], 'coverage': [{'task': task['task'], 'included': True, 'unbound_families': []}],
                'limitations': [], 'scope': 'partial'}
        md, page = report_markdown(data), report_html(data)
        self.assertIn('displacement (mm)', md)
        self.assertIn('2.000 / 2.000', md)
        self.assertIn('first_lift', md)
        self.assertIn('Position axes', md)
        parameters = dict(condition_parameters(condition))
        self.assertEqual(parameters['Tolerance (mm)'], '10.0')
        self.assertIn('"threshold_mm": 25.0', parameters['Measurement event'])
        self.assertIn('Exact delivered policy prompts', page)
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;', page)
        self.assertNotIn('<script>alert(1)</script>', page)
        self.assertNotIn('mean / median r', md)


if __name__ == '__main__':
    unittest.main()
