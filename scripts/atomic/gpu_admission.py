#!/usr/bin/env python3
"""Run a capture only when its allocated GPU is idle before policy startup."""

import argparse
import csv
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import time


REJECTED = 78


def read_snapshot():
    def query(fields, kind):
        result = subprocess.run(
            ["nvidia-smi", f"--query-{kind}={fields}", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, check=True, timeout=15,
        )
        return list(csv.reader(io.StringIO(result.stdout), skipinitialspace=True))

    devices = query("index,uuid,memory.used,memory.total", "gpu")
    processes = query("gpu_uuid,pid,process_name,used_gpu_memory", "compute-apps")
    return {
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "gpus": [
            {"index": int(row[0]), "uuid": row[1], "used_mib": int(row[2]), "total_mib": int(row[3])}
            for row in devices if row
        ],
        "compute_processes": [
            {"gpu_uuid": row[0], "pid": row[1], "name": row[2], "used_mib": row[3]}
            for row in processes if row
        ],
    }


def rejection_reason(snapshot, max_used_mib):
    devices = snapshot["gpus"]
    if len(devices) != 1:
        return f"expected one visible allocated GPU, found {len(devices)}"
    gpu = devices[0]
    if gpu["used_mib"] > max_used_mib:
        return f"{gpu['uuid']} already uses {gpu['used_mib']} MiB (limit {max_used_mib} MiB)"
    processes = [p for p in snapshot["compute_processes"] if p["gpu_uuid"] == gpu["uuid"]]
    if processes:
        return f"{gpu['uuid']} already has {len(processes)} compute process(es)"
    return None


def publish_file(path, name):
    prefix = os.environ.get("RESULTS_S3")
    if prefix:
        subprocess.run(
            ["s5cmd", "--endpoint-url", os.environ["S3_ENDPOINT_URL"], "cp", str(path),
             f"{prefix.rstrip('/')}/{name}"], check=True,
        )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-used-mib", type=int, default=512)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if args.max_used_mib < 0 or not command:
        parser.error("a nonnegative memory limit and workload command are required")
    output = Path(os.environ.get("EVAL_OUTPUT_DIR", "/workspace/robodojo-eval-output"))
    output.mkdir(parents=True, exist_ok=True)
    admission = {"max_used_mib": args.max_used_mib, "reject_compute_processes": True, "samples": []}
    reason = None
    try:
        for index in range(2):
            if index:
                time.sleep(2)
            snapshot = read_snapshot()
            admission["samples"].append(snapshot)
            reason = rejection_reason(snapshot, args.max_used_mib)
            if reason:
                break
    except Exception as error:
        reason = f"could not verify allocated GPU: {error}"
    admission["admitted"] = reason is None
    admission["reason"] = reason
    admission_path = output / "gpu_admission.json"
    admission_path.write_text(json.dumps(admission, indent=2) + "\n")
    print("[gpu_admission]", json.dumps(admission), flush=True)
    publish_file(admission_path, "gpu_admission.json")
    if reason:
        report = {
            "schema_version": 1, "run_id": os.environ.get("ROBODOJO_RUN_ID"),
            "status": "failed", "completed_episodes": 0,
            "expected_episodes": os.environ.get("EVAL_NUM", "1"), "native_results": [],
            "errors": [f"GPU admission rejected before policy startup: {reason}"],
            "task": os.environ.get("TASK"), "seed": int(os.environ.get("SEED", "0")),
            "policy": "checkpoint", "failure_kind": "gpu_admission_rejected",
        }
        report_path = output / "eval_report.json"
        report_path.write_text(json.dumps(report, indent=2) + "\n")
        archive_path = output / "gpu-admission-rejected.tar.gz"
        with tarfile.open(archive_path, "w:gz") as archive:
            for path in (admission_path, report_path):
                archive.add(path, arcname=path.name)
        publish_file(archive_path, "results.tar.gz")
        publish_file(report_path, "eval_report.json")
        return REJECTED
    # The existing runner keeps its process groups, timeouts, and result collection.
    os.execvp(command[0], command)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
