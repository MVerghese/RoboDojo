#!/usr/bin/env python3
"""Overlay this RoboDojo fork onto a staged i4 Lepton job and record one trace.

First run i4's _submit_closed_loop_eval.py with --dry-run. This script packages
the fork's complete first-party runtime over its bundled RoboDojo image. Use --dry-run here to
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


# Keep the evaluator and its dependencies from the same checkout. Replacing
# only main.py/eval_env.py can leave newer imports absent in the baked image.
# Assets and third-party/submodule installations remain supplied by the image.
RUNTIME_PATHS = ("env", "env_cfg", "src", "task", "utils", "scripts")


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


def build_overlay(fork: Path, output: Path, extra_files: dict[str, Path] | None = None) -> str:
    # Tracked files exclude caches, generated output, and unrelated local data.
    tracked = subprocess.check_output(
        ["git", "-C", str(fork), "ls-files", "-z", "--", *RUNTIME_PATHS]
    ).decode().split("\0")
    entries = {relative: fork / relative for relative in tracked if relative}
    if "src/eval_client/main.py" not in entries:
        raise ValueError("--fork must be a RoboDojo Git checkout with its runtime files tracked")
    for relative, path in (extra_files or {}).items():
        if Path(relative).is_absolute() or ".." in Path(relative).parts or relative in entries:
            raise ValueError(f"invalid or conflicting overlay path: {relative}")
        entries[relative] = path
    with output.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w") as archive:
                for relative, path in sorted(entries.items()):
                    data = path.read_bytes()
                    info = tarfile.TarInfo(relative)
                    info.size = len(data)
                    info.mode = 0o755 if path.stat().st_mode & 0o111 else 0o644
                    archive.addfile(info, io.BytesIO(data))
    return hashlib.sha256(output.read_bytes()).hexdigest()


def patch_overlay_spec(spec: dict, remote: str, digest: str, reservation: str | None) -> dict:
    result = json.loads(json.dumps(spec))
    bootstrap = result["spec"]["container"]["command"][2]
    marker = "tar -xzf /tmp/robodojo-code.tar.gz -C /opt/imaginaire4"
    if bootstrap.count(marker) != 1:
        raise ValueError("unexpected i4 bootstrap; cannot place RoboDojo overlay safely")
    overlay_commands = "\n".join((
        f"s5cmd --endpoint-url https://storage.googleapis.com cp {shlex.quote(remote)} /tmp/robodojo-overlay.tar.gz",
        f"printf '%s  %s\\n' {shlex.quote(digest)} /tmp/robodojo-overlay.tar.gz | sha256sum -c -",
        "tar -xzf /tmp/robodojo-overlay.tar.gz -C /workspace/RoboDojo",
        # These imports are safe before SimulationApp and catch an incomplete
        # runtime overlay before downloading/initializing a GPU policy model.
        "/root/miniconda3/envs/RoboDojo/bin/python -c " + shlex.quote(
            "import sys; sys.path.insert(0, '/workspace/RoboDojo'); "
            "from env.camera_manager.capture.render_sync import add_zero_delay_kit_args; "
            "from task.RoboDojo.task_registry import load_task_class; "
            "print('RoboDojo runtime overlay imports verified')"
        ),
    ))
    result["spec"]["container"]["command"][2] = bootstrap.replace(marker, marker + "\n" + overlay_commands)
    if reservation:
        result["spec"]["reservation_config"] = {
            "reservation_id": reservation,
            "allow_burst_to_other_reservations": True,
        }
    return result


def patch_spec(spec: dict, remote: str, digest: str, task: str, reservation: str | None) -> dict:
    result = patch_overlay_spec(spec, remote, digest, reservation)
    result["spec"]["envs"].extend((
        {"name": "ATOMIC_RECORD_DIR", "value": "/workspace/robodojo-eval-output/traces"},
        {"name": "ATOMIC_RECORD_SPEC", "value": f"/workspace/RoboDojo/task/atomic/programs/{task}.json"},
    ))
    return result


def submit_prepared(plan_path: Path, patched: dict, overlay: Path, digest: str,
                    credentials_file: Path, provenance: dict | None = None) -> str:
    from leptonai.api.v1.types.job import LeptonJob
    from leptonai.api.v2.client import APIClient

    plan = json.loads(plan_path.read_text())
    if plan.get("submitted"):
        raise ValueError("this run plan already has a submitted job")
    job = LeptonJob.model_validate(patched)
    credentials = json.loads(credentials_file.read_text())
    verify_checkpoint(plan["checkpoint"], credentials)
    environment = dict(os.environ)
    environment["AWS_ACCESS_KEY_ID"] = credentials["aws_access_key_id"]
    environment["AWS_SECRET_ACCESS_KEY"] = credentials["aws_secret_access_key"]
    s5cmd = "/lustre/fsw/portfolios/cosmos/projects/cosmos_base_cap/users/mverghese/uv/envs/cosmos-benchmarks-workflow/bin/s5cmd"
    for local in (plan_path.parent / "code.tar.gz", plan_path.parent / "source_manifest.json", overlay):
        subprocess.run(
            [s5cmd, "--endpoint-url", credentials["endpoint_url"], "cp", str(local),
             f"{plan['results_s3']}/{local.name}"],
            env=environment, check=True,
        )
    created = APIClient().job.create(job).model_dump(mode="json", by_alias=True, exclude_none=True)
    job_id = created["metadata"]["id"]
    plan["submitted"] = [{"name": plan["jobs"][0], "id": job_id}]
    plan["staged"] = True
    plan["atomic_overlay_sha256"] = digest
    if provenance is not None:
        plan["atomic"] = provenance
    plan_path.write_text(json.dumps(plan, indent=2) + "\n")
    subprocess.run(
        [s5cmd, "--endpoint-url", credentials["endpoint_url"], "cp", str(plan_path),
         f"{plan['results_s3']}/run_plan.json"],
        env=environment, check=True,
    )
    print(f"Submitted {plan['jobs'][0]}: {job_id}")
    return job_id


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

    LeptonJob.model_validate(patched)
    print(f"Prepared {patched_path} and {overlay} ({overlay.stat().st_size} bytes)")
    if args.dry_run:
        return
    if args.credentials_file is None:
        raise ValueError("--credentials-file is required to upload the source bundles")
    submit_prepared(plan_path, patched, overlay, digest, args.credentials_file,
                    {"mode": "capture", "task": args.task})


if __name__ == "__main__":
    main()
