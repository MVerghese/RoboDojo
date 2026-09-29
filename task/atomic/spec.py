"""Validated, JSON-serializable definitions of atomic RoboDojo trials."""

from dataclasses import dataclass
import json
from pathlib import Path


FAMILIES = frozenset(
    {
        "pick", "place", "push", "push_with_tool", "pour", "actuate",
        "twist", "insert", "touch_with_tool", "handover", "fold",
    }
)
GEOMETRY_KINDS = frozenset(
    {"point", "pose", "relative_displacement", "relative_orientation", "spatial_relation"}
)
EVENT_KINDS = frozenset({"stage_success", "first_lift", "first_motion", "first_predicate"})
MEASUREMENT_KINDS = frozenset({"object_pose", "object_position", "robot_ee_pose", "functional_point"})


def _read_json(path):
    with Path(path).open(encoding="utf-8") as stream:
        return json.load(stream)


def _validate_selector(selector, name):
    if not isinstance(selector, dict) or selector.get("kind") not in MEASUREMENT_KINDS:
        raise ValueError(f"{name} must have kind in {sorted(MEASUREMENT_KINDS)}")
    if selector["kind"] == "robot_ee_pose":
        if not selector.get("arm"):
            raise ValueError(f"{name}.arm is required for robot_ee_pose")
        if selector["arm"] == "nearest" and not selector.get("label"):
            raise ValueError(f"{name}.label is required when arm is nearest")
    elif not selector.get("label"):
        raise ValueError(f"{name}.label is required for {selector['kind']}")


def _validate_condition(condition):
    if not isinstance(condition, dict) or not condition.get("id") or not condition.get("slot"):
        raise ValueError("each geometry condition needs id and slot")
    if condition.get("kind") not in GEOMETRY_KINDS:
        raise ValueError(f"unsupported geometry kind: {condition.get('kind')}")
    if "expected" not in condition or "tolerance" not in condition:
        raise ValueError(f"condition {condition['id']} needs expected and tolerance")
    _validate_selector(condition.get("measurement"), f"condition {condition['id']}.measurement")
    if condition.get("reference") is not None:
        _validate_selector(condition["reference"], f"condition {condition['id']}.reference")
    event = condition.get("event", {"kind": "stage_success"})
    if not isinstance(event, dict) or event.get("kind") not in EVENT_KINDS:
        raise ValueError(f"condition {condition['id']} has unsupported event")
    if event["kind"] in ("first_lift", "first_motion") and not event.get("label"):
        raise ValueError(f"condition {condition['id']} event needs object label")
    if event["kind"] == "first_predicate":
        checks = event.get("checks")
        if not isinstance(checks, list) or not checks or event.get("mode", "any") not in ("any", "all"):
            raise ValueError(f"condition {condition['id']} first_predicate needs checks and any/all mode")
        for check in checks:
            _validate_check(check)


def _validate_check(check):
    if not isinstance(check, dict) or not isinstance(check.get("name"), str) or not isinstance(check.get("args"), dict):
        raise ValueError("success_checks entries need name and args")
    if not check["name"].startswith("is_"):
        raise ValueError("atomic success checks must be read-only is_* predicates")
    if check["args"].get("update"):
        raise ValueError("atomic success checks must not update parser state")


@dataclass(frozen=True)
class AtomicStage:
    id: str
    family: str
    instruction: str
    success_checks: tuple[dict, ...]
    geometry: tuple[dict, ...]
    step_limit: int | None = None

    @classmethod
    def from_dict(cls, data):
        if not data.get("id") or data.get("family") not in FAMILIES or not data.get("instruction"):
            raise ValueError("stage needs id, valid family, and instruction")
        checks = tuple(data.get("success_checks", ()))
        if not checks:
            raise ValueError(f"stage {data['id']} needs at least one success check")
        for check in checks:
            _validate_check(check)
        geometry = tuple(data.get("geometry", ()))
        for condition in geometry:
            _validate_condition(condition)
        ids = [condition["id"] for condition in geometry]
        if len(ids) != len(set(ids)):
            raise ValueError(f"stage {data['id']} has duplicate condition ids")
        step_limit = data.get("step_limit")
        if step_limit is not None and (not isinstance(step_limit, int) or step_limit <= 0):
            raise ValueError("step_limit must be a positive integer")
        return cls(data["id"], data["family"], data["instruction"], checks, geometry, step_limit)

    def with_variant(self, variant):
        """Overlay instruction and expected geometry without changing the task.

        A variant may update expected values, tolerances, landmarks, or events
        by condition id. It cannot silently add a new success predicate.
        """
        if variant.get("stage_id") != self.id:
            raise ValueError("variant stage_id does not match selected stage")
        overrides = variant.get("conditions", {})
        if set(overrides) - {c["id"] for c in self.geometry}:
            raise ValueError("variant refers to unknown geometry condition")
        conditions = []
        for condition in self.geometry:
            changed = {**condition, **overrides.get(condition["id"], {})}
            if changed["id"] != condition["id"] or changed["slot"] != condition["slot"]:
                raise ValueError("variant cannot change condition identity or slot")
            _validate_condition(changed)
            conditions.append(changed)
        return AtomicStage(
            self.id, self.family, variant.get("instruction", self.instruction),
            self.success_checks, tuple(conditions), self.step_limit,
        )


@dataclass(frozen=True)
class AtomicProgram:
    task_name: str
    stages: tuple[AtomicStage, ...]

    @classmethod
    def load(cls, path):
        data = _read_json(path)
        if not data.get("task_name"):
            raise ValueError("atomic program needs task_name")
        stages = tuple(AtomicStage.from_dict(stage) for stage in data.get("stages", ()))
        if not stages or len({stage.id for stage in stages}) != len(stages):
            raise ValueError("atomic program needs unique, nonempty stages")
        return cls(data["task_name"], stages)

    def stage(self, stage_id):
        for stage in self.stages:
            if stage.id == stage_id:
                return stage
        raise ValueError(f"unknown atomic stage {stage_id!r} for {self.task_name}")


@dataclass(frozen=True)
class AtomicTrace:
    task_name: str
    layout_id: int
    actions: tuple[dict, ...]
    stage_starts: dict[str, int]

    @classmethod
    def load(cls, path):
        data = _read_json(path)
        actions = data.get("actions", [])
        starts = data.get("stage_starts", {})
        if not data.get("task_name") or not isinstance(actions, list) or not isinstance(starts, dict):
            raise ValueError("trace needs task_name, actions list, and stage_starts mapping")
        if not isinstance(data.get("layout_id"), int):
            raise ValueError("trace needs an integer layout_id")
        if any(not isinstance(action, dict) for action in actions):
            raise ValueError("trace actions must be dictionaries")
        if any(not isinstance(index, int) or index < 0 or index > len(actions) for index in starts.values()):
            raise ValueError("stage_starts indices must be valid action boundaries")
        return cls(data["task_name"], data["layout_id"], tuple(actions), starts)


def load_variant(path):
    return _read_json(path) if path else None
