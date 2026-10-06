"""Release an atomic eval allocation after a retained simulator exception.

The original workflow still owns collection/upload and its policy subprocesses.
TERM lets its existing trap run; a bounded cleanup wait prevents a stuck Isaac
shutdown from retaining the GPU until the full episode timeout.
"""
import argparse
import codecs
import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import sys
import time


FATAL_MARKER = '[Eval] unhandled exception during reset/run_eval:'


def supervise(command, cleanup_timeout_s=120, failure_path=None):
    child = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             start_new_session=True)
    selector = selectors.DefaultSelector()
    selector.register(child.stdout, selectors.EVENT_READ)
    decoder = codecs.getincrementaldecoder('utf-8')(errors='replace')
    pending = ''
    failed_at = None
    try:
        while True:
            for key, _ in selector.select(timeout=.2):
                chunk = os.read(key.fileobj.fileno(), 65536)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                sys.stdout.buffer.write(chunk)
                sys.stdout.buffer.flush()
                pending += decoder.decode(chunk)
                lines = pending.split('\n')
                pending = lines.pop()
                for line in lines:
                    if FATAL_MARKER in line and failed_at is None:
                        failed_at = time.monotonic()
                        if failure_path is not None:
                            failure_path.parent.mkdir(parents=True, exist_ok=True)
                            failure_path.write_text(json.dumps({
                                'status': 'simulator_exception', 'message': line,
                                'action': 'terminate workflow and retain existing collection trap'}) + '\n')
                        print('[atomic guard] simulator exception; requesting workflow cleanup', flush=True)
                        child.send_signal(signal.SIGTERM)
            code = child.poll()
            if code is not None:
                return (code if code > 0 else 1) if failed_at is not None else (code if code >= 0 else 128-code)
            if failed_at is not None and time.monotonic()-failed_at > cleanup_timeout_s:
                print('[atomic guard] cleanup timeout; terminating workflow process group', flush=True)
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()
                return 1
    finally:
        selector.close()
        child.stdout.close()
        if child.poll() is None:
            os.killpg(child.pid, signal.SIGTERM)
            try:
                child.wait(timeout=cleanup_timeout_s)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cleanup-timeout-s', type=float, default=120)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    if not command or args.cleanup_timeout_s <= 0:
        parser.error('requires a command and a positive cleanup timeout')
    output = Path(os.environ.get('EVAL_OUTPUT_DIR', '/workspace/robodojo-eval-output'))
    raise SystemExit(supervise(command, args.cleanup_timeout_s, output/'atomic-guard-failure.json'))
