"""Release failed older workers after allowing their normal cleanup to finish.

Only an explicit simulator exception in retained logs can trigger a stop. Normal
policy failure, a quiet contact scene and a websocket reconnect cannot do so.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import time

from scripts.atomic.closed_loop_guard import FATAL_MARKER


def aged_exception(snapshot, now_s, grace_s=300):
    timestamps = [int(stamp)/1e9 for stream in snapshot.get('data',{}).get('result',[])
                  for stamp,line in stream.get('values',[]) if FATAL_MARKER in line]
    return min(timestamps) if timestamps and now_s-min(timestamps)>=grace_s else None


def current_job(run):
    path = run/'run_plan.json'
    plan = json.loads(path.read_text()) if path.exists() else {}
    return plan.get('submitted',[{}])[0].get('id') if plan.get('submitted') else None


def check(root, helper, grace_s):
    from leptonai.api.v2.client import APIClient
    client = APIClient()
    for suite in sorted(root.glob('geometry-*-1006')):
        manifest_path = suite/'suite.json'
        if not manifest_path.exists():
            continue
        cases = json.loads(manifest_path.read_text())['cases']
        for case in cases:
            run = suite/'runs'/case['id'];ident = current_job(run)
            if not ident or (run/'collection_finished.json').exists():
                continue
            if client.job.get(ident).status.state.value != 'Running':
                continue
            # The existing helper retains and redacts creation-to-now cloud logs.
            args = [sys.executable,str(helper),'log-snapshot','--suite-name',suite.name,'--case',case['id']]
            snapshot = run/'failure-logs'/'cloud-log-snapshot.json'
            result = subprocess.run(args,capture_output=True,text=True,timeout=60)
            if result.returncode or not snapshot.exists():
                continue
            stamp = aged_exception(json.loads(snapshot.read_text()),time.time(),grace_s)
            if stamp is None or current_job(run)!=ident:
                continue
            if client.job.get(ident).status.state.value != 'Running':
                continue
            # Reuse the helper's explicit retained-proof gate and scoped stop API.
            result = subprocess.run([sys.executable,str(helper),'stop-failed','--suite-name',suite.name,
                '--case',case['id']],capture_output=True,text=True,timeout=60)
            record = {'observed_at':datetime.now(timezone.utc).isoformat(),'suite':suite.name,
                'case':case['id'],'job':ident,'simulator_exception_at_s':stamp,
                'cleanup_grace_s':grace_s,'stop_helper_exit_code':result.returncode,
                'evidence':str(snapshot),'policy_outcome':'unavailable'}
            with (root/'failed-worker-watch-events.jsonl').open('a') as stream:
                stream.write(json.dumps(record)+'\n')
            print(json.dumps(record),flush=True)
        source = suite/'benchmark_results.json'
        if (source.exists() and all((suite/'runs'/c['id']/'collection_finished.json').exists() for c in cases)
                and any(r['status']=='pending' for r in json.loads(source.read_text())['cases'])):
            subprocess.run([sys.executable,str(helper),'reconcile','--suite-name',suite.name],
                           capture_output=True,text=True,timeout=60,check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--helper',type=Path,required=True)
    parser.add_argument('--grace-s',type=float,default=300)
    parser.add_argument('--period-s',type=float,default=120)
    parser.add_argument('--once',action='store_true')
    args = parser.parse_args()
    if args.grace_s<120 or args.period_s<30:
        parser.error('retain at least 120 seconds for cleanup and 30 seconds between checks')
    import fcntl
    lock = (args.root/'failed-worker-watch.lock').open('a+')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    while True:
        try:
            check(args.root,args.helper,args.grace_s)
        except Exception as error:
            print(datetime.now(timezone.utc).isoformat(),'watch failed:',type(error).__name__,str(error),flush=True)
        if args.once:
            break
        time.sleep(args.period_s)


if __name__=='__main__':
    main()
