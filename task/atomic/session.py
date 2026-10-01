"""Live, event-based evaluation of a single atomic stage in RoboDojo."""

from copy import deepcopy

import numpy as np

from task.atomic.geometry import evaluate_geometry
from task.atomic.contacts import ContactUnavailable


def _state(value):
    return deepcopy(value) if isinstance(value, dict) else value.tolist()


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
        self.closest_approach = {}
        self.measurement_failures = {}
        self.interaction_observed = False
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
        return self._resolve_with_source(selector)[0]

    def _resolve_with_source(self, selector):
        source = {**selector, "frame": "environment_local_world"}
        kind = selector["kind"]
        if kind in ("object_pose", "object_position"):
            pose = self._object_pose(selector["label"])
            source['landmark'] = 'object root frame origin, not geometric centre'
            return (pose if kind == "object_pose" else pose[:3]), source
        if kind in ('object_center_pose', 'object_center_position'):
            pose = self.env._atomic_surfaces.center_pose(selector['label'], self.env_idx,
                                                       self._object_pose(selector['label']))
            source['landmark'] = 'centre of local mesh bounds, transformed by live rigid-body pose'
            return (pose if kind == 'object_center_pose' else pose[:3]), source
        if kind == 'contact_points':
            contacts = getattr(self.env, '_atomic_contacts', None)
            if contacts is None:
                raise RuntimeError('PhysX contacts were not initialized')
            return contacts.resolve(selector, self.env_idx)
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
            source.update({"resolved_arm": robot.arm_name,
                           "ee_link_name": getattr(robot, "ee_link_name", None)})
            return _array(poses[self.env_idx]), source
        if kind in ('functional_point', 'support_point'):
            lm = self.env.scene_manager.layout_manager
            inst_name = lm.get_instance_name(env_idx=self.env_idx, label=selector["label"])
            if inst_name is None:
                raise ValueError(f"unknown object label {selector['label']!r}")
            resolver = lm.get_functional_points if kind == 'functional_point' else lm.get_support_points
            points = resolver(
                tag=selector["tag"], type=selector.get("type", "active"),
                config=lm.get_instance_metadata(inst_name=inst_name, env_idx=self.env_idx),
                ret="list", obj_name=inst_name, env_idx=self.env_idx,
            )
            if kind == 'support_point':
                points, radii = points
                source['support_radii_m'] = list(radii)
            index = int(selector.get("index", 0))
            if not points or index >= len(points):
                raise ValueError(f"functional point {selector['tag']!r} is unavailable")
            return _array(points[index]), source
        raise ValueError(f"unknown measurement kind {kind!r}")

    def _check_success(self):
        for check in self.stage.success_checks:
            if not self._predicate(check):
                return False
        return True

    def _predicate(self, check):
        if check['name'] in ('is_atomic_entry', 'is_atomic_inserted'):
            from task.atomic.geometry import _rotation
            args = check['args']
            tip = self._resolve({'kind': 'functional_point', 'label': args['label_A'],
                                 'tag': args.get('tip_tag', 'insert'), 'type': 'active'})
            lm = self.env.scene_manager.layout_manager
            metadata = lm.get_instance_metadata(env_idx=self.env_idx, label=args['label_B'])
            for tag in metadata.get('passive', {}).get('support', {}):
                if not tag.startswith('socket/'):
                    continue
                target = self._resolve({'kind': 'support_point', 'label': args['label_B'], 'tag': tag,
                                        'type': 'passive', 'index': 0})
                local = _rotation(target[3:]).T @ (tip[:3] - target[:3])
                angle = np.arccos(np.clip((_rotation(tip[3:])[:, 2] @ _rotation(target[3:])[:, 2]), -1, 1))
                depth = -local[2]
                if (np.linalg.norm(local[:2]) <= args.get('xy_tolerance', 0.012)
                        and args.get('min_depth', 0.0) <= depth <= args.get('max_depth', 0.025)
                        and angle <= np.deg2rad(args.get('angle_tolerance_deg', 30))):
                    return True
            return False
        return self.env.reward_manager.call_func_parser((check['name'], deepcopy(check['args'])), self.env_idx) >= 1

    def _event_fired(self, event, success_now):
        kind = event["kind"]
        if kind == "stage_success":
            return success_now
        if kind == "first_predicate":
            values = (
                self._predicate(check)
                for check in event["checks"]
            )
            return all(values) if event.get("mode", "any") == "all" else any(values)
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

    def _sample(self, success_now):
        self.sample_index += 1
        for condition in self.stage.geometry:
            condition_id = condition["id"]
            if condition_id in self.results or condition_id in self.measurement_failures:
                continue
            event = condition.get("event", {"kind": "stage_success"})
            if not self._event_fired(event, success_now):
                continue
            try:
                measured, measurement_source, reference, reference_source = self._resolve_condition(condition)
            except ContactUnavailable as error:
                self.measurement_failures[condition_id] = {
                    'event': deepcopy(event), 'event_observed': True,
                    'status': 'contact_not_observed_at_event', 'reason': str(error),
                    'policy_action_index': int(self.env.take_action_cnt[self.env_idx]),
                }
                continue
            result = evaluate_geometry(condition, measured, reference)
            if condition['measurement']['kind'] == 'contact_points':
                self.interaction_observed = True
            self.results[condition_id] = {
                "slot": condition["slot"],
                "kind": condition["kind"],
                "event": event,
                "sample_index": self.sample_index,
                "policy_action_index": (
                    int(self.env.take_action_cnt[self.env_idx])
                    if hasattr(self.env, "take_action_cnt") else None
                ),
                "measurement": condition["measurement"],
                "condition": deepcopy(condition),
                "measured_state": _state(measured),
                "reference_state": _state(reference) if reference is not None else None,
                "measurement_source": measurement_source,
                "reference_source": reference_source,
                "ee_contact_proxy": (
                    condition["measurement"]["kind"] == "robot_ee_pose"
                    and event["kind"] in ("first_lift", "first_motion")
                ),
                "result": result.as_dict(),
            }

    def _resolve_condition(self, condition):
        measured, source = self._resolve_with_source(condition['measurement'])
        reference, reference_source = self._resolve_with_source(condition['reference']) if condition.get('reference') else (None, None)
        if condition.get('relation_scope') == 'objects':
            surfaces = self.env._atomic_surfaces
            measured = surfaces.resolve(condition['measurement']['label'], self.env_idx,
                                        self._object_pose(condition['measurement']['label']))
            reference = surfaces.resolve(condition['reference']['label'], self.env_idx,
                                         self._object_pose(condition['reference']['label']))
            source['geometry_representation'] = measured['geometry_representation']
            reference_source['geometry_representation'] = reference['geometry_representation']
            if condition['expected'] == 'on_top':
                from task.atomic.geometry import _rotation
                measured['support_contact'] = self.env._atomic_contacts.has_support_contact(
                    condition['measurement']['label'], condition['reference']['label'], self.env_idx,
                    _rotation(reference['orientation'])[:, 2])
        return measured, source, reference, reference_source

    def observe_events(self):
        """Capture first-lift/motion geometry at physics-step resolution."""
        self._sample(success_now=False)

    def step(self):
        """Evaluate stage success after a policy action chunk."""
        success_now = self._check_success()
        self._sample(success_now)
        # Diagnostic scores for failed attempts, separate from the required event.
        for condition in self.stage.geometry:
            if not condition.get('track_closest', True):
                continue
            try:
                measured, source, reference, _ = self._resolve_condition(condition)
            except ContactUnavailable:
                continue
            result = evaluate_geometry(condition, measured, reference).as_dict()
            old = self.closest_approach.get(condition["id"])
            if old is None or result["error"] < old["result"]["error"]:
                self.closest_approach[condition["id"]] = {
                    "condition": deepcopy(condition), "measured_state": _state(measured),
                    "reference_state": _state(reference) if reference is not None else None,
                    "measurement_source": source, "result": result,
                    "policy_action_index": int(self.env.take_action_cnt[self.env_idx]) if hasattr(self.env, "take_action_cnt") else None,
                    "measurement_context": "closest approach at policy action boundaries; not required-event adherence",
                    "ee_contact_proxy": condition["measurement"]["kind"] == "robot_ee_pose",
                }
        if any(c['measurement']['kind'] == 'contact_points' for c in self.stage.geometry):
            success_now = success_now and self.interaction_observed
        self.success = self.success or success_now
        return self.success

    def check_success_only(self):
        """Advance stage annotation without measuring geometric conditions."""
        self.success = self.success or self._check_success()
        return self.success

    def summary(self):
        passed = sum(item["result"]["passed"] for item in self.results.values())
        total = len(self.stage.geometry)
        observed = len(self.results)
        return {
            "stage_id": self.stage.id,
            "family": self.stage.family,
            "instruction": self.stage.instruction,
            "conditions": deepcopy(list(self.stage.geometry)),
            "coordinate_frame": "environment_local_world",
            "quaternion_order": "wxyz",
            "distance_unit": "metres",
            "angle_unit": "radians",
            "action_success": self.success,
            "geometry_pass_rate": passed / observed if observed else None,
            "geometry_coverage": observed / total if total else None,
            "geometry_observed": observed,
            "geometry_total": total,
            "geometry": self.results,
            "closest_approach": self.closest_approach,
            'measurement_failures': deepcopy(self.measurement_failures),
            'interaction_observed': self.interaction_observed,
            'recognition_checks': deepcopy(list(self.stage.success_checks)),
            'initial_object_positions': {k: v.tolist() for k, v in self.initial_positions.items()},
        }
