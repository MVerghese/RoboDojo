#!/usr/bin/env python3
"""Watch a submitted one-episode Lepton trace job and collect its result."""

import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

from leptonai.api.v2.client import APIClient


REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.atomic.gpu_memory_log import record_admission
from scripts.atomic.node_neighbors import collect_node_neighbors, save_node_neighbors
TERMINAL_STATES = {"Completed", "Succeeded", "Failed", "Cancelled", "Canceled", "Stopped"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--credentials-file", type=Path, required=True)
    parser.add_argument("--max-hours", type=float, default=24)
    parser.add_argument("--gpu-memory-ledger", type=Path,
                        help="Persistent initial GPU memory log; default: run directory's parent")
    parser.add_argument("--counterfactual-variant", type=Path,
                        help="After collection, rescore saved states against this alternate target")
    args = parser.parse_args()

    plan = json.loads((args.run_dir / "run_plan.json").read_text())
    if len(plan["submitted"]) != 1 or len(plan["tasks"]) != 1 or len(plan["seeds"]) != 1:
        raise ValueError("monitor requires one submitted task and seed")
    job_id = plan["submitted"][0]["id"]
    task = plan["tasks"][0]
    seed = plan["seeds"][0]
    results = f"{plan['results_s3']}/{task}/seed-{seed}"
    log_path = args.run_dir / "monitor.jsonl"
    ledger = args.gpu_memory_ledger or args.run_dir.parent / "gpu-memory-observations.jsonl"
    admission_logged = not plan.get("atomic", {}).get("gpu_admission")
    if not admission_logged:
        import boto3
        from botocore.config import Config
        from urllib.parse import urlparse

        credentials = json.loads(args.credentials_file.read_text())
        storage = boto3.client(
            "s3", endpoint_url=credentials["endpoint_url"],
            aws_access_key_id=credentials["aws_access_key_id"],
            aws_secret_access_key=credentials["aws_secret_access_key"],
            region_name=credentials["region_name"],
            config=Config(connect_timeout=5, read_timeout=10, retries={"max_attempts": 1}),
        )
        location = urlparse(results)
        admission_key = location.path.strip("/") + "/gpu_admission.json"

    def record(event: dict) -> None:
        event["observed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with log_path.open("a") as output:
            output.write(json.dumps(event) + "\n")
        print(event, flush=True)

    client = APIClient()
    deadline = time.monotonic() + args.max_hours * 3600
    last_state = None
    terminal_at = None
    while time.monotonic() < deadline:
        try:
            status = client.job.get(job_id).model_dump(
                mode="json", by_alias=True, exclude_none=True
            )["status"]
        except Exception as error:
            record({"event": "poll_error", "error": str(error)})
            time.sleep(30)
            continue
        state = status.get("state")
        if state != last_state:
            record({"event": "state", "status": status})
            last_state = state
        if not admission_logged and state != "Queueing":
            try:
                admission = json.loads(storage.get_object(
                    Bucket=location.netloc, Key=admission_key
                )["Body"].read())
                replicas = client.job.get_replicas(job_id)
                replica = max(replicas, key=lambda r: r.metadata.created_at)
                placement = replica.model_dump(mode="json", by_alias=True, exclude_none=True)
                summary = record_admission(
                    ledger, job_id, placement["id"], placement["status"]["node"]["name"],
                    admission, f"{results}/gpu_admission.json",
                )
                (args.run_dir / "gpu_admission.json").write_text(json.dumps(admission, indent=2) + "\n")
                if any(
                    gpu["used_mib"] > admission["max_used_mib"]
                    or any(p["gpu_uuid"] == gpu["uuid"] for p in sample["compute_processes"])
                    for sample in admission["samples"] for gpu in sample["gpus"]
                ):
                    neighbors_path = args.run_dir / "gpu_node_neighbors.json"
                    neighbors = None
                    if neighbors_path.exists():
                        saved = json.loads(neighbors_path.read_text())
                        if (saved["replica_id"] == placement["id"]
                                and saved["incident_observed_at"] == admission["samples"][0]["observed_at"]):
                            neighbors = saved
                    if neighbors is None:
                        job = client.job.get(job_id).model_dump(
                            mode="json", by_alias=True, exclude_none=True)
                        groups = (job["spec"].get("affinity") or {}).get("allowed_dedicated_node_groups", [])
                        neighbors = collect_node_neighbors(
                            client, groups, placement["status"]["node"]["name"], job_id,
                            placement["id"], admission,
                        )
                        neighbors_path.write_text(json.dumps(neighbors, indent=2) + "\n")
                    save_node_neighbors(ledger.parent / "gpu-node-neighbors.jsonl", neighbors)
                    record({"event": "node_neighbors", "evidence": str(neighbors_path),
                            "neighbor_jobs": len([w for w in neighbors["workloads"]
                                                  if w["type"] == "job" and not w["is_our_job"]]),
                            "errors": neighbors["errors"]})
                record({"event": "gpu_admission", "admitted": admission["admitted"],
                        "reason": admission["reason"], "gpu_memory_counts": summary})
                admission_logged = True
            except storage.exceptions.ClientError as error:
                if error.response["Error"]["Code"] not in {"NoSuchKey", "404"}:
                    record({"event": "gpu_admission_fetch_error", "error": str(error)})
            except Exception as error:
                record({"event": "gpu_admission_log_error", "error": str(error)})
        if state in TERMINAL_STATES:
            if terminal_at is None:
                terminal_at = time.monotonic()
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/atomic/collect_trace.py",
                    "--results-s3", results,
                    "--credentials-file", str(args.credentials_file),
                    "--output-dir", str(args.run_dir / "traces"),
                ],
                cwd=REPO,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                record({"event": "collected", "job_state": state, "output": result.stdout.strip()})
                if args.counterfactual_variant:
                    audit = subprocess.run(
                        [sys.executable, "scripts/atomic/audit_scores.py",
                         "--report", str(args.run_dir / "eval_report.json"),
                         "--variant", str(args.counterfactual_variant),
                         "--output", str(args.run_dir / "opposite-target-scores.json")],
                        cwd=REPO, capture_output=True, text=True,
                    )
                    record({"event": "counterfactual_audit", "exit_code": audit.returncode,
                            "output": audit.stdout.strip(), "error": audit.stderr.strip()})
                    if audit.returncode:
                        return audit.returncode
                return 0 if state in {"Completed", "Succeeded"} else 1
            if result.returncode == 2:
                record({"event": "no_trace", "job_state": state, "output": result.stdout.strip(),
                        "error": result.stderr.strip()})
                return 2
            record({
                "event": "collect_retry", "job_state": state,
                "output": result.stdout.strip()[-1000:],
                "error": result.stderr.strip()[-1000:],
            })
            if time.monotonic() - terminal_at > 900:
                return 2
        time.sleep(30)
    record({"event": "monitor_timeout"})
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
