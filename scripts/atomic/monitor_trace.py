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
TERMINAL_STATES = {"Succeeded", "Failed", "Cancelled", "Canceled", "Stopped"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--credentials-file", type=Path, required=True)
    parser.add_argument("--max-hours", type=float, default=24)
    args = parser.parse_args()

    plan = json.loads((args.run_dir / "run_plan.json").read_text())
    if len(plan["submitted"]) != 1 or len(plan["tasks"]) != 1 or len(plan["seeds"]) != 1:
        raise ValueError("monitor requires one submitted task and seed")
    job_id = plan["submitted"][0]["id"]
    task = plan["tasks"][0]
    seed = plan["seeds"][0]
    results = f"{plan['results_s3']}/{task}/seed-{seed}"
    log_path = args.run_dir / "monitor.jsonl"

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
