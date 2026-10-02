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
    """Exploratory target variations, not same-target A/B comparisons."""
    baseline = deepcopy(base)
    baseline["instruction"] = TASK_INSTRUCTION
    cases = [{"id": "baseline", "stage": None, "kind": None, "program": baseline}]
    for stage_index, stage in enumerate(base["stages"]):
        pick = stage["id"] == "pick_cup"
        for kind in ("point", "pose", "relative_displacement", "relative_orientation", "spatial_relation"):
            for setting in range(2):
                contact = pick and kind not in ('pose', 'relative_orientation')
                measurement = ({'kind': 'contact_points', 'arm': 'any', 'label': 'cup', 'min_finger_bodies': 2}
                               if contact else {'kind': 'object_center_pose', 'label': 'cup'})
                frame = 'cup' if contact else 'vase'
                reference = {'kind': 'object_center_pose', 'label': frame}
                offset = ([-0.04 if setting == 0 else 0.04, 0, 0] if contact
                          else [0, 0, 0.15 if setting == 0 else 0.20])
                angle = ((-math.pi / 2 if setting == 0 else math.pi / 2) if pick
                         else (math.pi / 2 if setting == 0 else 2 * math.pi / 3))
                orientation = ([math.cos(angle / 2), 0, 0, math.sin(angle / 2)] if pick
                               else [math.cos(angle / 2), math.sin(angle / 2), 0, 0])
                point_text = f"{offset} metres in the {frame} mesh-bounds-centre frame"
                subject = 'every force-bearing finger contact' if contact else 'cup mesh-bounds centre'
                if kind in ('point', 'relative_displacement'):
                    expected = offset
                    # A band can be feasible for opposing contacts; do not ask
                    # multiple separated finger points to occupy one exact point.
                    text = (f"Keep {subject} at local x {offset[0]} m in the cup mesh-bounds-centre frame, within 0.03 m, with other coordinates unrestricted."
                            if contact and kind == 'relative_displacement'
                            else f"Keep {subject} within {0.03 if contact else 0.05} m of {point_text}.")
                elif kind == 'pose':
                    expected = {'position': offset, 'orientation': orientation}
                    text = f"Keep {subject} within 0.05 m of {point_text}, with cup orientation quaternion {orientation} relative to the vase, within 30 degrees (w, x, y, z order)."
                elif kind == 'relative_orientation':
                    expected = orientation
                    text = f"Keep cup orientation quaternion {orientation} relative to the vase, within 30 degrees (w, x, y, z order)."
                else:
                    expected = ('left_of' if setting == 0 else 'right_of') if contact else 'above'
                    text = (f"Keep every force-bearing finger contact at least 2 cm {'left' if setting == 0 else 'right'} of the cup mesh-bounds centre along its local x axis, with 1 cm tolerance."
                            if contact else f"Keep the cup mesh-bounds centre at least {offset[2] * 100:.0f} cm above the vase mesh-bounds centre along the vase local z axis, with 2 cm tolerance and at least 10 percent overlap of the smaller projected mesh footprint.")
                timing = 'At the first 2.5 cm cup lift, ' if pick else 'When the first whole ball enters the finite vase bounds, '
                program = deepcopy(baseline)
                condition = program['stages'][stage_index]['geometry'][0]
                for field in ('axes', 'relation_scope', 'min_overlap_fraction', 'margin', 'angle_tolerance_rad', 'orientation_axes'):
                    condition.pop(field, None)
                condition.update(kind=kind, measurement=measurement, reference=reference,
                                 expected=expected, tolerance=0.03 if contact else 0.05, track_closest=False)
                condition['slot'] = 'grasp_region' if contact else ('object_pose' if pick else 'source_pour_pose')
                if contact and kind == 'relative_displacement':
                    condition['axes'] = [0]
                if kind == 'pose':
                    condition['angle_tolerance_rad'] = math.radians(30)
                elif kind == 'relative_orientation':
                    condition['tolerance'] = math.radians(30)
                elif kind == 'spatial_relation':
                    condition['margin'] = 0.02 if contact else offset[2]
                    condition['tolerance'] = 0.01 if contact else 0.02
                    if not contact:
                        condition.update(relation_scope='objects', min_overlap_fraction=0.1)
                program['instruction'] = TASK_INSTRUCTION + ' ' + timing + text[0].lower() + text[1:]
                cases.append({'id': f"{stage['id']}_{kind}_{setting}", 'stage': stage['id'],
                              'family': stage['family'], 'kind': kind, 'slot': condition['slot'],
                              'target': expected, 'program': program})
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
                "limitations": ["Grasps use force-bearing finger points; orientation requests refer to the cup frame, not contact points.",
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
