#!/usr/bin/env python3
"""Overlay an atomic program, replay trace, and optional variant onto an i4 job.

Prepare a fresh one-episode task plan using i4's _submit_closed_loop_eval.py
with --dry-run first. This helper supports --dry-run before cloud submission.
"""

import argparse
import hashlib
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from scripts.atomic.submit_trace import build_overlay, patch_overlay_spec, submit_prepared
from task.atomic.spec import AtomicProgram, AtomicTrace, load_variant


def validate_stage_inputs(program, stage_id, trace, variant):
    stage = program.stage(stage_id)
    if variant:
        stage.with_variant(variant)
    selected_index = [item.id for item in program.stages].index(stage_id)
    if trace is None:
        if selected_index != 0:
            raise ValueError("a recorded trace is required after the first atomic stage")
        return
    if trace.task_name != program.task_name:
        raise ValueError("trace task_name does not match atomic program")
    starts = [trace.stage_starts.get(item.id) for item in program.stages[:selected_index + 1]]
    if starts[0] != 0 or any(index is None for index in starts):
        raise ValueError("trace must contain the first stage at zero and every preceding stage boundary")
    if any(a >= b for a, b in zip(starts, starts[1:])):
        raise ValueError("trace stage boundaries must be strictly increasing")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--fork", type=Path, default=REPO)
    parser.add_argument("--program", type=Path, required=True)
    parser.add_argument("--stage", required=True)
    parser.add_argument("--trace", type=Path)
    parser.add_argument("--variant", type=Path)
    parser.add_argument("--reservation")
    parser.add_argument("--credentials-file", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    program = AtomicProgram.load(args.program)
    trace = AtomicTrace.load(args.trace) if args.trace else None
    variant = load_variant(args.variant)
    validate_stage_inputs(program, args.stage, trace, variant)
    plan_path = args.run_dir / "run_plan.json"
    plan = json.loads(plan_path.read_text())
    if plan.get("submitted"):
        raise ValueError("this run plan already has a submitted job")
    if plan.get("tasks") != [program.task_name] or plan.get("eval_num") != "1" or len(plan["jobs"]) != 1:
        raise ValueError("run plan must contain one episode of the program's task")

    inputs = {"task/atomic/inputs/program.json": args.program}
    envs = [
        {"name": "ATOMIC_SPEC", "value": "/workspace/RoboDojo/task/atomic/inputs/program.json"},
        {"name": "ATOMIC_STAGE", "value": args.stage},
    ]
    for name, source in (("trace", args.trace), ("variant", args.variant)):
        if source:
            relative = f"task/atomic/inputs/{name}.json"
            inputs[relative] = source
            envs.append({"name": f"ATOMIC_{name.upper()}", "value": f"/workspace/RoboDojo/{relative}"})
    overlay = args.run_dir / "robodojo-overlay.tar.gz"
    digest = build_overlay(args.fork, overlay, inputs)
    spec = json.loads((args.run_dir / f"{plan['jobs'][0]}.job-spec.json").read_text())
    patched = patch_overlay_spec(
        spec, f"{plan['results_s3']}/robodojo-overlay.tar.gz", digest, args.reservation
    )
    patched["spec"]["envs"].extend(envs)
    patched_path = args.run_dir / f"{plan['jobs'][0]}.atomic-job-spec.json"
    patched_path.write_text(json.dumps(patched, indent=2) + "\n")
    (args.run_dir / "overlay.sha256").write_text(digest + "  robodojo-overlay.tar.gz\n")
    provenance = {
        "mode": "stage", "task": program.task_name, "stage": args.stage,
        "inputs": {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in inputs.items()},
    }
    (args.run_dir / "atomic_settings.json").write_text(json.dumps(provenance, indent=2) + "\n")

    from leptonai.api.v1.types.job import LeptonJob

    LeptonJob.model_validate(patched)
    print(f"Prepared stage {args.stage}: {patched_path} ({overlay.stat().st_size} overlay bytes)")
    if args.dry_run:
        return
    if args.credentials_file is None:
        raise ValueError("--credentials-file is required to upload and submit")
    submit_prepared(plan_path, patched, overlay, digest, args.credentials_file, provenance)


if __name__ == "__main__":
    main()
