#!/usr/bin/env python3
"""Generate one-factor geometric variations for the full pour_balls_into_vase task."""

import argparse
from copy import deepcopy
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from task.atomic.spec import AtomicProgram


TASK_INSTRUCTION = "Pour all seven balls from the cup into the vase. Finish with the cup upright and both robot arms returned to their starting poses."


def generate_cases(base):
    baseline = deepcopy(base)
    baseline["instruction"] = TASK_INSTRUCTION
    cases = [{"id": "baseline", "stage": None, "kind": None, "program": baseline}]
    for stage_index, stage in enumerate(base["stages"]):
        pick = stage["id"] == "pick_cup"
        measurement = {"kind": "robot_ee_pose", "arm": "nearest", "label": "cup"} if pick else {"kind": "object_pose", "label": "cup"}
        reference = {"kind": "object_pose", "label": "cup" if pick else "vase"}
        for kind in ("point", "pose", "relative_displacement", "relative_orientation", "spatial_relation"):
            for setting in range(2):
                offset = ([-0.04 if setting == 0 else 0.04, 0, 0] if pick
                          else [0, 0, 0.15 if setting == 0 else 0.20])
                angle = (-math.pi / 2 if setting == 0 else math.pi / 2) if pick else (math.pi / 2 if setting == 0 else 2 * math.pi / 3)
                orientation = [math.cos(angle / 2), 0, 0, math.sin(angle / 2)] if pick else [math.cos(angle / 2), math.sin(angle / 2), 0, 0]
                frame = "cup" if pick else "vase"
                point_text = f"({offset[0]:.2f}, {offset[1]:.2f}, {offset[2]:.2f}) metres in the {frame}'s local coordinate frame"
                subject = "gripper end-effector link origin" if pick else "cup centre"
                if kind == "point":
                    expected, text = offset, f"Keep the {subject} at the 3D point {point_text}."
                elif kind == "relative_displacement":
                    expected, text = offset, f"Keep the {subject} at displacement {point_text} from the {frame}'s centre."
                elif kind == "pose":
                    expected = {"position": offset, "orientation": orientation}
                    text = f"Keep the {subject} at {point_text}, with orientation quaternion {orientation} relative to the {frame} (w, x, y, z order)."
                elif kind == "relative_orientation":
                    expected = orientation
                    axis = "z" if pick else "x"
                    text = f"Orient the {'gripper end-effector link' if pick else 'cup'} {math.degrees(angle):.0f} degrees about the {frame}'s local {axis} axis relative to the {frame}."
                else:
                    expected = ("left_of" if setting == 0 else "right_of") if pick else "above"
                    text = (f"Keep the gripper end-effector origin at least 2 cm {'left' if setting == 0 else 'right'} of the cup centre along the cup's local x axis."
                            if pick else f"Keep the cup centre at least {offset[2] * 100:.0f} cm above the vase centre along the vase's local z axis.")
                timing = "When first lifting the cup 2.5 cm, " if pick else "When the first ball enters the vase, "
                program = deepcopy(baseline)
                condition = program["stages"][stage_index]["geometry"][0]
                condition.update(kind=kind, measurement=measurement, reference=reference,
                                 expected=expected, tolerance=0.03 if pick else 0.05)
                if kind == "pose":
                    condition["angle_tolerance_rad"] = math.radians(30)
                elif kind == "relative_orientation":
                    condition["tolerance"] = math.radians(30)
                elif kind == "spatial_relation":
                    condition["margin"] = 0.02 if pick else offset[2]
                    condition["tolerance"] = 0.01 if pick else 0.02
                program["instruction"] = TASK_INSTRUCTION + " " + timing + text[0].lower() + text[1:]
                cases.append({"id": f"{stage['id']}_{kind}_{setting}", "stage": stage["id"],
                              "family": stage["family"], "kind": kind, "slot": condition["slot"],
                              "target": expected, "program": program})
    return cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--program", type=Path, default=Path(__file__).resolve().parents[2] / "task/atomic/programs/pour_balls_into_vase.json")
    args = parser.parse_args()
    base = json.loads(args.program.read_text())
    if base["task_name"] != "pour_balls_into_vase" or [s["id"] for s in base["stages"]] != ["pick_cup", "pour_balls"]:
        raise ValueError("generator is grounded specifically in the cup/vase task")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest = {"schema_version": 1, "task": base["task_name"], "layout_id": 0,
                "mode": "uninterrupted_full_task", "cases": [],
                "atomic_actions": [{"stage": s["id"], "family": s["family"], "success_checks": s["success_checks"]} for s in base["stages"]],
                "native_cleanup": ["cup local z axis upright", "both robot arms back to origin"],
                "limitations": ["Grasp measurements are end-effector link proxies, not contact patches.",
                                "Candidate geometry needs live feasibility calibration; policy failure is allowed.",
                                "Points/poses use the named object frame; no hidden world-coordinate conversion is assumed.",
                                "One episode per setting is an integration pilot, not a statistical policy comparison."]}
    for case in generate_cases(base):
        path = args.output_dir / (case["id"] + ".program.json")
        path.write_text(json.dumps(case.pop("program"), indent=2) + "\n")
        AtomicProgram.load(path)
        manifest["cases"].append({**case, "program": str(path.resolve())})
    output = args.output_dir / "suite.json"
    output.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Generated {len(manifest['cases'])} full-task trials: {output}")


if __name__ == "__main__":
    main()
