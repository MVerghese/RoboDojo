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
TERMINAL_STATES = {"Succeeded", "Failed", "Cancelled", "Canceled", "Stopped"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--credentials-file", type=Path, required=True)
    parser.add_argument("--max-hours", type=float, default=24)
    parser.add_argument("--gpu-memory-ledger", type=Path,
                        help="Persistent initial GPU memory log; default: run directory's parent")
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
                return 0 if state == "Succeeded" else 1
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
