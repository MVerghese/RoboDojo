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


def output_directory(environment):
    if environment.get('EVAL_OUTPUT_DIR'):
        return Path(environment['EVAL_OUTPUT_DIR'])
    if environment.get('ROBODOJO_NODE_CACHE_DIR') and environment.get('ROBODOJO_RUN_ID'):
        return Path(environment['ROBODOJO_NODE_CACHE_DIR'])/'runs'/environment['ROBODOJO_RUN_ID']/'output'
    return Path('/workspace/robodojo-eval-output')


def supervise(command, cleanup_timeout_s=120, failure_path=None):
    child = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             start_new_session=True)
    selector = selectors.DefaultSelector()
    selector.register(child.stdout, selectors.EVENT_READ)
    decoder = codecs.getincrementaldecoder('utf-8')(errors='replace')
    pending = ''
    failed_at = None
    stopping_at = None
    interrupted = None
    exited_at = None

    def retain(status, message):
        if failure_path is not None:
            failure_path.parent.mkdir(parents=True, exist_ok=True)
            failure_path.write_text(json.dumps({'status': status, 'message': message,
                'action': 'terminate workflow and retain existing collection trap'})+'\n')

    def check_line(line):
        nonlocal failed_at, stopping_at
        if FATAL_MARKER in line and failed_at is None:
            failed_at = time.monotonic()
            stopping_at = stopping_at or failed_at
            retain('simulator_exception', line)
            print('[atomic guard] simulator exception; requesting workflow cleanup', flush=True)
            if child.poll() is None:
                child.send_signal(signal.SIGTERM)

    def forward_signal(signum, frame):
        nonlocal interrupted, stopping_at
        if interrupted is None:
            interrupted = signum
            stopping_at = stopping_at or time.monotonic()
            if failed_at is None:
                retain('workflow_interrupted', 'external signal '+str(signum))
            if child.poll() is None:
                child.send_signal(signum)

    original_handlers = {s: signal.signal(s, forward_signal) for s in (signal.SIGTERM, signal.SIGINT)}
    try:
        while True:
            for key, _ in selector.select(timeout=.2):
                chunk = os.read(key.fileobj.fileno(), 65536)
                if not chunk:
                    selector.unregister(key.fileobj)
                    pending += decoder.decode(b'', final=True)
                    check_line(pending)
                    pending = ''
                    continue
                sys.stdout.buffer.write(chunk)
                sys.stdout.buffer.flush()
                pending += decoder.decode(chunk)
                lines = pending.split('\n')
                pending = lines.pop()
                for line in lines:
                    check_line(line)
                # Detect a fatal marker even when the dying worker emits no newline.
                if FATAL_MARKER in pending:
                    check_line(pending)
            code = child.poll()
            if code is not None:
                exited_at = exited_at or time.monotonic()
                # Drain an already exited worker's buffered output. Bound inherited
                # writers so an orphan cannot hold this allocation indefinitely.
                if selector.get_map() and time.monotonic()-exited_at < 2:
                    continue
                check_line(pending)
                if failed_at is not None:
                    return code if code > 0 else 1
                if interrupted is not None:
                    return 128+interrupted
                return code if code >= 0 else 128-code
            if stopping_at is not None and time.monotonic()-stopping_at > cleanup_timeout_s:
                print('[atomic guard] cleanup timeout; terminating workflow process group', flush=True)
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()
                return 1
    finally:
        for signum, handler in original_handlers.items():
            signal.signal(signum, handler)
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
    output = output_directory(os.environ)
    raise SystemExit(supervise(command, args.cleanup_timeout_s, output/'atomic-guard-failure.json'))
