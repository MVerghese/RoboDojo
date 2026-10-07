"""Replay position residuals require linked trace, boundary, frame and units."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from scripts.atomic.run_prefix_validation import compare_start_positions


class ReplayPositionTests(unittest.TestCase):
    def test_actual_unit_residual_and_guarded_unavailable_cases(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); src = root/'capture/traces/trace.json';src.parent.mkdir(parents=True)
            src.write_text('{}');(root/'inputs').mkdir();(root/'inputs/trace.json').write_bytes(src.read_bytes())
            (root/'capture-source.json').write_text(json.dumps({'trace':str(src),
                'trace_sha256':hashlib.sha256(src.read_bytes()).hexdigest()}))
            stage = {'stage_id':'place','coordinate_frame':'environment_local_world','distance_unit':'metres',
                     'start_boundary':{'action_index':5,'physics_step':100}, 'initial_object_positions':{'obj':[1,2,3]}}
            report = {'native_results':[{'details':{'0':{'layout_id':0,'atomic_sequence':{'stages':[stage]}}}}]}
            path = src.parent.parent/'eval_report.json';path.write_text(json.dumps(report))
            detail = {'layout_id':0,'atomic_start':{'stage_id':'place','action_index':5,'recorded_physics_step':100},
                      'atomic':{**stage,'initial_object_positions':{'obj':[1.003,2.004,3]}}}
            result = compare_start_positions(root,detail)
            self.assertEqual(result['status'],'observed_position_comparison')
            self.assertAlmostEqual(result['positions'][0]['position_error_mm'],5)
            self.assertEqual(result['source_report_sha256'],hashlib.sha256(path.read_bytes()).hexdigest())
            for key, value in [('distance_unit','millimetres'), ('coordinate_frame','object_local')]:
                old = detail['atomic'][key];detail['atomic'][key] = value
                self.assertEqual(compare_start_positions(root,detail)['status'],'unavailable')
                detail['atomic'][key] = old
            detail['atomic_start']['recorded_physics_step'] = 101
            self.assertEqual(compare_start_positions(root,detail)['reason'],'original_boundary_identity_mismatch')
            detail['atomic_start']['recorded_physics_step'] = 100
            (root/'inputs/trace.json').write_text('{"changed":true}')
            self.assertEqual(compare_start_positions(root,detail)['reason'],'capture_trace_hash_mismatch')


if __name__ == '__main__': unittest.main()
