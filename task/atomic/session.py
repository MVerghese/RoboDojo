"""Live, event-based evaluation of a single atomic stage in RoboDojo."""

from copy import deepcopy

import numpy as np

from task.atomic.geometry import evaluate_geometry


def _array(value):
    if hasattr(value, "detach"):
        value = value.detach().cpu().numpy()
    return np.asarray(value, dtype=float).reshape(-1)


class AtomicSession:
    def __init__(self, env, stage, env_idx):
        self.env = env
        self.stage = stage
        self.env_idx = env_idx
        self.success = False
        self.results = {}
        self.sample_index = 0
        self.initial_positions = {}
        for condition in stage.geometry:
            event = condition.get("event", {"kind": "stage_success"})
            if event["kind"] in ("first_lift", "first_motion"):
                label = event["label"]
                self.initial_positions[label] = self._object_pose(label)[:3].copy()

    def _object_pose(self, label):
        position, orientation = self.env.scene_manager.layout_manager.get_instance_pose(
            env_idx=self.env_idx, label=label
        )
        if position is None or orientation is None:
            raise ValueError(f"object label {label!r} is unavailable in env {self.env_idx}")
        return np.concatenate((_array(position), _array(orientation)))

    def _resolve(self, selector):
        kind = selector["kind"]
        if kind in ("object_pose", "object_position"):
            pose = self._object_pose(selector["label"])
            return pose if kind == "object_pose" else pose[:3]
        if kind == "robot_ee_pose":
            if selector["arm"] == "nearest":
                target = self._object_pose(selector["label"])[:3]
                candidates = [r for r in self.env.robot_manager.robot_list if r.type == "target"]
                if not candidates:
                    raise ValueError("no target robot arm is available")
                robot = min(
                    candidates,
                    key=lambda r: np.linalg.norm(
                        _array(self.env.robot_manager.get_real_endpose(
                            r, env_idx_list=[self.env_idx], is_relative=True
                        )[self.env_idx])[:3] - target
                    ),
                )
            else:
                robot = next((r for r in self.env.robot_manager.robot_list if r.arm_name == selector["arm"]), None)
            if robot is None:
                raise ValueError(f"unknown robot arm {selector['arm']!r}")
            poses = self.env.robot_manager.get_real_endpose(robot, env_idx_list=[self.env_idx], is_relative=True)
            return _array(poses[self.env_idx])
        if kind == "functional_point":
            lm = self.env.scene_manager.layout_manager
            inst_name = lm.get_instance_name(env_idx=self.env_idx, label=selector["label"])
            if inst_name is None:
                raise ValueError(f"unknown object label {selector['label']!r}")
            points = lm.get_functional_points(
                tag=selector["tag"], type=selector.get("type", "active"),
                config=lm.get_instance_metadata(inst_name=inst_name, env_idx=self.env_idx),
                ret="list", obj_name=inst_name, env_idx=self.env_idx,
            )
            index = int(selector.get("index", 0))
            if not points or index >= len(points):
                raise ValueError(f"functional point {selector['tag']!r} is unavailable")
            return _array(points[index])
        raise ValueError(f"unknown measurement kind {kind!r}")

    def _check_success(self):
        for check in self.stage.success_checks:
            func = (check["name"], deepcopy(check["args"]))
            if self.env.reward_manager.call_func_parser(func, self.env_idx) < 1:
                return False
        return True

    def _event_fired(self, event, success_now):
        kind = event["kind"]
        if kind == "stage_success":
            return success_now
        label = event["label"]
        current = self._object_pose(label)[:3]
        initial = self.initial_positions[label]
        threshold = float(event.get("threshold", 0.01))
        if threshold <= 0:
            raise ValueError("event threshold must be positive")
        if kind == "first_lift":
            return current[2] - initial[2] >= threshold
        if kind == "first_motion":
            return np.linalg.norm(current - initial) >= threshold
        raise ValueError(f"unknown event kind {kind!r}")

    def step(self):
        self.sample_index += 1
        success_now = self._check_success()
        for condition in self.stage.geometry:
            condition_id = condition["id"]
            if condition_id in self.results:
                continue
            event = condition.get("event", {"kind": "stage_success"})
            if not self._event_fired(event, success_now):
                continue
            measured = self._resolve(condition["measurement"])
            reference = self._resolve(condition["reference"]) if condition.get("reference") else None
            result = evaluate_geometry(condition, measured, reference)
            self.results[condition_id] = {
                "slot": condition["slot"],
                "kind": condition["kind"],
                "event": event,
                "sample_index": self.sample_index,
                "measurement": condition["measurement"],
                "ee_contact_proxy": (
                    condition["measurement"]["kind"] == "robot_ee_pose"
                    and event["kind"] in ("first_lift", "first_motion")
                ),
                "result": result.as_dict(),
            }
        self.success = self.success or success_now
        return self.success

    def summary(self):
        passed = sum(item["result"]["passed"] for item in self.results.values())
        total = len(self.stage.geometry)
        return {
            "stage_id": self.stage.id,
            "family": self.stage.family,
            "action_success": self.success,
            "geometry_pass_rate": passed / total if total else None,
            "geometry_observed": len(self.results),
            "geometry_total": total,
            "geometry": self.results,
        }
