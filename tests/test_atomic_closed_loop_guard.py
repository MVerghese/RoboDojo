"""A failed simulator cannot leave a policy workflow allocated indefinitely."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class ClosedLoopGuardTests(unittest.TestCase):
    def test_simulator_exception_invokes_collection_trap_and_returns_failure(self):
        repo = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = root/'workflow.sh'
            script.write_text("trap 'echo collected > \"$EVAL_OUTPUT_DIR/collected\"; exit 0' TERM\n"
                "echo '[Eval] unhandled exception during reset/run_eval: AttributeError: broken view'\n"
                "while true; do sleep .1; done\n")
            import os
            environment = dict(os.environ, EVAL_OUTPUT_DIR=str(root))
            result = subprocess.run([sys.executable, str(repo/'scripts/atomic/closed_loop_guard.py'),
                '--cleanup-timeout-s', '1', '--', 'bash', str(script)], env=environment,
                capture_output=True, text=True, timeout=5)
            self.assertNotEqual(result.returncode, 0)  # Trap's zero exit cannot erase failure.
            self.assertTrue((root/'collected').exists())
            self.assertEqual(json.loads((root/'atomic-guard-failure.json').read_text())['status'],
                             'simulator_exception')

    def test_normal_policy_task_failure_preserves_exit_and_does_not_trigger_guard(self):
        repo = Path(__file__).resolve().parents[1]
        result = subprocess.run([sys.executable, str(repo/'scripts/atomic/closed_loop_guard.py'),
            '--', sys.executable, '-c', "print('Native task success: False')"],
            capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0)
        self.assertIn('Native task success: False', result.stdout)
        self.assertNotIn('requesting workflow cleanup', result.stdout)
