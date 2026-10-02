#!/usr/bin/env python3
"""Submit and collect a generated full-task suite with bounded GPU concurrency."""

import argparse
import errno
import hashlib
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import time

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.atomic.audit_scores import audit_report
from scripts.atomic.storage import atomic_write_json, atomic_write_text
from task.atomic.spec import AtomicProgram

TERMINAL = {"Completed", "Succeeded", "Failed", "Stopped", "Cancelled", "Canceled"}
# Existing i4 workflow routes these variants to H200, not this L40S controller.
H200_TASKS = {'fold_clothes_random', 'hang_mugs_random',
              'arrange_largest_number_random', 'stack_blocks_random'}


def overlay_runtime_hash(path):
    """Hash packaged runtime contents independently of each case's input."""
    digest = hashlib.sha256()
    with tarfile.open(path, 'r:gz') as archive:
        for item in sorted(archive.getmembers(), key=lambda m: m.name):
            if not item.isfile() or item.name == 'task/atomic/inputs/program.json':
                continue
            digest.update(item.name.encode() + b'\0')
            digest.update(hashlib.sha256(archive.extractfile(item).read()).digest())
    return digest.hexdigest()


def freeze_case(run, program, task):
    plan = json.loads((run / 'run_plan.json').read_text())
    overlay = run / 'robodojo-overlay.tar.gz'
    spec = run / f"{plan['jobs'][0]}.atomic-job-spec.json"
    frozen = {'task': task, 'program_sha256': hashlib.sha256(Path(program).read_bytes()).hexdigest(),
              'overlay_sha256': hashlib.sha256(overlay.read_bytes()).hexdigest(),
              'spec_sha256': hashlib.sha256(spec.read_bytes()).hexdigest(),
              'runtime_sha256': overlay_runtime_hash(overlay)}
    atomic_write_json(run / 'prepared_case.json', frozen)
    return frozen


def read_frozen_case(run, program, task):
    frozen = json.loads((run / 'prepared_case.json').read_text())
    plan = json.loads((run / 'run_plan.json').read_text())
    paths = {'program_sha256': Path(program), 'overlay_sha256': run / 'robodojo-overlay.tar.gz',
             'spec_sha256': run / f"{plan['jobs'][0]}.atomic-job-spec.json"}
    if frozen['task'] != task or any(hashlib.sha256(path.read_bytes()).hexdigest() != frozen[key]
                                   for key, path in paths.items()):
        raise ValueError('prepared case changed; create a fresh suite rather than rebuilding queued evidence')
    return frozen


def submit_frozen_case(run, program, task, credentials):
    from scripts.atomic.submit_trace import submit_prepared
    frozen = read_frozen_case(run, program, task)
    plan_path = run / 'run_plan.json'
    plan = json.loads(plan_path.read_text())
    patched = json.loads((run / f"{plan['jobs'][0]}.atomic-job-spec.json").read_text())
    provenance = {'mode':'full_task_benchmark', 'task':task,
                  'program_sha256':frozen['program_sha256'], 'runtime_sha256':frozen['runtime_sha256'],
                  'gpu_admission':{'max_used_mib':512, 'reject_compute_processes':True}}
    return submit_prepared(plan_path, patched, run / 'robodojo-overlay.tar.gz',
                           frozen['overlay_sha256'], credentials, provenance)


def validate_suite(manifest):
    """Reject mislabeled A/B controls before reading the scheduler or submitting."""
    cases = manifest['cases']
    ids = [case['id'] for case in cases]
    if not ids or len(set(ids)) != len(ids) or any(not re.fullmatch(r'[a-zA-Z0-9_-]+', name) for name in ids):
        raise ValueError('case IDs must be nonempty, unique directory-safe names')
    programs = []
    for case in cases:
        path = Path(case['program'])
        program = AtomicProgram.load(path)
        if program.task_name != case.get('task', manifest['task']):
            raise ValueError('program task_name does not match case task')
        if program.task_name in H200_TASKS:
            raise ValueError(f'{program.task_name} requires the H200 workflow, not this L40S suite runner')
        if case.get('layout_id', manifest.get('layout_id', 0)) != 0:
            raise ValueError('suite runner supports layout 0 only')
        programs.append(json.loads(path.read_text()))
    if manifest['mode'] == 'paired_native_and_geometrically_conditioned':
        if len(cases) % 2:
            raise ValueError('A/B suite requires adjacent baseline/conditioned pairs')
        for index in range(0, len(cases), 2):
            a, b = cases[index:index + 2]
            baseline, conditioned = programs[index:index + 2]
            append = conditioned.pop('geometric_instruction', None)
            if (a.get('prompt_mode'), b.get('prompt_mode')) != ('baseline', 'conditioned') or a.get('task') != b.get('task'):
                raise ValueError('A/B pair must have the same task and baseline/conditioned order')
            if not append or append != b.get('geometric_prompt_append') or a.get('geometric_prompt_append'):
                raise ValueError('manifest geometric append does not match the program')
            if baseline.get('geometric_instruction') or baseline != conditioned:
                raise ValueError('A/B programs must differ only in geometric_instruction')


def prepare_case(source, destination, name, client, ledger, task=None):
    old = source.name
    old_task = json.loads((source / 'run_plan.json').read_text())['tasks'][0]
    def rename(value):
        if isinstance(value, str):
            return value.replace(old, name).replace(old_task, task or old_task)
        if isinstance(value, list):
            return [rename(v) for v in value]
        if isinstance(value, dict):
            return {rename(k): rename(v) for k, v in value.items()}
        return value
    plan = rename(json.loads((source / "run_plan.json").read_text()))
    spec = rename(json.loads((source / f"{old}-000.job-spec.json").read_text()))
    group = spec["spec"]["affinity"]["allowed_dedicated_node_groups"][0]
    response = client._get(f"/dedicated-node-groups/{group}/nodes")
    response.raise_for_status()
    # Historical memory use is workload evidence, not a permanent node fault.
    # The live admission guard decides whether the allocated GPU is idle.
    excluded = set()
    eligible = []
    for node in response.json():
        status, config = node["status"], node["spec"]
        if (node["metadata"]["id"] not in excluded and config.get("unschedulable") is False
                and config.get("resource", {}).get("gpu", {}).get("product") == "NVIDIA-L40S"
                and status.get("machine_status") == "Healthy"
                and {"Ready", "Healthy"}.issubset(status.get("status", []))
                and (status.get("reserved_status") or {}).get("id") == plan["reservation"]
                and not any(v.get("healthy") is False for v in status.get("component_status", {}).values())):
            eligible.append(node["metadata"]["id"])
    if not eligible:
        raise RuntimeError("no healthy eligible L40S nodes in the reservation")
    destination.mkdir(parents=True, exist_ok=True)
    if not (destination / "code.tar.gz").exists():
        # Source bundles can live on Lustre while review metadata lives in home.
        # Resolve existing symlinks and reuse the immutable archive when possible.
        bundle = (source / "code.tar.gz").resolve(strict=True)
        try:
            os.link(bundle, destination / "code.tar.gz")
        except OSError as error:
            if error.errno != errno.EXDEV:
                raise
            (destination / "code.tar.gz").symlink_to(bundle)
    shutil.copyfile(source / "source_manifest.json", destination / "source_manifest.json")
    plan.update(submitted=[], staged=False, jobs=[name + "-000"], node_ids=eligible)
    for resource in plan.get("resources_by_task", {}).values():
        resource["node_ids"] = eligible
    plan.pop("atomic", None)
    plan.pop("atomic_overlay_sha256", None)
    # All cases write into their own directory and cloud prefix.
    plan["results_s3"] = plan["results_s3"].rsplit("/", 1)[0] + "/" + name
    spec["metadata"]["name"] = name + "-000"
    spec["spec"]["affinity"]["allowed_nodes_in_node_group"] = eligible
    spec["spec"]["reservation_config"]["allow_burst_to_other_reservations"] = False
    (destination / "run_plan.json").write_text(json.dumps(plan, indent=2) + "\n")
    (destination / (name + "-000.job-spec.json")).write_text(json.dumps(spec, indent=2) + "\n")


def summarize(manifest, root):
    rows = []
    scored = 0
    mismatches = 0
    for case in manifest["cases"]:
        run = root / "runs" / case["id"]
        row = {"case_id": case["id"], "conditioned_stage": case["stage"], "kind": case["kind"],
               "run_dir": str(run), "status": "pending", 'task': case.get('task', manifest['task']),
               'prompt_mode': case.get('prompt_mode', 'legacy')}
        if (run / "run_plan.json").exists():
            plan = json.loads((run / "run_plan.json").read_text())
            row["job_id"] = plan["submitted"][0]["id"] if plan["submitted"] else None
        if (run / "eval_report.json").exists():
            report = json.loads((run / "eval_report.json").read_text())
            row.update(status=report["status"], completed_episodes=report["completed_episodes"], errors=report["errors"])
            row["full_task_success"] = [d["success"] for n in report["native_results"]
                                        for d in (n.get("details", {}).values() if isinstance(n.get("details", {}), dict)
                                                  else n["details"])]
            audit_path = run / 'atomic-score-audit.json'
            row["atomic_scores"] = (json.loads(audit_path.read_text()) if audit_path.exists() else audit_report(report))["atomic_episodes"]
            row['policy_prompt_history'] = [d.get('policy_prompt_history', []) for n in report['native_results']
                                            for d in (n.get('details', {}).values() if isinstance(n.get('details', {}), dict) else n['details'])]
            row['contact_instrumentation'] = [d.get('contact_instrumentation') for n in report['native_results']
                                              for d in (n.get('details', {}).values() if isinstance(n.get('details', {}), dict) else n['details'])]
            scored += sum(c["status"] == "reproduced" for a in row["atomic_scores"] for c in a["conditions"].values())
            mismatches += sum(c["status"] == "score_mismatch" for a in row["atomic_scores"]
                              for c in list(a["conditions"].values()) + list(a.get("closest_approach", {}).values()))
        rows.append(row)
    result = {"updated_at": datetime.now(timezone.utc).isoformat(), "task": manifest["task"],
              "mode": manifest["mode"], "cases": rows, "reproduced_event_scores": scored,
              "completed_cases": sum(r["status"] != "pending" for r in rows),
              "score_mismatches": mismatches,
              "benchmark_proof": "pending" if any(r["status"] == "pending" for r in rows) else
                  ("score_audit_failed" if mismatches else "completed_with_infrastructure_failures"
                   if any(r["status"] != "passed" for r in rows) else
                   "end_to_end_verified" if scored else "no_event_scores_observed")}
    atomic_write_json(root / 'benchmark_results.json', result)
    lines = ["# Full-task atomic geometric benchmark", "", f"Task: `{manifest['task']}`. "
             f"Collected {result['completed_cases']} / {len(rows)} cases; reproduced {scored} event scores.", "",
             "Policy task/action failures are valid benchmark outcomes. Infrastructure failures and "
             "unobserved geometric events are reported explicitly; they do not count as geometric passes.", "",
             "| Case | Task | Prompt mode | Pipeline | Full task success | Event scores |",
             "| --- | --- | --- | --- | --- | --- |"]
    for row in rows:
        metrics = []
        for stage in row.get("atomic_scores", []):
            for condition, score in stage["conditions"].items():
                metrics.append(f"{stage['stage_id']}/{condition}: " +
                               (str(score["recorded_result"]["components"]) if score["status"] == "reproduced" else score["status"]))
            for condition, score in stage.get("closest_approach", {}).items():
                if score["status"] == "reproduced":
                    metrics.append(f"{stage['stage_id']}/{condition} closest (diagnostic): {score['recorded_result']['components']}")
        lines.append(f"| {row['case_id']} | {row['task']} | {row['prompt_mode']} | {row['status']} | {row.get('full_task_success', 'pending')} | {'; '.join(metrics) or 'pending'} |")
    atomic_write_text(root / 'benchmark_results.md', '\n'.join(lines) + '\n')
    if manifest['mode'] == 'paired_native_and_geometrically_conditioned':
        from scripts.atomic.report_paired_suite import write_report
        write_report(manifest, result, root)
    return result


def main():
    from leptonai.api.v2.client import APIClient
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--base-run", type=Path, required=True)
    parser.add_argument("--credentials-file", type=Path, required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--max-concurrent", type=int, default=4)
    parser.add_argument("--gpu-memory-ledger", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9-]+", args.name) or not 1 <= args.max_concurrent <= 8:
        parser.error("use a job-name slug and concurrency between one and eight")
    manifest = json.loads(args.suite.read_text())
    validate_suite(manifest)
    base_plan = json.loads((args.base_run / 'run_plan.json').read_text())
    if base_plan.get('seeds') != [0] or base_plan.get('eval_num') != '1':
        parser.error('suite runner currently requires a one-episode seed-0 base plan')
    if any(case.get('layout_id', manifest.get('layout_id', 0)) != 0 for case in manifest['cases']):
        parser.error('suite runner currently supports layout 0 only; metadata cannot select another layout')
    root = args.suite.parent
    client = APIClient()
    runtimes = set()
    for index, case in enumerate(manifest["cases"]):
        run = root / "runs" / case["id"]
        case_task = case.get('task', manifest['task'])
        if (run / 'prepared_case.json').exists():
            runtimes.add(read_frozen_case(run, case['program'], case_task)['runtime_sha256'])
            continue
        if (run / "run_plan.json").exists() and json.loads((run / "run_plan.json").read_text())["submitted"]:
            raise ValueError('submitted legacy case has no frozen preparation; use its original controller version')
        prepare_case(args.base_run, run, f"{args.name}-{index:02d}", client, args.gpu_memory_ledger, task=case_task)
        subprocess.run([sys.executable, "scripts/atomic/submit_trace.py", "--run-dir", str(run),
                        '--task', case_task,
                        "--program", case["program"], "--max-initial-gpu-memory-mib", "512", "--dry-run"],
                       cwd=REPO, check=True, stdout=subprocess.DEVNULL)
        runtimes.add(freeze_case(run, case['program'], case_task)['runtime_sha256'])
    if len(runtimes) != 1:
        raise ValueError('suite cases have different packaged runtimes; prepare a fresh suite')
    summarize(manifest, root)
    if args.dry_run:
        print(f"Prepared {len(manifest['cases'])} cases; maximum concurrent GPUs: {args.max_concurrent}")
        return
    monitors = {}
    infrastructure_failures = 0
    while True:
        active = 0
        pending = []
        for case in manifest["cases"]:
            run = root / "runs" / case["id"]
            plan = json.loads((run / "run_plan.json").read_text())
            if not plan["submitted"]:
                pending.append(case)
                continue
            job_id = plan["submitted"][0]["id"]
            try:
                state = client.job.get(job_id).status.state.value
            except Exception as error:
                print(f"State poll error for {job_id}: {type(error).__name__}", flush=True)
                active += 1
                continue
            if state not in TERMINAL:
                active += 1
            if case["id"] not in monitors and not (run / "collection_finished.json").exists():
                log = (run / "controller-monitor.log").open("a")
                monitors[case["id"]] = subprocess.Popen(
                    [sys.executable, "-u", "scripts/atomic/monitor_trace.py", "--run-dir", str(run),
                     "--credentials-file", str(args.credentials_file), "--gpu-memory-ledger", str(args.gpu_memory_ledger)],
                    cwd=REPO, stdout=log, stderr=subprocess.STDOUT)
                log.close()
        for case_id, process in list(monitors.items()):
            code = process.poll()
            if code is not None:
                (root / "runs" / case_id / "collection_finished.json").write_text(json.dumps({"exit_code": code}) + "\n")
                if code:
                    infrastructure_failures += 1
                del monitors[case_id]
        result = summarize(manifest, root)
        if infrastructure_failures >= 2:
            print("Stopping new submissions after two infrastructure/collection failures; inspect per-case evidence.", flush=True)
            return
        for case in pending[:max(0, args.max_concurrent - active)]:
            run = root / "runs" / case["id"]
            submit_frozen_case(run, case['program'], case.get('task', manifest['task']), args.credentials_file)
            print(f"Submitted full-task case {case['id']}", flush=True)
        if not pending and not monitors and result["completed_cases"] == len(manifest["cases"]):
            print("Suite collected:", root / "benchmark_results.md", flush=True)
            return
        time.sleep(30)


if __name__ == "__main__":
    main()
