#!/usr/bin/env python3
"""Freeze, submit and collect a selected-stage physical-prefix validation job.

This is a stage-only runtime proof, kept outside full-task A/B summaries.
"""
import argparse
from datetime import datetime,timezone
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys

REPO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(REPO))
from scripts.atomic.storage import atomic_write_json
from scripts.atomic.run_suite import prepare_case,freeze_case,read_frozen_case
from scripts.atomic.submit_stage import validate_stage_inputs
from scripts.atomic.submit_trace import submit_prepared
from task.atomic.spec import AtomicProgram,AtomicTrace


def compare_start_positions(root, detail):
    """Compare retained selected-stage root positions; never claim full state."""
    scope = 'selected-stage object root positions only; no velocity, drive, material or full-state comparison'
    unavailable = lambda reason: {'status':'unavailable', 'reason':reason, 'scope':scope}
    source = root/'capture-source.json'
    if not source.exists(): return unavailable('capture_source_manifest_absent')
    try:
        capture = json.loads(source.read_text());trace_path = Path(capture['trace'])
        if (hashlib.sha256(trace_path.read_bytes()).hexdigest() != capture['trace_sha256']
                or hashlib.sha256((root/'inputs/trace.json').read_bytes()).hexdigest() != capture['trace_sha256']):
            return unavailable('capture_trace_hash_mismatch')
        original_path = trace_path.parent.parent/'eval_report.json'
        data = original_path.read_bytes();original = json.loads(data)
        start = detail['atomic_start'];atomic = detail['atomic'];matches = []
        if type(detail.get('layout_id')) is not int:
            return unavailable('replay_layout_id_absent')
        for native in original.get('native_results', []):
            details = native.get('details', {});details = details.values() if isinstance(details,dict) else details
            for candidate in details:
                if candidate.get('layout_id') != detail.get('layout_id'): continue
                for stage in candidate.get('atomic_sequence',{}).get('stages',[]):
                    if stage['stage_id'] == start['stage_id']: matches.append(stage)
        if len(matches) != 1: return unavailable('original_stage_boundary_not_unique')
        before = matches[0];boundary = before['start_boundary']
        if (boundary['action_index'] != start['action_index']
                or boundary['physics_step'] != start.get('recorded_physics_step')
                or atomic['stage_id'] != start['stage_id']):
            return unavailable('original_boundary_identity_mismatch')
        if any(s.get('coordinate_frame') != 'environment_local_world' or s.get('distance_unit') != 'metres'
               for s in (before,atomic)):
            return unavailable('position_frame_or_units_not_comparable')
        old, new = before['initial_object_positions'], atomic['initial_object_positions']
        positions = []
        for label in sorted(old.keys() & new.keys()):
            a, b = old[label], new[label]
            if len(a) != 3 or len(b) != 3 or not all(type(v) in (int,float) and math.isfinite(v) for v in [*a,*b]):
                return unavailable('invalid_root_position')
            delta = [1000*(actual-recorded) for recorded,actual in zip(a,b)]
            positions.append({'label':label, 'recorded_position_m':a, 'replayed_position_m':b,
                              'axis_difference_mm':delta, 'position_error_mm':math.sqrt(sum(v*v for v in delta))})
        if not positions: return unavailable('no_comparable_object_roots')
        from task.atomic.kinematics import compare_rigid_roots
        kinematics=compare_rigid_roots(before.get('initial_object_states',{}),atomic.get('initial_object_states',{}),
            boundary['physics_step'],atomic.get('initial_state_physics_step'))
        return {'status':'observed_position_comparison', 'positions':positions,
                'unmatched_labels':sorted(old.keys() ^ new.keys()), 'scope':scope,
                'rigid_kinematics':kinematics,
                'source_report':str(original_path), 'source_report_sha256':hashlib.sha256(data).hexdigest()}
    except (KeyError, ValueError, TypeError, OSError) as error:
        return unavailable(type(error).__name__)


def collect_proof(root,case):
    run=root/'runs'/case['id'];path=run/'eval_report.json'
    rows=[]
    if path.exists():
        report=json.loads(path.read_text())
        for native in report.get('native_results',[]):
            details=native.get('details',{});details=details.values() if isinstance(details,dict) else details
            for detail in details:
                start=detail.get('atomic_start',{});prefix=start.get('prefix_stage_validation',[])
                rows.append({'atomic_start':start,'selected_stage_success':detail.get('atomic',{}).get('action_success'),
                    'boundary_position_comparison':compare_start_positions(root,detail),
                    'prefix_verified':start.get('mode') in ('linear_prefix', 'linear_substep_prefix', 'linear_timed_prefix') and bool(prefix)
                        and (start.get('mode')=='linear_prefix' or start.get('physics_boundary_verified') is True)
                        and all(s.get('action_success') is True and s.get('prefix_boundary_verified') is True for s in prefix)})
    proof={'scope':'selected-stage replay and physical prefix witnesses; not full-state fidelity or a full-task A/B run',
        'status':'observed_verified_prefix' if any(r['prefix_verified'] for r in rows) else 'prefix_validation_unavailable',
        'episodes':rows,'report_sha256':hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None}
    atomic_write_json(root/'prefix-validation.json',proof)
    print(json.dumps({k:v for k,v in proof.items() if k!='episodes'}),flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['prepare','start','monitor','proof'])
    p.add_argument('--root',type=Path,required=True);p.add_argument('--base-run',type=Path)
    p.add_argument('--program',type=Path);p.add_argument('--trace',type=Path);p.add_argument('--stage')
    p.add_argument('--name',default='rb-prefix-validation');p.add_argument('--credentials-file',type=Path)
    p.add_argument('--detach',action='store_true',help='Detach a resumed monitor for an already submitted proof')
    p.add_argument('--gpu-memory-ledger',type=Path,required=True)
    a=p.parse_args();root=a.root
    if not re.fullmatch('[a-z0-9-]+',a.name):p.error('name must be a job slug')
    if a.action=='prepare':
        if not all((a.base_run,a.program,a.trace,a.stage)):p.error('prepare needs base-run, program, trace and stage')
        program=AtomicProgram.load(a.program);trace=AtomicTrace.load(a.trace)
        validate_stage_inputs(program,a.stage,trace,None)
        if root.exists() and any(root.iterdir()):raise ValueError('prepare needs an empty fresh directory')
        root.mkdir(parents=True,exist_ok=True)
        inputs=root/'inputs';inputs.mkdir()
        for name,source in [('program',a.program),('trace',a.trace)]:
            (inputs/(name+'.json')).write_bytes(source.read_bytes())
        case={'id':'selected_stage','task':program.task_name,'stage':a.stage,
              'program':str(inputs/'program.json'),'trace':str(inputs/'trace.json')}
        atomic_write_json(root/'suite.json',{'task':program.task_name,'mode':'selected_stage_replay_validation',
            'cases':[case],'scope':'stage-only runtime proof; no full-task A/B summary'})
        from leptonai.api.v2.client import APIClient
        run=root/'runs'/case['id']
        prepare_case(a.base_run,run,a.name,APIClient(),a.gpu_memory_ledger,task=program.task_name,task_timeout_s=7200)
        subprocess.run([sys.executable,'scripts/atomic/submit_stage.py','--run-dir',str(run),
            '--program',case['program'],'--trace',case['trace'],'--stage',a.stage,
            '--max-initial-gpu-memory-mib','512','--dry-run'],cwd=REPO,check=True)
        plan=json.loads((run/'run_plan.json').read_text());specpath=run/(plan['jobs'][0]+'.atomic-job-spec.json')
        spec=json.loads(specpath.read_text());spec['spec']['queue_config']={'priority_class':'high-9000'}
        allowed=spec['spec']['affinity']['allowed_nodes_in_node_group']
        spec['spec']['affinity']['allowed_nodes_in_node_group']=[n for n in allowed if n!='node-ip-10-50-114-4']
        atomic_write_json(specpath,spec);freeze_case(run,case['program'],case['task'])
        print('Frozen selected-stage prefix validation:',root,flush=True);return
    case=json.loads((root/'suite.json').read_text())['cases'][0];run=root/'runs'/case['id']
    if a.action=='proof':collect_proof(root,case);return
    if a.credentials_file is None:p.error('start/monitor needs credentials-file')
    if a.action=='monitor':
        if a.detach:
            plan=json.loads((run/'run_plan.json').read_text())
            if len(plan.get('submitted',[]))!=1:raise ValueError('monitor resume needs exactly one submitted proof')
            control=json.loads((root/'control.json').read_text())
            if control['job']!=plan['submitted'][0]['id']:raise ValueError('monitor resume job identity mismatch')
            if (run/'collection_finished.json').exists():
                print('Prefix proof collection already finished',flush=True);return
            try:
                argv=Path('/proc',str(control['monitor_pid']),'cmdline').read_bytes().split(b'\0')
                if (str(root).encode() in argv and b'monitor' in argv
                        and any(arg.endswith(b'/scripts/atomic/run_prefix_validation.py') for arg in argv)):
                    print('Prefix proof monitor already running',control['monitor_pid'],flush=True);return
            except (FileNotFoundError,ProcessLookupError):pass
            with (run/'controller-monitor.log').open('a') as log:
                argv=[arg for arg in sys.argv[1:] if arg!='--detach']
                child=subprocess.Popen([sys.executable,'-u',str(Path(__file__).resolve()),*argv],cwd=REPO,
                    stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,start_new_session=True)
            control['previous_monitor_pid']=control['monitor_pid'];control['monitor_pid']=child.pid
            control['monitor_resumed_at']=datetime.now(timezone.utc).isoformat()
            atomic_write_json(root/'control.json',control)
            print('Resumed prefix proof monitor',child.pid,flush=True);return
        collection_lock=(root/'prefix-collection.lock').open('a+')
        try:fcntl.flock(collection_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            print('Prefix proof collector already active',flush=True);return
        subprocess.run([sys.executable,'scripts/atomic/monitor_trace.py','--run-dir',str(run),
            '--credentials-file',str(a.credentials_file),'--gpu-memory-ledger',str(a.gpu_memory_ledger)],cwd=REPO,check=True)
        collect_proof(root,case)
        atomic_write_json(run/'collection_finished.json',{
            'completed_at':datetime.now(timezone.utc).isoformat(),
            'scope':'selected-stage replay proof; excluded from full-task A/B aggregates',
            'status':'collected'})
        return
    lock=(root.parent/'geometry-global-window.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX)
    pending=0
    for directory in root.parent.glob('geometry-*-1006'):
        if not (directory/'suite.json').exists():continue
        active=False
        if (directory/'controller.pid').exists():
            try:
                argv=Path('/proc',str(int((directory/'controller.pid').read_text())),'cmdline').read_bytes().split(b'\0')
                active=b'scripts/atomic/run_suite.py' in argv
            except (FileNotFoundError,ValueError):pass
        for c in json.loads((directory/'suite.json').read_text())['cases']:
            path=directory/'runs'/c['id'];planpath=path/'run_plan.json'
            submitted=planpath.exists() and bool(json.loads(planpath.read_text()).get('submitted'))
            pending+=int(not(path/'collection_finished.json').exists() and (active or submitted))
    pending+=sum(not(path.parent/'collection_finished.json').exists()
                 for path in root.parent.glob('*asset-calibration*-1006/control.json'))
    if pending>=32:raise RuntimeError('global 32-job window has no free slot')
    frozen=read_frozen_case(run,case['program'],case['task']);planpath=run/'run_plan.json'
    plan=json.loads(planpath.read_text())
    if plan.get('submitted'):raise ValueError('validation job already submitted; resume monitor instead')
    spec=json.loads((run/(plan['jobs'][0]+'.atomic-job-spec.json')).read_text())
    provenance=json.loads((run/'atomic_settings.json').read_text())
    ident=submit_prepared(planpath,spec,run/'robodojo-overlay.tar.gz',frozen['overlay_sha256'],a.credentials_file,provenance)
    with (run/'controller-monitor.log').open('a') as log:
        child=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'monitor','--root',str(root),
            '--credentials-file',str(a.credentials_file),'--gpu-memory-ledger',str(a.gpu_memory_ledger)],
            cwd=REPO,stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,start_new_session=True)
    atomic_write_json(root/'control.json',{'job':ident,'monitor_pid':child.pid,
        'submitted_at':datetime.now(timezone.utc).isoformat(),'global_pending_before_submission':pending})
    print('Submitted prefix proof',ident,'monitor',child.pid,flush=True)


if __name__=='__main__':main()
