"""Coverage, layout binding and missing-data controls for expanded A/B evals."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest

from scripts.atomic.generate_eval_matrix import generate, pickup
from scripts.atomic.report_eval_matrix import aggregate
from scripts.atomic.run_suite import validate_suite
from task.atomic.spec import AtomicProgram, AtomicStage


class EvalMatrixTests(unittest.TestCase):
    def test_render_refresh_checks_raw_boundaries_from_an_older_collector_without_changing_inputs(self):
        from scripts.atomic.report_eval_matrix import refresh_recognition_validation
        from test_atomic_recognition_validation import handover
        stage=handover();stage['stage_id']='handover';stage['conditions']=[{
            'id':'giver','event':{'kind':'recognition_event','name':'giver_hold'}}]
        stage['physical_events']['giver_hold']['contact']['contact_interval_start_step']=1
        result={'cases':[{'case_id':'case','atomic_scores':[{'episode':'0','stage_id':'handover',
            'conditions':{'giver':{'status':'reproduced'}},'trajectories':{}}]}]}
        before=deepcopy(result)
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);run=root/'runs/case';run.mkdir(parents=True)
            (run/'eval_report.json').write_text(json.dumps({'native_results':[{'details':{
                '0':{'atomic_sequence':{'stages':[stage]}}}}]}))
            refreshed=refresh_recognition_validation(root,result)
        self.assertEqual(result,before)
        self.assertEqual(refreshed['reproduced_event_scores'],0)
        self.assertEqual(refreshed['recognition_witness_failures'],1)
        self.assertEqual(refreshed['cases'][0]['atomic_scores'][0]['conditions']['giver']['status'],
                         'invalid_recognition_window')

    def test_finished_collection_without_report_is_failed_evidence_not_pending_policy_failure(self):
        from scripts.atomic.run_suite import summarize
        manifest = {'task':'task','mode':'test','cases':[{'id':'case','stage':'stage','kind':'point'}]}
        for code in (0,2):
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp);run = root/'runs'/'case';run.mkdir(parents=True)
                (run/'collection_finished.json').write_text(json.dumps({'exit_code':code}))
                result = summarize(manifest,root);row = result['cases'][0]
                self.assertEqual(row['status'],'failed');self.assertEqual(result['completed_cases'],1)
                self.assertEqual(row['rollout_outcome'],'unavailable')
                self.assertEqual(row['completed_episodes'],0)  # Retained episodes, not inferred execution count.
                self.assertNotIn('full_task_success',row);self.assertNotIn('atomic_scores',row)

    def test_report_takes_precedence_over_collector_exit_and_unfinished_case_stays_pending(self):
        from scripts.atomic.run_suite import summarize
        manifest = {'task':'task','mode':'test','cases':[{'id':'case','stage':'stage','kind':'point'}]}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp);run = root/'runs'/'case';run.mkdir(parents=True)
            self.assertEqual(summarize(manifest,root)['cases'][0]['status'],'pending')
            (run/'collection_finished.json').write_text(json.dumps({'exit_code':2}))
            (run/'eval_report.json').write_text(json.dumps({'status':'passed','completed_episodes':1,
                'errors':[],'native_results':[]}))
            row = summarize(manifest,root)['cases'][0]
            self.assertEqual(row['status'],'passed');self.assertEqual(row['completed_episodes'],1)
            self.assertNotIn('collection_outcome',row)

    def test_quiet_contact_backend_is_unverified_until_a_report_arrives(self):
        from task.atomic.contacts import PhysXContacts
        backend = PhysXContacts.__new__(PhysXContacts)
        backend.steps, backend.reports, backend.errors, backend.fingers = 20, 0, [], {'finger': (0, 'arm')}
        self.assertEqual(backend.summary()['health_status'], 'awaiting_contact_evidence')
        backend.reports = 1
        self.assertEqual(backend.summary()['health_status'], 'observed_reports')
        backend.errors = ['malformed report']
        self.assertEqual(backend.summary()['health_status'], 'callback_error')

    def test_reviewed_eval_coverage_and_checkpoint_pairing(self):
        with tempfile.TemporaryDirectory() as temp:
            checkpoints = {'cp': {'checkpoint': 's3://bucket/checkpoint', 'base_run': '/compatible/base'}}
            suite = generate(Path(temp), checkpoints)
            self.assertEqual(len(suite['coverage']), 54)
            self.assertEqual(sum(c['included'] for c in suite['coverage']), 49)
            self.assertEqual(len(suite['cases']), 98)
            self.assertEqual({f for c in suite['coverage'] if c['included'] for f in c['families']},
                {'pick', 'place', 'push', 'push_with_tool', 'actuate', 'touch_with_tool', 'handover'})
            validate_suite(suite)
            suite['cases'][1]['checkpoint_id'] = 'unknown'
            with self.assertRaisesRegex(ValueError, 'checkpoint'):
                validate_suite(suite)

    def template(self):
        a = AtomicStage.from_dict(pickup('pick', '$object'))
        b = AtomicStage.from_dict(pickup('later', 'fixed'))
        return AtomicProgram('task', (a, b), stage_dependencies={'pick': [], 'later': ['pick']},
            label_templates={'pick': {'prefix': 'cube', 'placeholder': '$object', 'min': 1, 'max': 3, 'category': 'rigid'}})

    def world(self, labels=('cube_b', 'cube_a'), category='rigid'):
        lm = NS(get_labels_by_prefix=lambda **kw: labels,
                get_instance_name=lambda **kw: kw['label'],
                instance_type_by_env=[dict.fromkeys(labels, category)])
        return NS(scene_manager=NS(layout_manager=lm))

    def test_explicit_prefix_expansion_preserves_optional_and_all_dependencies(self):
        bound = self.template().bind(self.world(), 0)
        self.assertEqual([s.recognition['label'] for s in bound.stages], ['cube_a', 'cube_b', 'fixed'])
        self.assertEqual(bound.dependencies()['later'], ['pick__label_1', 'pick__label_2'])
        self.assertFalse(bound.stages[0].required)
        self.assertEqual(bound.stages[0].geometry[0]['reference']['label'], 'cube_a')
        self.assertEqual(bound.binding_evidence['pick']['labels'], ['cube_a', 'cube_b'])
        self.assertIsNone(bound.label_templates)

    def test_prefix_refuses_count_category_duplicate_and_collision(self):
        for labels, category in [((), 'rigid'), (('a','a'), 'rigid'), (('a',), 'garment'),
                                (('a','b','c','d'), 'rigid')]:
            with self.subTest(labels=labels, category=category), self.assertRaises(ValueError):
                self.template().bind(self.world(labels, category), 0)
        program = self.template()
        program = replace(program, stages=(program.stages[0], replace(program.stages[1], id='pick__label_1')),
                          stage_dependencies={'pick': [], 'pick__label_1': []})
        with self.assertRaises(ValueError):
            program.bind(self.world(), 0)

    def test_missing_geometry_and_infrastructure_never_become_passes(self):
        manifest = {'cases': [{'id': 'a', 'task': 't', 'checkpoint_id': 'cp', 'layout_id': 0},
                             {'id': 'b', 'task': 't', 'checkpoint_id': 'cp', 'layout_id': 0,
                              'geometric_prompt_append': 'geometry'}],
                    'coverage': [], 'limitations': [], 'scope': 'partial',
                    'checkpoints': {'cp': {'checkpoint': 'checkpoint'}}}
        stage = {'stage_id': 'pick', 'layout_id': 0, 'family': 'pick', 'action_success': False,
                 'required': False, 'conditions': {'grasp': {'status': 'event_not_observed',
                 'kind': 'relative_displacement', 'slot': 'grasp_region'}}}
        row = {'status': 'passed', 'completed_episodes': 1, 'full_task_success': [False],
               'contact_instrumentation': [{'steps': 1, 'reports': 1, 'errors': []}],
               'checkpoint_id': 'cp', 'checkpoint': 'checkpoint', 'task': 't',
               'runtime_sha256': 'same', 'source_archive_sha256': 'same',
               'execution_controls': {'checkpoint': 'checkpoint'}, 'atomic_scores': [stage]}
        a = row | {'case_id': 'a', 'prompt_mode': 'baseline',
                   'policy_prompt_history': [[{'instruction': 'native'}]]}
        b = deepcopy(row) | {'case_id': 'b', 'prompt_mode': 'conditioned',
                   'policy_prompt_history': [[{'instruction': 'native geometry'}]]}
        result = {'updated_at': 'now', 'cases': [a, b]}
        data = aggregate(manifest, result)
        self.assertEqual(data['matched_pairs'], 1)
        self.assertEqual(data['metrics'][0]['geometry'][0]['observed'], 0)
        self.assertEqual(data['metrics'][0]['geometry'][0]['components'], {})
        b['contact_instrumentation'][0]['reports'] = 0
        self.assertEqual(aggregate(manifest, result)['matched_pairs'], 0)
        b['contact_instrumentation'][0]['reports'] = 1
        b['completed_episodes'] = 0
        b['status'] = 'failed'
        data = aggregate(manifest, result)
        self.assertEqual(data['valid_episodes'], 1)
        self.assertEqual(data['matched_pairs'], 0)
        self.assertTrue(all(m['scope'] == 'all_valid_episodes' for m in data['metrics']))


if __name__ == '__main__':
    unittest.main()
