"""A failed simulator cannot leave a policy workflow allocated indefinitely."""
import json
import os
from pathlib import Path
import subprocess
import sys
import signal
import tempfile
import unittest
import time


class ClosedLoopGuardTests(unittest.TestCase):
    def test_external_termination_forwards_to_workflow_trap_and_uses_node_cache_output(self):
        repo = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory);output = root/'runs'/'test-run'/'output'
            script = root/'workflow.sh'
            script.write_text("mkdir -p \"$ROBODOJO_NODE_CACHE_DIR/runs/$ROBODOJO_RUN_ID/output\"\n"
                "trap 'touch \"$ROBODOJO_NODE_CACHE_DIR/runs/$ROBODOJO_RUN_ID/output/collected\"; exit 0' TERM\n"
                "touch \"$ROBODOJO_NODE_CACHE_DIR/ready\"\nwhile true; do sleep .05; done\n")
            environment = {k:v for k,v in os.environ.items() if k != 'EVAL_OUTPUT_DIR'}
            environment.update(ROBODOJO_NODE_CACHE_DIR=str(root),ROBODOJO_RUN_ID='test-run')
            child = subprocess.Popen([sys.executable,str(repo/'scripts/atomic/closed_loop_guard.py'),
                '--cleanup-timeout-s','1','--','bash',str(script)],env=environment,
                stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
            try:
                deadline = time.monotonic()+3
                while not (root/'ready').exists() and time.monotonic()<deadline:
                    time.sleep(.01)
                self.assertTrue((root/'ready').exists())
                child.send_signal(signal.SIGTERM)
                child.communicate(timeout=4)
                self.assertEqual(child.returncode,143)
                self.assertTrue((output/'collected').exists())
                self.assertEqual(json.loads((output/'atomic-guard-failure.json').read_text())['status'],
                                 'workflow_interrupted')
            finally:
                if child.poll() is None:child.kill();child.communicate()

    def test_fast_worker_exit_drains_fatal_marker_without_newline(self):
        repo = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            environment = dict(os.environ,EVAL_OUTPUT_DIR=directory)
            source = ("import sys;sys.stdout.write('normal log\\n'*40000);"
                      "sys.stdout.write('[Eval] unhandled exception during reset/run_eval: broken');sys.stdout.flush()")
            result = subprocess.run([sys.executable,str(repo/'scripts/atomic/closed_loop_guard.py'),
                '--',sys.executable,'-c',source],env=environment,capture_output=True,timeout=5)
            self.assertNotEqual(result.returncode,0)
            self.assertEqual(json.loads((Path(directory)/'atomic-guard-failure.json').read_text())['status'],
                             'simulator_exception')

    def test_unresponsive_cleanup_is_bounded(self):
        repo = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            source = ("import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);"
                      "print('[Eval] unhandled exception during reset/run_eval: stuck',flush=True);time.sleep(10)")
            result = subprocess.run([sys.executable,str(repo/'scripts/atomic/closed_loop_guard.py'),
                '--cleanup-timeout-s','.1','--',sys.executable,'-c',source],
                env=dict(os.environ,EVAL_OUTPUT_DIR=directory),capture_output=True,text=True,timeout=4)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('cleanup timeout',result.stdout)

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
