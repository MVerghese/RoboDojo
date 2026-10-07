"""Automatic replay waits for original physical boundaries with a command tail."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from dataclasses import replace
from scripts.atomic.watch_substep_replay import eligible_capture
from test_atomic_substep_replay import fixture


class SubstepWatchTests(unittest.TestCase):
    def test_missing_timing_and_command_end_do_not_launch_partial_proof(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); program, trace = fixture()
            # Serialize a concrete schema program rather than synthetic callbacks.
            raw = {'task_name': program.task_name, 'stages': [
                {'id':s.id, 'family':s.family, 'instruction':s.instruction,
                 'success_checks':list(s.success_checks), 'geometry':[], 'recognition':s.recognition}
                for s in program.stages]}
            p = root/'program.json'; p.write_text(json.dumps(raw))
            case = {'id':'baseline','prompt_mode':'baseline','program':str(p),
                    'program_sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
            (root/'suite.json').write_text(json.dumps({'cases':[case]}))
            d = root/'runs/baseline/traces'; d.mkdir(parents=True)
            self.assertIsNone(eligible_capture(root, 'b'))
            path = d/'trace.json'
            path.write_text(json.dumps(replace(trace, control_timing={}).__dict__))
            self.assertIsNone(eligible_capture(root, 'b'))
            path.write_text(json.dumps(replace(trace, stage_boundaries={
                'b':{'action_index':2,'physics_step':108,'at_action_boundary':False}}).__dict__))
            self.assertIsNone(eligible_capture(root, 'b'))
            path.write_text(json.dumps(trace.__dict__))
            selected = eligible_capture(root, 'b')
            self.assertEqual(selected['boundary']['physics_substeps'], 2)
            self.assertEqual(selected['trace_sha256'], hashlib.sha256(path.read_bytes()).hexdigest())
            p.write_text('{}')
            with self.assertRaisesRegex(ValueError, 'program changed'):
                eligible_capture(root, 'b')


if __name__ == '__main__': unittest.main()
