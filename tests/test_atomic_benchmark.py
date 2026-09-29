import json
import math
from pathlib import Path
import tempfile
import unittest

import numpy as np

from task.atomic.geometry import evaluate_geometry
from task.atomic.replay import replay_prefix
from task.atomic.session import AtomicSession
from task.atomic.spec import AtomicProgram, AtomicStage, AtomicTrace


class GeometryTests(unittest.TestCase):
    def test_point_and_displacement_use_landmark_frame(self):
        # Landmark yaw = 90 degrees; its local +x is world +y.
        reference = [1, 2, 0, math.sqrt(0.5), 0, 0, math.sqrt(0.5)]
        measured = [1, 2.1, 0]
        for kind in ("point", "relative_displacement"):
            result = evaluate_geometry(
                {"kind": kind, "expected": [0.1, 0, 0], "tolerance": 1e-5}, measured, reference
            )
            self.assertTrue(result.passed)
            self.assertLess(result.error, 1e-5)

    def test_pose_and_orientation_are_quaternion_sign_invariant(self):
        q = [math.sqrt(0.5), 0, 0, math.sqrt(0.5)]
        pose = [0, 0, 0, *[-v for v in q]]
        self.assertTrue(evaluate_geometry(
            {"kind": "pose", "expected": {"position": [0, 0, 0], "orientation": q},
             "tolerance": 0.001, "angle_tolerance_rad": 0.001}, pose
        ).passed)
        self.assertTrue(evaluate_geometry(
            {"kind": "relative_orientation", "expected": q, "tolerance": 0.001}, pose
        ).passed)

    def test_directional_and_volume_relations(self):
        self.assertTrue(evaluate_geometry(
            {"kind": "spatial_relation", "expected": "above", "margin": 0.1, "tolerance": 0.0},
            [0, 0, 0.2],
        ).passed)
        self.assertFalse(evaluate_geometry(
            {"kind": "spatial_relation", "expected": "inside_box", "half_extents": [1, 1, 1],
             "tolerance": 0.01}, [1.1, 0, 0],
        ).passed)


class SpecTests(unittest.TestCase):
    def test_programs_and_variant(self):
        root = Path(__file__).resolve().parents[1] / "task/atomic/programs"
        for path in root.glob("*.json"):
            program = AtomicProgram.load(path)
            self.assertTrue(program.stages)
        program = AtomicProgram.load(root / "push_T.json")
        with (root / "variants/push_T_right_contact.json").open(encoding="utf-8") as stream:
            variant = json.load(stream)
        stage = program.stage("push_t_to_pad").with_variant(variant)
        self.assertEqual(stage.geometry[0]["expected"], [0.05, 0, 0])
        self.assertEqual(stage.success_checks, program.stage("push_t_to_pad").success_checks)

    def test_trace_rejects_boundary_beyond_action_count(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trace.json"
            path.write_text(json.dumps({
                "task_name": "deposit_coin", "layout_id": 3,
                "actions": [{}], "stage_starts": {"insert_coin": 2},
            }))
            with self.assertRaisesRegex(ValueError, "valid action boundaries"):
                AtomicTrace.load(path)

    def test_replay_checks_preceding_stage_at_recorded_boundary(self):
        program = AtomicProgram.load(
            Path(__file__).resolve().parents[1] / "task/atomic/programs/deposit_coin.json"
        )
        trace = AtomicTrace(
            "deposit_coin", 3, ({"step": 0}, {"step": 1}, {"step": 2}),
            {"pick_coin": 0, "insert_coin": 2},
        )
        played = []
        start = replay_prefix(
            program, program.stage("insert_coin"), trace,
            lambda action: played.append(action["step"]),
            lambda stage: played == [0, 1] and stage.id == "pick_coin",
        )
        self.assertEqual((start, played), (2, [0, 1]))
        with self.assertRaisesRegex(ValueError, "replay diverged"):
            replay_prefix(
                program, program.stage("insert_coin"), trace,
                lambda action: None, lambda stage: False,
            )


class _FakeLayout:
    def __init__(self):
        self.position = np.array([0.0, 0.0, 0.0])

    def get_instance_pose(self, env_idx, label):
        return self.position.copy(), np.array([1.0, 0.0, 0.0, 0.0])


class _FakeReward:
    def __init__(self, layout):
        self.layout = layout

    def call_func_parser(self, func, env_idx):
        return float(self.layout.position[2] >= func[1]["z_threshold"])


class _FakeRobot:
    arm_name = "left_arm"
    type = "target"


class _FakeRobotManager:
    robot_list = [_FakeRobot()]

    def get_real_endpose(self, robot, env_idx_list, is_relative):
        return {0: [0.02, 0.0, 0.04, 1, 0, 0, 0]}


class SessionTests(unittest.TestCase):
    def test_grasp_geometry_is_recorded_at_first_lift_not_final_state(self):
        layout = _FakeLayout()
        scene = type("Scene", (), {"layout_manager": layout})()
        env = type("Env", (), {"scene_manager": scene, "robot_manager": _FakeRobotManager(),
                                 "reward_manager": _FakeReward(layout)})()
        stage = AtomicStage.from_dict({
            "id": "pick", "family": "pick", "instruction": "Pick target",
            "success_checks": [{"name": "is_lift", "args": {"z_threshold": 0.1}}],
            "geometry": [{
                "id": "grasp", "slot": "grasp_region", "kind": "relative_displacement",
                "expected": [0.02, 0, 0], "tolerance": 0.001,
                "measurement": {"kind": "robot_ee_pose", "arm": "left_arm"},
                "reference": {"kind": "object_pose", "label": "target"},
                "event": {"kind": "first_lift", "label": "target", "threshold": 0.025},
            }],
        })
        session = AtomicSession(env, stage, 0)
        self.assertFalse(session.step())
        self.assertIsNone(session.summary()["geometry_pass_rate"])
        self.assertEqual(session.summary()["geometry_coverage"], 0.0)
        layout.position[2] = 0.04
        session.observe_events()  # physics step before the policy chunk ends
        self.assertEqual(session.summary()["geometry_observed"], 1)
        self.assertEqual(session.summary()["geometry_coverage"], 1.0)
        self.assertFalse(session.step())
        self.assertEqual(session.summary()["geometry_observed"], 1)
        layout.position[2] = 0.11
        self.assertTrue(session.step())
        self.assertEqual(session.summary()["geometry_observed"], 1)


if __name__ == "__main__":
    unittest.main()
