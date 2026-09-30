#!/usr/bin/env python3
"""Overlay this RoboDojo fork onto a staged i4 Lepton job and record one trace.

First run i4's _submit_closed_loop_eval.py with --dry-run. This script packages
only the fork files needed by its bundled RoboDojo image. Use --dry-run here to
review the patched job spec before uploading or submitting it.
"""

import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import shlex
import subprocess
import tarfile
from urllib.parse import urlparse


BENCHMARK_FILES = (
    "scripts/eval_policy.sh",
    "scripts/robodojo.sh",
    "src/eval_client/eval_env.py",
    "src/eval_client/main.py",
)


def verify_checkpoint(checkpoint: str, credentials: dict) -> None:
    """Fail before submitting a GPU job when its DCP model is unavailable."""
    parsed = urlparse(checkpoint)
    if parsed.scheme != "s3" or not parsed.netloc or not parsed.path.strip("/"):
        raise ValueError("trace capture requires a full s3:// checkpoint prefix")
    import boto3

    client = boto3.client(
        "s3",
        endpoint_url=credentials["endpoint_url"],
        aws_access_key_id=credentials["aws_access_key_id"],
        aws_secret_access_key=credentials["aws_secret_access_key"],
        region_name=credentials["region_name"],
    )
    key = f"{parsed.path.strip('/')}/model/.metadata"
    try:
        client.head_object(Bucket=parsed.netloc, Key=key)
    except Exception as error:
        raise RuntimeError(
            f"checkpoint model metadata is unavailable at s3://{parsed.netloc}/{key}"
        ) from error


def build_overlay(fork: Path, output: Path) -> str:
    files = [fork / relative for relative in BENCHMARK_FILES]
    files.extend(path for path in (fork / "task/atomic").rglob("*") if path.is_file() and "__pycache__" not in path.parts)
    with output.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w") as archive:
                for path in sorted(files):
                    relative = path.relative_to(fork).as_posix()
                    data = path.read_bytes()
                    info = tarfile.TarInfo(relative)
                    info.size = len(data)
                    info.mode = 0o755 if path.stat().st_mode & 0o111 else 0o644
                    archive.addfile(info, io.BytesIO(data))
    return hashlib.sha256(output.read_bytes()).hexdigest()


def patch_spec(spec: dict, remote: str, digest: str, task: str, reservation: str | None) -> dict:
    result = json.loads(json.dumps(spec))
    bootstrap = result["spec"]["container"]["command"][2]
    marker = "tar -xzf /tmp/robodojo-code.tar.gz -C /opt/imaginaire4"
    if bootstrap.count(marker) != 1:
        raise ValueError("unexpected i4 bootstrap; cannot place RoboDojo overlay safely")
    overlay_commands = "\n".join((
        f"s5cmd --endpoint-url https://storage.googleapis.com cp {shlex.quote(remote)} /tmp/robodojo-overlay.tar.gz",
        f"printf '%s  %s\\n' {shlex.quote(digest)} /tmp/robodojo-overlay.tar.gz | sha256sum -c -",
        "tar -xzf /tmp/robodojo-overlay.tar.gz -C /workspace/RoboDojo",
    ))
    result["spec"]["container"]["command"][2] = bootstrap.replace(marker, marker + "\n" + overlay_commands)
    result["spec"]["envs"].extend((
        {"name": "ATOMIC_RECORD_DIR", "value": "/workspace/robodojo-eval-output/traces"},
        {"name": "ATOMIC_RECORD_SPEC", "value": f"/workspace/RoboDojo/task/atomic/programs/{task}.json"},
    ))
    if reservation:
        result["spec"]["reservation_config"] = {
            "reservation_id": reservation,
            "allow_burst_to_other_reservations": True,
        }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--fork", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--task", default="pour_balls_into_vase")
    parser.add_argument("--reservation", help="Existing Lepton reservation ID for the capture job")
    parser.add_argument("--credentials-file", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    plan_path = args.run_dir / "run_plan.json"
    plan = json.loads(plan_path.read_text())
    if plan.get("submitted"):
        raise ValueError("this run plan already has a submitted job")
    if plan.get("tasks") != [args.task] or plan.get("eval_num") != "1":
        raise ValueError("run plan must contain exactly one episode of the selected task")
    spec_path = args.run_dir / f"{plan['jobs'][0]}.job-spec.json"
    spec = json.loads(spec_path.read_text())
    overlay = args.run_dir / "robodojo-overlay.tar.gz"
    digest = build_overlay(args.fork, overlay)
    remote = f"{plan['results_s3']}/robodojo-overlay.tar.gz"
    patched = patch_spec(spec, remote, digest, args.task, args.reservation)
    patched_path = args.run_dir / f"{plan['jobs'][0]}.atomic-job-spec.json"
    patched_path.write_text(json.dumps(patched, indent=2) + "\n")
    (args.run_dir / "overlay.sha256").write_text(digest + "  robodojo-overlay.tar.gz\n")

    from leptonai.api.v1.types.job import LeptonJob

    job = LeptonJob.model_validate(patched)
    print(f"Prepared {patched_path} and {overlay} ({overlay.stat().st_size} bytes)")
    if args.dry_run:
        return
    if args.credentials_file is None:
        raise ValueError("--credentials-file is required to upload the source bundles")
    credentials = json.loads(args.credentials_file.read_text())
    verify_checkpoint(plan["checkpoint"], credentials)
    environment = dict(os.environ)
    environment["AWS_ACCESS_KEY_ID"] = credentials["aws_access_key_id"]
    environment["AWS_SECRET_ACCESS_KEY"] = credentials["aws_secret_access_key"]
    s5cmd = "/lustre/fsw/portfolios/cosmos/projects/cosmos_base_cap/users/mverghese/uv/envs/cosmos-benchmarks-workflow/bin/s5cmd"
    for local in (args.run_dir / "code.tar.gz", args.run_dir / "source_manifest.json", overlay):
        subprocess.run(
            [s5cmd, "--endpoint-url", "https://storage.googleapis.com", "cp", str(local),
             f"{plan['results_s3']}/{local.name}"],
            env=environment, check=True,
        )

    from leptonai.api.v2.client import APIClient

    created = APIClient().job.create(job).model_dump(mode="json", by_alias=True, exclude_none=True)
    job_id = created["metadata"]["id"]
    plan["submitted"] = [{"name": plan["jobs"][0], "id": job_id}]
    plan["staged"] = True
    plan["atomic_overlay_sha256"] = digest
    plan_path.write_text(json.dumps(plan, indent=2) + "\n")
    subprocess.run(
        [s5cmd, "--endpoint-url", "https://storage.googleapis.com", "cp", str(plan_path),
         f"{plan['results_s3']}/run_plan.json"],
        env=environment, check=True,
    )
    print(f"Submitted {plan['jobs'][0]}: {job_id}")


if __name__ == "__main__":
    main()
