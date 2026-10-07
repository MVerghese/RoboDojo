import ast
import json
import hashlib
import math
import os
from pathlib import Path
import tempfile
import tarfile
import unittest
from unittest.mock import Mock, patch

import numpy as np

from task.atomic.geometry import evaluate_geometry
from task.atomic.replay import replay_prefix
from task.atomic.session import AtomicSession
from task.atomic.spec import AtomicProgram, AtomicStage, AtomicTrace
from scripts.atomic.submit_stage import validate_stage_inputs
from scripts.atomic.submit_trace import build_overlay, patch_overlay_spec, patch_spec
from scripts.atomic import gpu_admission
from scripts.atomic.gpu_memory_log import record_admission
from scripts.atomic.node_neighbors import collect_node_neighbors, save_node_neighbors, summarize_job
from scripts.atomic.audit_scores import audit_atomic
from scripts.atomic.generate_suite import generate_cases
from task.atomic.sequence import AtomicSequence
from src.eval_client.ws_compat import compatible_client_kwargs


class GeometryTests(unittest.TestCase):
    def test_all_five_kinds_detect_known_target_changes_in_a_rotated_frame(self):
        q = [math.sqrt(0.5), 0, 0, math.sqrt(0.5)]
        reference = [1, 2, 3, *q]
        measured = [1, 2.1, 3.2, *q]  # local position [0.1, 0, 0.2], local orientation identity
        cases = [
            ({"kind": "point", "expected": [0.1, 0, 0.2]},
             {"expected": [0.15, 0, 0.2]}, "position_m", 0.05),
            ({"kind": "relative_displacement", "expected": [0.1, 0, 0.2]},
             {"expected": [0.15, 0, 0.2]}, "displacement_m", 0.05),
            ({"kind": "pose", "expected": {"position": [0.1, 0, 0.2], "orientation": [1, 0, 0, 0]},
              "angle_tolerance_rad": 0.001},
             {"expected": {"position": [0.1, 0, 0.2], "orientation": q}}, "orientation_rad", math.pi / 2),
            ({"kind": "relative_orientation", "expected": [1, 0, 0, 0]},
             {"expected": q}, "orientation_rad", math.pi / 2),
            ({"kind": "spatial_relation", "expected": "above", "margin": 0.15},
             {"expected": "below"}, "relation_error_m", 0.35),
        ]
        for condition, change, component, expected_error in cases:
            with self.subTest(kind=condition["kind"]):
                condition["tolerance"] = 0.001
                self.assertTrue(evaluate_geometry(condition, measured, reference).passed)
                result = evaluate_geometry({**condition, **change}, measured, reference)
                self.assertFalse(result.passed)
                self.assertAlmostEqual(result.components[component], expected_error)

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
    def test_full_task_suite_varies_every_modifier_for_each_action(self):
        base = json.loads((Path(__file__).resolve().parents[1] / "task/atomic/programs/pour_balls_into_vase.json").read_text())
        cases = generate_cases(base)
        self.assertEqual(len(cases), 21)
        self.assertEqual(len({c["id"] for c in cases}), 21)
        for stage in ("pick_cup", "pour_balls"):
            for kind in ("point", "pose", "relative_displacement", "relative_orientation", "spatial_relation"):
                self.assertEqual(len([c for c in cases if c["stage"] == stage and c["kind"] == kind]), 2)
        for case in cases:
            program = case["program"]
            self.assertIn("all seven balls", program["instruction"])
            self.assertIn("cup upright", program["instruction"])
            for original, changed in zip(base["stages"], program["stages"]):
                self.assertEqual(original["success_checks"], changed["success_checks"])
                AtomicStage.from_dict(changed)

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


class SubmissionTests(unittest.TestCase):
    def test_overlay_contains_evaluator_runtime_imports(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            overlay = Path(directory) / "overlay.tar.gz"
            build_overlay(root, overlay)
            with tarfile.open(overlay) as archive:
                names = set(archive.getnames())
                # Regression: main.py imported this module, but the older
                # image did not contain it and the partial overlay omitted it.
                self.assertIn('XPolicyLab/client_server/ws/model_client.py',names)
                self.assertIn('XPolicyLab/client_server/ws/protocol/client.py',names)
                self.assertIn('src/eval_client/checkpoint_client.py', names)
                proof=json.loads(archive.extractfile('task/atomic/pinned-protocol.json').read())
                self.assertEqual(len(proof['xpolicylab_commit']),40)
                data=archive.extractfile('XPolicyLab/client_server/ws/model_client.py').read()
                self.assertEqual(hashlib.sha256(data).hexdigest(),proof['files']['XPolicyLab/client_server/ws/model_client.py'])
                self.assertIn("env/camera_manager/capture/render_sync.py", names)
                self.assertIn("env_cfg/arx_x5.yml", names)
                self.assertIn("task/RoboDojo/config/pour_balls_into_vase.yml", names)
                for name in names:
                    if not name.endswith(".py"):
                        continue
                    tree = ast.parse(archive.extractfile(name).read(), filename=name)
                    modules = []
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Import):
                            modules.extend(alias.name for alias in node.names)
                        elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
                            modules.append(node.module)
                    for module in modules:
                        if module.split(".")[0] not in {"env", "env_cfg", "src", "task", "utils", "scripts"}:
                            continue
                        relative = module.replace(".", "/")
                        for candidate in (relative + ".py", relative + "/__init__.py"):
                            if (root / candidate).is_file():
                                self.assertIn(candidate, names, f"{name} imports missing {module}")

    def test_later_stage_requires_matching_trace_and_preceding_boundaries(self):
        program = AtomicProgram.load(
            Path(__file__).resolve().parents[1] / "task/atomic/programs/deposit_coin.json"
        )
        validate_stage_inputs(program, "pick_coin", None, None)
        with self.assertRaisesRegex(ValueError, "recorded trace"):
            validate_stage_inputs(program, "insert_coin", None, None)
        valid = AtomicTrace("deposit_coin", 3, ({}, {}), {"pick_coin": 0, "insert_coin": 1})
        validate_stage_inputs(program, "insert_coin", valid, None)
        mismatched = AtomicTrace("other_task", 3, valid.actions, valid.stage_starts)
        with self.assertRaisesRegex(ValueError, "task_name"):
            validate_stage_inputs(program, "insert_coin", mismatched, None)
        same_boundary = AtomicTrace("deposit_coin", 3, valid.actions, {"pick_coin": 0, "insert_coin": 0})
        with self.assertRaisesRegex(ValueError, "strictly increasing"):
            validate_stage_inputs(program, "insert_coin", same_boundary, None)

    def test_overlay_preserves_replay_payload_and_base_job(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            trace = Path(directory) / "trace.json"
            trace.write_text('{"layout_id": 17, "actions": [{"left_arm": [0.1]}]}\n')
            overlay = Path(directory) / "overlay.tar.gz"
            digest = build_overlay(root, overlay, {"task/atomic/inputs/trace.json": trace})
            with tarfile.open(overlay) as archive:
                self.assertEqual(archive.extractfile("task/atomic/inputs/trace.json").read(), trace.read_bytes())
            with self.assertRaisesRegex(ValueError, "overlay path"):
                build_overlay(root, overlay, {"../trace.json": trace})
        base = {"spec": {
            "container": {"command": ["bash", "-lc", "tar -xzf /tmp/robodojo-code.tar.gz -C /opt/imaginaire4\nexec runner"]},
            "envs": [{"name": "CHECKPOINT", "value": "model"}],
            "queue_config": {"priority_class": "high-8000"},
        }}
        patched = patch_overlay_spec(base, "s3://bucket/overlay.tar.gz", digest, "reservation")
        self.assertNotIn("reservation_config", base["spec"])
        self.assertEqual(patched["spec"]["envs"], base["spec"]["envs"])
        self.assertEqual(patched["spec"]["queue_config"], base["spec"]["queue_config"])
        self.assertEqual(patched["spec"]["reservation_config"]["reservation_id"], "reservation")
        self.assertTrue(patched["spec"]["container"]["command"][2].endswith("exec runner"))
        self.assertIn('export ROBODOJO_POLICY_API=checkpoint_infer', patched['spec']['container']['command'][2])


class GpuAdmissionTests(unittest.TestCase):
    @staticmethod
    def snapshot(used_mib, processes=()):
        return {"observed_at": "2026-10-01T16:00:00Z",
                "gpus": [{"index": 0, "uuid": "GPU-test", "used_mib": used_mib, "total_mib": 46068}],
                "compute_processes": list(processes)}

    def test_occupied_gpu_does_not_start_workload_and_persists_rejection(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.dict(os.environ, {"EVAL_OUTPUT_DIR": directory, "RESULTS_S3": ""}), \
                patch.object(gpu_admission, "read_snapshot", return_value=self.snapshot(6699)), \
                patch.object(gpu_admission.os, "execvp") as execute:
            self.assertEqual(gpu_admission.main(["--max-used-mib", "512", "--", "timeout", "2400", "capture"]), 78)
            execute.assert_not_called()
            report = json.loads((Path(directory) / "eval_report.json").read_text())
            self.assertEqual(report["completed_episodes"], 0)
            self.assertEqual(report["failure_kind"], "gpu_admission_rejected")
            self.assertIn("6699 MiB", report["errors"][0])

    def test_idle_gpu_starts_workload_after_two_samples(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.dict(os.environ, {"EVAL_OUTPUT_DIR": directory, "RESULTS_S3": ""}), \
                patch.object(gpu_admission, "read_snapshot", return_value=self.snapshot(1)) as sample, \
                patch.object(gpu_admission.time, "sleep"), \
                patch.object(gpu_admission.os, "execvp") as execute:
            self.assertEqual(gpu_admission.main(["--max-used-mib", "512", "--", "timeout", "2400", "capture"]), 0)
            self.assertEqual(sample.call_count, 2)
            execute.assert_called_once_with("timeout", ["timeout", "2400", "capture"])
            admission = json.loads((Path(directory) / "gpu_admission.json").read_text())
            self.assertTrue(admission["admitted"])

    def test_existing_process_is_rejected_even_below_memory_allowance(self):
        sample = self.snapshot(225, [{"gpu_uuid": "GPU-test", "pid": "42", "used_mib": "225"}])
        self.assertIn("compute process", gpu_admission.rejection_reason(sample, 512))

    def test_admission_guard_wraps_native_timeout_without_changing_allocation(self):
        base = {"spec": {"container": {"command": ["bash", "-lc",
                "tar -xzf /tmp/robodojo-code.tar.gz -C /opt/imaginaire4\nexec timeout 10800 bash run.sh"]},
                "envs": [], "resource_shape": "my.1xl40s"}}
        guarded = patch_spec(base, "s3://bucket/overlay", "sha", "pour_balls_into_vase", None, 512)
        self.assertEqual(guarded["spec"]["resource_shape"], "my.1xl40s")
        self.assertIn("gpu_admission.py --max-used-mib 512 -- timeout 10800 bash run.sh",
                      guarded["spec"]["container"]["command"][2])

    def test_gpu_counts_deduplicate_monitor_restarts_and_distinguish_placements(self):
        admission = {"max_used_mib": 512, "admitted": False, "samples": [self.snapshot(20404)]}
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / "gpu-memory.jsonl"
            for _ in range(2):
                summary = record_admission(ledger, "job-1", "replica-1", "node-a", admission, "source")
            self.assertEqual(summary["affected_placements"], 1)
            self.assertEqual(summary["affected_unique_gpus"], 1)
            summary = record_admission(ledger, "job-2", "replica-2", "node-a", admission, "source")
            self.assertEqual(summary["affected_placements"], 2)
            self.assertEqual(summary["affected_unique_gpus"], 1)


class NodeNeighborTests(unittest.TestCase):
    def test_contact_summary_excludes_commands_and_unrelated_secrets(self):
        job = {"metadata": {"owner": "owner@example.com", "created_by": "creator@example.com"},
               "spec": {"container": {"command": ["secret command"]},
                        "envs": [{"name": "AWS_SECRET_ACCESS_KEY", "value": "private-value"},
                                 {"name": "CUDA_VISIBLE_DEVICES", "value": "0"}]}}
        summary = summarize_job(job)
        self.assertEqual(summary["owner"], "owner@example.com")
        self.assertIsNone(summary["privileged"])
        self.assertEqual(summary["gpu_scope_envs_in_job_spec"], {"CUDA_VISIBLE_DEVICES": "0"})
        self.assertNotIn("private-value", json.dumps(summary))
        self.assertNotIn("secret command", json.dumps(summary))

    def test_neighbors_retain_unreadable_jobs_and_do_not_assign_gpu_ownership(self):
        client = Mock()
        client._get.return_value.json.return_value = [{"metadata": {"id": "node-a"},
            "status": {"workloads": [
                {"type": "job", "id": "ours", "replica_id": "ours-0", "gpu_count": 1},
                {"type": "job", "id": "neighbor", "replica_id": "neighbor-0", "gpu_count": 1},
                {"type": "job", "id": "unreadable", "replica_id": "unreadable-0", "gpu_count": 2}]}}]
        def get_job(job_id):
            if job_id == "unreadable":
                raise RuntimeError("private error body")
            model = Mock()
            model.model_dump.return_value = {"metadata": {"owner": job_id + "@example.com"},
                "spec": {"user_security_context": {"privileged": True}}}
            return model
        client.job.get.side_effect = get_job
        admission = {"samples": [GpuAdmissionTests.snapshot(6699)]}
        snapshot = collect_node_neighbors(client, ["group-a"], "node-a", "ours", "ours-0", admission)
        self.assertEqual(len(snapshot["workloads"]), 3)
        self.assertTrue(snapshot["workloads"][0]["is_our_job"])
        self.assertEqual(snapshot["workloads"][1]["owner"], "neighbor@example.com")
        self.assertTrue(snapshot["workloads"][1]["privileged"])
        self.assertEqual(snapshot["workloads"][2]["lookup_error"], "RuntimeError")
        self.assertNotIn("private error body", json.dumps(snapshot))
        self.assertNotIn("gpu_uuid", snapshot["workloads"][1])
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / "neighbors.jsonl"
            save_node_neighbors(ledger, snapshot)
            save_node_neighbors(ledger, snapshot)
            self.assertEqual(len(ledger.read_text().splitlines()), 1)
            report = ledger.with_suffix(".md").read_text()
            self.assertIn("neighbor@example.com", report)
            self.assertNotIn("ours@example.com", report)


class ClientCompatibilityTests(unittest.TestCase):
    def test_legacy_client_keeps_identity_and_rejects_unsupported_custom_options(self):
        # Signature from XPolicyLab fe71eb5, baked in the existing eval image.
        class LegacyClient:
            def __init__(self, *, url, evaluation_id, trial_id, action_case_id=None,
                         repeat_index=None, client=None):
                self.identity = (url, evaluation_id, trial_id, action_case_id, repeat_index)

        options = dict(url="ws://localhost:9990", evaluation_id="eval-1", trial_id="trial-2",
                       action_case_id="pour", repeat_index=3,
                       ws_ping_interval_s=20.0, ws_ping_timeout_s=20.0)
        client = LegacyClient(**compatible_client_kwargs(LegacyClient, **options))
        self.assertEqual(client.identity, ("ws://localhost:9990", "eval-1", "trial-2", "pour", 3))
        with self.assertRaisesRegex(ValueError, "does not support ws_ping_timeout_s"):
            compatible_client_kwargs(LegacyClient, **dict(options, ws_ping_timeout_s=None))
        with self.assertRaises(TypeError):
            compatible_client_kwargs(LegacyClient, **dict(options, unknown_option=1))

    def test_current_client_preserves_requested_keepalive_options(self):
        class CurrentClient:
            def __init__(self, *, url, evaluation_id, trial_id, ws_ping_interval_s=20.0,
                         ws_ping_timeout_s=20.0):
                self.keepalive = (ws_ping_interval_s, ws_ping_timeout_s)

        options = dict(url="ws://localhost:9990", evaluation_id="eval-1", trial_id="trial-2",
                       ws_ping_interval_s=15.0, ws_ping_timeout_s=None)
        self.assertEqual(compatible_client_kwargs(CurrentClient, **options), options)
        self.assertEqual(CurrentClient(**options).keepalive, (15.0, None))


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
    ee_link_name = "gripper_origin"


class _FakeRobotManager:
    robot_list = [_FakeRobot()]

    def get_real_endpose(self, robot, env_idx_list, is_relative):
        return {0: [0.02, 0.0, 0.04, 1, 0, 0, 0]}


class _FakeContacts:
    def __init__(self):
        self.steps = 0

    def resolve(self, selector, env_idx):
        return {'position': [0.02, 0, 0.04], 'points': [[0.02, 0, 0.04]]}, {
            'kind': 'contact_points', 'resolved_arm': 'left_arm', 'finger_bodies': ['finger1', 'finger2'],
            'physics_step': self.steps}


class SessionTests(unittest.TestCase):
    def test_full_task_sequence_scores_stages_without_ending_native_episode(self):
        layout = _FakeLayout()
        env = type("Env", (), {"scene_manager": type("Scene", (), {"layout_manager": layout})(),
                                 "robot_manager": _FakeRobotManager(), "reward_manager": _FakeReward(layout),
                                 "take_action_cnt": [0], "success": [False], "end_flag": [False],
                                 '_atomic_contacts': _FakeContacts()})()
        def stage(name, height):
            return AtomicStage.from_dict({"id": name, "family": "pick" if name == "pick" else "pour",
                "instruction": name, "success_checks": [{"name": "is_lift", "args": {"z_threshold": height}}],
                'recognition': ({'kind': 'finger_contact_motion', 'label': 'cup', 'arm': 'any',
                                 'motion_threshold_m': .025, 'min_contact_steps': 2} if name == 'pick' else None),
                "geometry": [{"id": "height", "slot": "source", "kind": "point", "expected": [0, 0, height],
                              "tolerance": 0.005, "measurement": {"kind": "object_position", "label": "cup"},
                              "event": {"kind": "stage_success"}}]})
        sequence = AtomicSequence(env, AtomicProgram("pour_test", (stage("pick", 0.05), stage("pour", 0.2)), "Full task"), 0)
        sequence.step(1)
        before = sequence.summary()
        self.assertFalse(before["stages"][1]["reached"])
        self.assertEqual(before["stages"][0]["geometry_coverage"], 0)
        self.assertEqual(audit_atomic(before["stages"][0])["conditions"]["height"]["status"], "event_not_observed")
        self.assertIn("closest_approach", audit_atomic(before["stages"][0]))
        layout.position[2] = 0.05
        env._atomic_contacts.steps += 1
        env.take_action_cnt[0] = 45
        sequence.step(45)
        self.assertEqual(sequence.stage_starts, {"pick": 0, "pour": 45})
        layout.position[2] = 0.2
        env.take_action_cnt[0] = 90
        sequence.step(90)
        complete = sequence.summary()
        self.assertTrue(all(s["action_success"] for s in complete["stages"]))
        self.assertTrue(all(s["geometry_coverage"] == 1 for s in complete["stages"]))
        self.assertEqual(env.end_flag, [False])
        self.assertEqual(env.success, [False])
        self.assertIsNone(sequence.session)

    def test_grasp_geometry_is_recorded_at_first_lift_not_final_state(self):
        layout = _FakeLayout()
        scene = type("Scene", (), {"layout_manager": layout})()
        env = type("Env", (), {"scene_manager": scene, "robot_manager": _FakeRobotManager(),
                                 "reward_manager": _FakeReward(layout), '_atomic_contacts': _FakeContacts()})()
        stage = AtomicStage.from_dict({
            "id": "pick", "family": "pick", "instruction": "Pick target",
            'recognition': {'kind': 'finger_contact_motion', 'label': 'target', 'arm': 'any',
                            'motion_threshold_m': .025, 'min_contact_steps': 2},
            "success_checks": [{"name": "is_lift", "args": {"z_threshold": 0.1}}],
            "geometry": [{
                "id": "grasp", "slot": "grasp_region", "kind": "relative_displacement",
                "expected": [0.02, 0, 0], "tolerance": 0.001,
                "measurement": {"kind": "contact_points", "label": "target", "arm": "left_arm"},
                "reference": {"kind": "object_pose", "label": "target"},
                "event": {"kind": "first_lift", "label": "target", "threshold": 0.025},
            }],
        })
        session = AtomicSession(env, stage, 0)
        self.assertFalse(session.step())
        self.assertIsNone(session.summary()["geometry_pass_rate"])
        self.assertEqual(session.summary()["geometry_coverage"], 0.0)
        layout.position[2] = 0.04
        env._atomic_contacts.steps += 1
        session.observe_events()  # physics step before the policy chunk ends
        self.assertEqual(session.summary()["geometry_observed"], 1)
        self.assertEqual(session.summary()["geometry_coverage"], 1.0)
        saved = session.summary()["geometry"]["grasp"]
        self.assertEqual(saved["measured_state"], {'position': [0.02, 0, 0.04], 'points': [[0.02, 0, 0.04]]})
        self.assertEqual(saved["reference_state"], [0, 0, 0.04, 1, 0, 0, 0])
        self.assertEqual(saved["measurement_source"]["resolved_arm"], "left_arm")
        self.assertEqual(saved["measurement_source"]["finger_bodies"], ['finger1', 'finger2'])
        self.assertFalse(saved['ee_contact_proxy'])
        own = audit_atomic(session.summary())["conditions"]["grasp"]
        self.assertEqual(own["status"], "reproduced")
        self.assertTrue(own["rescored_result"]["passed"])
        changed = audit_atomic(session.summary(), {"stage_id": "pick", "conditions": {
            "grasp": {"expected": [-0.02, 0, 0]}}})["conditions"]["grasp"]
        self.assertFalse(changed["rescored_result"]["passed"])
        self.assertAlmostEqual(changed["rescored_result"]["error"], 0.04)
        with self.assertRaisesRegex(ValueError, "requires a new simulator run"):
            audit_atomic(session.summary(), {"stage_id": "pick", "conditions": {
                "grasp": {"reference": {"kind": "object_pose", "label": "other"}}}})
        self.assertFalse(session.step())
        self.assertEqual(session.summary()["geometry_observed"], 1)
        layout.position[2] = 0.11
        env._atomic_contacts.steps += 1
        self.assertTrue(session.step())
        self.assertEqual(session.summary()["geometry_observed"], 1)

    def test_first_predicate_captures_geometry_before_stage_success(self):
        layout = _FakeLayout()
        scene = type("Scene", (), {"layout_manager": layout})()
        env = type("Env", (), {"scene_manager": scene, "robot_manager": _FakeRobotManager(),
                                 "reward_manager": _FakeReward(layout)})()
        stage = AtomicStage.from_dict({
            "id": "pour", "family": "pour", "instruction": "Pour balls",
            "success_checks": [{"name": "is_lift", "args": {"z_threshold": 0.2}}],
            "geometry": [{
                "id": "cup_height", "slot": "source_pour_pose", "kind": "point",
                "expected": [0, 0, 0.06], "tolerance": 0.01,
                "measurement": {"kind": "object_position", "label": "cup"},
                "event": {"kind": "first_predicate", "checks": [
                    {"name": "is_lift", "args": {"z_threshold": 0.05}}
                ]},
            }],
        })
        session = AtomicSession(env, stage, 0)
        layout.position[2] = 0.06
        session.observe_events()
        self.assertFalse(session.step())
        self.assertEqual(session.summary()["geometry_pass_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
