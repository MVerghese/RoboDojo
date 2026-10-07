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
    def test_invalid_strike_window_is_not_hidden_by_numerically_scored_path(self):
        rows={'atomic_scores':[{'stage_id':'strike','family':'touch_with_tool','conditions':{},
            'trajectories':{'path':{'status':'invalid_recognition_window',
                'condition':{'slot':'tool path'}, 'recorded_result':{'status':'scored',
                'max_deviation_m':.001,'duration_s':.5}}}}]}
        events=collect_events(rows); summary=arm_summary(events.values())
        self.assertEqual(summary['observed'],0)
        self.assertEqual(summary['statuses'],{'invalid_recognition_window':1})
        self.assertEqual(summary['components'],{})

    def test_layer_gap_defaults_are_not_measurements_without_projected_overlap(self):
        a = event({'footprint_overlap_fraction':0.,'footprint_gap_m':.018,
                   'layer_gap_shortfall_m':0.,'layer_gap_excess_m':0.})
        a['score']['recorded_result']['observed'] = {'gap_observed':False}
        b = event({'footprint_overlap_fraction':.7,'footprint_gap_m':0.,
                   'layer_gap_shortfall_m':0.,'layer_gap_excess_m':.004})
        b['score']['recorded_result']['observed'] = {'gap_observed':True}
        sa,sb = arm_summary([a]),arm_summary([b])
        self.assertEqual(sa['components']['footprint_overlap_fraction']['mean'],0.)
        self.assertEqual(sa['components']['footprint_gap_m']['mean'],.018)
        self.assertNotIn('layer_gap_shortfall_m',sa['components'])
        self.assertEqual(sa['component_unavailable_reasons'],{'no_projected_material_overlap_for_vertical_gap':1})
        self.assertEqual(sb['components']['layer_gap_excess_m']['mean'],.004)
        shared = shared_summary({('fold','layer'):a},{('fold','layer'):b},True)
        self.assertNotIn('layer_gap_excess_m',shared['components'])
        self.assertEqual(shared['components']['footprint_overlap_fraction']['n'],1)

    def test_pending_relation_rows_name_the_actual_checker_components(self):
        empty = arm_summary([])
        for definition,expected in [
            ({'expected':'coincides_with_curve','relation_scope':'curves'},
             {'curve_gap_m','curve_hausdorff_m','measurement_curve_length_m','reference_curve_length_m'}),
            ({'expected':'coincides_with_segment','relation_scope':'segments'},
             {'segment_gap_m','segment_hausdorff_m','segment_axis_angle_rad','measurement_length_m','reference_length_m'}),
            ({'expected':'inside_trace_aperture','relation_scope':'objects'},
             {'section_area_m2','outside_aperture_area_m2','outside_allowed_area_m2','boundary_distance_m'}),
            ({'expected':'near','relation_scope':'objects'},{'surface_distance_m'})]:
            c = {'kind':'spatial_relation','definitions':[{'condition':definition}],
                 'baseline':empty,'conditioned':empty}
            self.assertEqual(set(component_names(c)),expected)
        self.assertEqual(component_unit('section_area_m2'),('section area (mm²)',1e6))

    def test_unobserved_selection_still_names_its_requested_physical_factor(self):
        empty = arm_summary([])
        c = {'kind':'selection','definitions':[{'condition':{'kind':'pose'}}],
             'baseline':empty,'conditioned':empty}
        self.assertEqual(set(component_names(c)),{'position_m','orientation_rad'})

    def test_integrated_report_keeps_repeated_tasks_and_runtimes_separate(self):
        from pathlib import Path
        from scripts.atomic.report_integrated import integrate
        empty = arm_summary([])
        task = {'task': 'same_task', 'checkpoint_id': 'cp', 'matched': True,
                'exclusions': [], 'conditions': [], 'baseline': empty, 'conditioned': empty,
                'baseline_case': 'a', 'conditioned_case': 'b',
                'actual_layouts': {'baseline': [0], 'conditioned': [0]},
                'conditioning_prompt': 'original target',
                'delivered_prompts': {'baseline': ['native'], 'conditioned': ['native original target']}}
        condition = {'family': 'pick', 'condition_id': 'offset', 'kind': 'relative_displacement',
                     'slot': 'grasp_region', 'baseline': empty, 'conditioned': empty,
                     'shared': {'n_events': 0, 'components': {}}, 'checkpoint_id': 'cp'}
        data = {'valid_episodes': 2, 'included_tasks': 1, 'catalog_tasks': 2, 'matched_pairs': 1,
                'total_pairs': 1, 'updated_at': '2026-10-06', 'reproduced_event_scores': 0,
                'score_mismatches': 0, 'method': 'Physical units.', 'summary': [condition],
                'tasks': [task], 'coverage': [
                    {'task': 'same_task', 'included': True, 'unbound_families': []},
                    {'task': 'not_run', 'included': False, 'blocker': 'unsupported'}],
                'limitations': [], 'scope': 'partial', 'checkpoints': {'cp': {}}}
        result = {'completed_cases': 2, 'cases': [
            {'case_id': c, 'status': 'passed', 'completed_episodes': 1,
             'full_task_success': [True], 'runtime_sha256': 'old-runtime'} for c in ('a', 'b')]}
        second = deepcopy(data)
        second['tasks'][0]['conditioning_prompt'] = 'new target <unsafe>'
        second['valid_episodes'] = second['matched_pairs'] = 0
        second['tasks'][0]['matched'] = False
        second['tasks'][0]['exclusions'] = ['pending']
        pending = {'completed_cases': 0, 'cases': [
            {'case_id': c, 'status': 'pending', 'completed_episodes': 0,
             'runtime_sha256': 'new-runtime'} for c in ('a', 'b')]}
        suites = [('original', Path('/original'), {'cases': [{}, {}]}, result, data),
                  ('expansion', Path('/expansion'), {'cases': [{}, {}]}, pending, second)]
        combined = integrate(suites)
        self.assertEqual(combined['included_tasks'], 1)
        self.assertEqual(combined['total_pairs'], 2)
        self.assertEqual(combined['matched_pairs'], 1)
        self.assertEqual(combined['valid_episodes'], 2)
        self.assertEqual(len(combined['tasks']), 2)
        self.assertEqual([r['suite'] for r in combined['summary']], ['original', 'expansion'])
        self.assertEqual(combined['tasks'][1]['provenance']['baseline']['runtime_sha256'], 'new-runtime')
        self.assertEqual(data['tasks'][0]['conditioning_prompt'], 'original target')
        md, page = report_markdown(combined), report_html(combined)
        self.assertIn('original target', md)
        self.assertIn('new target <unsafe>', md)
        self.assertIn('new target &lt;unsafe&gt;', page)
        self.assertIn('new-runtime', page)
        self.assertIn('Original screen and expansion suites', page)
        self.assertIn('not_run', md)

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
