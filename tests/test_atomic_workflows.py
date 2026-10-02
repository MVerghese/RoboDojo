"""Regression checks for experimental controls and portable source reuse."""
from copy import deepcopy
import errno
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from scripts.atomic.audit_scores import audit_atomic
from scripts.atomic.generate_ab_suite import generate
from scripts.atomic.run_suite import prepare_case, validate_suite
from task.atomic.geometry import evaluate_geometry
from task.atomic.spec import AtomicProgram

REPO = Path(__file__).resolve().parents[1]


class WorkflowControlsTests(unittest.TestCase):
    def test_pair_keeps_scoring_and_rejects_target_or_prompt_drift(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            prompt = root / 'prompt.txt'
            prompt.write_text('Grasp at the specified contact band.')
            path = generate(REPO / 'task/atomic/programs/pour_balls_into_vase.json', prompt, root / 'suite')
            suite = json.loads(path.read_text())
            validate_suite(suite)
            baseline = json.loads(Path(suite['cases'][0]['program']).read_text())
            conditioned_path = Path(suite['cases'][1]['program'])
            conditioned = json.loads(conditioned_path.read_text())
            self.assertEqual(conditioned.pop('geometric_instruction'), prompt.read_text())
            self.assertEqual(baseline, conditioned)
            # Same-task runs with subtly different targets are not prompt A/B.
            drift = deepcopy(conditioned)
            drift['geometric_instruction'] = prompt.read_text()
            drift['stages'][0]['geometry'][0]['expected'][2] += 0.01
            conditioned_path.write_text(json.dumps(drift))
            with self.assertRaisesRegex(ValueError, 'differ only'):
                validate_suite(suite)
            drift = deepcopy(conditioned)
            drift['geometric_instruction'] = 'A different instruction.'
            conditioned_path.write_text(json.dumps(drift))
            with self.assertRaisesRegex(ValueError, 'append'):
                validate_suite(suite)
            with self.assertRaisesRegex(ValueError, 'empty output'):
                generate(REPO / 'task/atomic/programs/pour_balls_into_vase.json', prompt, root / 'suite')

    def test_x_variants_score_x_not_inherited_z_and_allow_only_fixed_axis_rescoring(self):
        program = AtomicProgram.load(REPO / 'task/atomic/programs/pour_balls_into_vase.json')
        conditions = []
        for side in ('positive', 'negative'):
            variant = json.loads((REPO / f'task/atomic/programs/variants/pick_cup_{side}_x.json').read_text())
            stage = program.stages[0].with_variant(variant)
            condition = stage.geometry[0]
            self.assertEqual(condition['axes'], [0])
            self.assertNotIn('end-effector', stage.instruction)
            # Same z, large unrestricted y: only x should discriminate bands.
            measured = {'position': [0.04, 0, 0.02],
                        'points': [[0.04, 0.30, 0.02], [0.04, -0.30, 0.02]]}
            result = evaluate_geometry(condition, measured, [0, 0, 0, 1, 0, 0, 0])
            self.assertEqual(result.passed, side == 'positive')
            conditions.append(condition)
        recorded = {'stage_id': 'pick_cup', 'conditions': [conditions[0]], 'geometry': {},
                    'action_success': True, 'geometry_coverage': 0}
        opposite = {'stage_id': 'pick_cup', 'conditions': {'cup_grasp_offset': {
            'expected': conditions[1]['expected'], 'axes': [0]}}}
        audit_atomic(recorded, opposite)
        opposite['conditions']['cup_grasp_offset']['axes'] = [2]
        with self.assertRaisesRegex(ValueError, 'new simulator run'):
            audit_atomic(recorded, opposite)

    def test_cross_filesystem_archive_reuse_resolves_source_symlink(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, destination = root / 'source', root / 'case'
            source.mkdir()
            bundle = root / 'immutable.tar.gz'
            bundle.write_bytes(b'archive fixture')
            (source / 'code.tar.gz').symlink_to(bundle)
            (source / 'source_manifest.json').write_text('{}')
            plan = {'tasks': ['pour_balls_into_vase'], 'reservation': 'reserved', 'results_s3': 's3://bucket/prefix/source'}
            (source / 'run_plan.json').write_text(json.dumps(plan))
            spec = {'metadata': {'name': 'source-000'}, 'spec': {
                'affinity': {'allowed_dedicated_node_groups': ['group']}, 'reservation_config': {}}}
            (source / 'source-000.job-spec.json').write_text(json.dumps(spec))
            client = Mock()
            client._get.return_value.json.return_value = [{
                'metadata': {'id': 'node'},
                'spec': {'unschedulable': False, 'resource': {'gpu': {'product': 'NVIDIA-L40S'}}},
                'status': {'machine_status': 'Healthy', 'status': ['Ready', 'Healthy'],
                           'reserved_status': {'id': 'reserved'}}}]
            with patch('scripts.atomic.run_suite.os.link', side_effect=OSError(errno.EXDEV, 'cross-device')) as link:
                prepare_case(source, destination, 'trial', client, root / 'ledger.jsonl')
            self.assertEqual(link.call_args.args[0], bundle.resolve())
            self.assertTrue((destination / 'code.tar.gz').is_symlink())
            self.assertEqual((destination / 'code.tar.gz').read_bytes(), b'archive fixture')
            patched = json.loads((destination / 'trial-000.job-spec.json').read_text())
            self.assertFalse(patched['spec']['reservation_config']['allow_burst_to_other_reservations'])


if __name__ == '__main__':
    unittest.main()
