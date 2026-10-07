#!/usr/bin/env python3
"""Start a stage-only replay proof when a timed, genuinely partial trace arrives."""
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.atomic.storage import atomic_write_json
from task.atomic.replay import validate_start_boundary
from task.atomic.spec import AtomicProgram, AtomicTrace


def eligible_capture(source, stage_id, require_partial_predecessor=False):
    """Prefer baseline; never manufacture a boundary or infer absent timing."""
    manifest = json.loads((source/'suite.json').read_text())
    cases = sorted(manifest['cases'], key=lambda c: c.get('prompt_mode') != 'baseline')
    for case in cases:
        program_path = Path(case['program'])
        digest = hashlib.sha256(program_path.read_bytes()).hexdigest()
        if digest != case['program_sha256']:
            raise ValueError('capture program changed after its manifest was frozen')
        program = AtomicProgram.load(program_path)
        for path in sorted((source/'runs'/case['id']/'traces').glob('*.json')):
            trace = AtomicTrace.load(path)
            try:
                boundary = validate_start_boundary(program, program.stage(stage_id), trace)
            except ValueError:
                continue
            partial_tail = (boundary['mode'] == 'linear_substep_prefix'
                    and boundary['physics_substeps'] < trace.control_timing['control_substeps'])
            earlier_partial = any(not r['at_action_boundary'] for r in
                                  boundary.get('prefix_physics_boundaries', [])[1:-1])
            eligible = (earlier_partial and boundary['mode'] in ('linear_substep_prefix', 'linear_timed_prefix')
                        if require_partial_predecessor else partial_tail)
            if eligible:
                return {'case_id': case['id'], 'program': str(program_path), 'trace': str(path),
                        'program_sha256': digest, 'trace_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                        'boundary': boundary}
    return None


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-suite', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--stage', required=True); p.add_argument('--base-run', type=Path, required=True)
    p.add_argument('--credentials-file', type=Path, required=True)
    p.add_argument('--gpu-memory-ledger', type=Path, required=True)
    p.add_argument('--name', default='rb-substep-proof')
    p.add_argument('--max-wait-s', type=int, default=14400)
    p.add_argument('--require-partial-predecessor', action='store_true',
                   help='Require a real partial boundary before the selected stage')
    p.add_argument('--detach', action='store_true', help='Start a persistent monitor and return its PID')
    a = p.parse_args()
    if a.detach:
        with (a.source_suite/'substep-replay-watch.log').open('a') as log:
            argv = [arg for arg in sys.argv[1:] if arg != '--detach']
            child = subprocess.Popen([sys.executable, '-u', str(Path(__file__).resolve()), *argv],
                cwd=REPO, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                start_new_session=True)
        (a.source_suite/'substep-replay-watch.pid').write_text(str(child.pid)+'\n')
        print('Started substep replay monitor', child.pid, flush=True)
        return
    lock = (a.source_suite/'substep-replay-watch.lock').open('a+')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    state = a.source_suite/'substep-replay-watch.json'
    deadline = time.monotonic() + a.max_wait_s
    driver = [sys.executable, '-u', 'scripts/atomic/run_prefix_validation.py']
    common = ['--root', str(a.output), '--gpu-memory-ledger', str(a.gpu_memory_ledger)]
    def record(status, **extra):
        atomic_write_json(state, {'status': status, 'updated_at': datetime.now(timezone.utc).isoformat(),
                                 'output': str(a.output), **extra})
        print(status, flush=True)
    while time.monotonic() < deadline:
        if (a.output/'control.json').exists():
            record('replay_submitted', control=json.loads((a.output/'control.json').read_text())); return
        provenance = a.output/'capture-source.json'
        if (a.output/'suite.json').exists() and not provenance.exists():
            raise ValueError('prepared replay needs retained capture provenance before resuming')
        selected = (json.loads(provenance.read_text()) if provenance.exists()
                    else eligible_capture(a.source_suite, a.stage, a.require_partial_predecessor))
        if selected is None:
            manifest = json.loads((a.source_suite/'suite.json').read_text())
            if all((a.source_suite/'runs'/c['id']/'collection_finished.json').exists() for c in manifest['cases']):
                record('capture_finished_without_eligible_substep_boundary'); return
            record('waiting_for_timed_partial_capture'); time.sleep(30); continue
        record('timed_capture_available', selected=selected)
        if not (a.output/'suite.json').exists():
            subprocess.run(driver + ['prepare', *common, '--base-run', str(a.base_run),
                '--program', selected['program'], '--trace', selected['trace'], '--stage', a.stage,
                '--name', a.name], cwd=REPO, check=True)
            frozen = a.output/'inputs/trace.json'
            if hashlib.sha256(frozen.read_bytes()).hexdigest() != selected['trace_sha256']:
                raise ValueError('capture changed while preparing replay; no job submitted')
            atomic_write_json(provenance, selected)
        result = subprocess.run(driver + ['start', *common, '--credentials-file', str(a.credentials_file)],
                                cwd=REPO, capture_output=True, text=True)
        if result.returncode:
            if 'global 32-job window has no free slot' in result.stderr:
                record('waiting_for_global_job_slot', selected=selected); time.sleep(30); continue
            record('replay_submission_failed', selected=selected, returncode=result.returncode)
            raise RuntimeError('replay submission failed; inspect its retained operational files')
        record('replay_submitted', selected=selected, control=json.loads((a.output/'control.json').read_text()))
        return
    record('capture_wait_timeout')


if __name__ == '__main__': main()
