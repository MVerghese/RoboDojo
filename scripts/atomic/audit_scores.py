#!/usr/bin/env python3
"""Recompute geometric scores from saved simulator states, optionally for new targets."""

import argparse
import json
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from task.atomic.geometry import evaluate_geometry


TARGET_FIELDS = {"expected", "tolerance", "angle_tolerance_rad", "margin", "half_extents", "min_overlap_fraction"}


def audit_atomic(atomic, variant=None):
    if variant and variant.get("stage_id") != atomic["stage_id"]:
        raise ValueError("counterfactual variant must use the recorded stage")
    overrides = variant.get("conditions", {}) if variant else {}
    conditions = {c["id"]: c for c in atomic.get("conditions", [])}
    if conditions and set(overrides) - set(conditions):
        raise ValueError("counterfactual variant refers to unknown conditions")
    for override in overrides.values():
        if set(override) - TARGET_FIELDS:
            raise ValueError("changing measurements, landmarks, or events requires a new simulator run")
    rows = {}
    for condition_id, item in atomic.get("geometry", {}).items():
        if "measured_state" not in item or "condition" not in item:
            rows[condition_id] = {"status": "missing_raw_evidence"}
            continue
        condition = item["condition"]
        measured, reference = item["measured_state"], item.get("reference_state")
        reproduced = evaluate_geometry(condition, measured, reference).as_dict()
        saved = item["result"]
        matches = reproduced["passed"] == saved["passed"] and all(
            np.isclose(reproduced[k], saved[k], rtol=1e-7, atol=1e-9)
            for k in ("error", "tolerance")
        ) and reproduced["components"].keys() == saved["components"].keys() and all(
            np.isclose(value, saved["components"][key], rtol=1e-7, atol=1e-9)
            for key, value in reproduced["components"].items()
        )
        changed = {**condition, **overrides.get(condition_id, {})}
        rows[condition_id] = {
            "status": "reproduced" if matches else "score_mismatch",
            "recorded_result": reproduced,
            "rescored_result": evaluate_geometry(changed, measured, reference).as_dict(),
            "policy_action_index": item.get("policy_action_index"),
            "measurement_source": item.get("measurement_source"),
            "ee_contact_proxy": item.get("ee_contact_proxy", False),
        }
    for condition_id in conditions.keys() - rows.keys():
        failure = atomic.get('measurement_failures', {}).get(condition_id)
        rows[condition_id] = failure or {"status": "event_not_observed"}
    output = {
        "stage_id": atomic["stage_id"], "instruction": atomic.get("instruction"),
        "action_success": atomic["action_success"],
        "geometry_coverage": atomic["geometry_coverage"],
        "counterfactual_instruction": variant.get("instruction") if variant else None,
        "interpretation": "Rescoring a saved outcome changes the target, not the policy behavior.",
        "conditions": rows,
    }
    if atomic.get("closest_approach"):
        alternate = {**atomic, "geometry": atomic["closest_approach"], "closest_approach": {}}
        output["closest_approach"] = audit_atomic(alternate, variant)["conditions"]
    return output


def audit_report(report, variant=None):
    rows = []
    for native in report.get("native_results", []):
        details = native.get("details", {})
        for episode, detail in (details.items() if isinstance(details, dict) else enumerate(details)):
            if "atomic" in detail:
                rows.append({"episode": str(episode), "layout_id": detail["layout_id"],
                             **audit_atomic(detail["atomic"], variant)})
            for atomic in detail.get("atomic_sequence", {}).get("stages", []):
                rows.append({"episode": str(episode), "layout_id": detail["layout_id"],
                             "reached": atomic["reached"], **audit_atomic(atomic, variant)})
    return {"atomic_episodes": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--variant", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    variant = json.loads(args.variant.read_text()) if args.variant else None
    audit = audit_report(json.loads(args.report.read_text()), variant)
    args.output.write_text(json.dumps(audit, indent=2) + "\n")
    print(args.output)


if __name__ == "__main__":
    main()
