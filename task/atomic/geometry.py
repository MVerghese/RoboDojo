"""Continuous geometric scores in an environment-local world frame.

Quaternions are scalar-first (w, x, y, z). Distances are metres and angular
errors are radians. This module deliberately has no Isaac Sim dependency.
"""

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class GeometryResult:
    passed: bool
    error: float
    tolerance: float
    components: dict[str, float]
    observed: Any

    def as_dict(self):
        return {
            "passed": self.passed,
            "error": self.error,
            "tolerance": self.tolerance,
            "components": self.components,
            "observed": self.observed,
        }


def _vector(value, size, name):
    result = np.asarray(value, dtype=float)
    if result.shape != (size,) or not np.isfinite(result).all():
        raise ValueError(f"{name} must be a finite {size}-vector")
    return result


def _quaternion(value):
    q = _vector(value, 4, "quaternion")
    norm = np.linalg.norm(q)
    if norm < 1e-12:
        raise ValueError("quaternion must have nonzero norm")
    return q / norm


def _rotation(q):
    w, x, y, z = _quaternion(q)
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ]
    )


def _angular_error(a, b):
    # The absolute dot makes q and -q represent the same rotation.
    dot = np.clip(abs(float(np.dot(_quaternion(a), _quaternion(b)))), 0.0, 1.0)
    return float(2 * np.arccos(dot))


def _pose(value, name):
    if value is None:
        return np.zeros(3), np.array([1.0, 0.0, 0.0, 0.0])
    if isinstance(value, dict):
        return _vector(value["position"], 3, f"{name}.position"), _quaternion(value["orientation"])
    arr = _vector(value, 7, name)
    return arr[:3], _quaternion(arr[3:])


def _observed_pose(measured):
    if isinstance(measured, dict):
        return _vector(measured["position"], 3, "measured.position"), (
            _quaternion(measured["orientation"]) if "orientation" in measured else None
        )
    arr = np.asarray(measured, dtype=float)
    if arr.shape == (3,):
        return _vector(arr, 3, "measured"), None
    if arr.shape == (7,):
        return _vector(arr[:3], 3, "measured.position"), _quaternion(arr[3:])
    raise ValueError("measured must be a point or pose")


def evaluate_geometry(condition: dict, measured, reference=None) -> GeometryResult:
    """Score one of the five taxonomy modifiers against a measured point/pose.

    ``reference`` is a world-frame pose of the named task landmark. For P/T,
    ``expected`` is expressed in that frame (world if omitted). For D/O, the
    observed displacement/rotation is expressed relative to that pose. For R,
    x is right, y is forward, z is up in the reference frame.
    """
    kind = condition["kind"]
    tolerance = float(condition.get("tolerance", 0.0))
    if tolerance < 0 or not np.isfinite(tolerance):
        raise ValueError("tolerance must be finite and nonnegative")
    point, orientation = _observed_pose(measured)
    ref_pos, ref_rot = _pose(reference, "reference")
    ref_matrix = _rotation(ref_rot)
    local_point = ref_matrix.T @ (point - ref_pos)

    if kind == "point":
        expected = _vector(condition["expected"], 3, "expected")
        error = float(np.linalg.norm(local_point - expected))
        return GeometryResult(error <= tolerance, error, tolerance, {"position_m": error}, local_point.tolist())

    if kind == "pose":
        if orientation is None:
            raise ValueError("pose condition requires an observed orientation")
        expected = condition["expected"]
        expected_pos = _vector(expected["position"], 3, "expected.position")
        expected_rot = _quaternion(expected["orientation"])
        pos_error = float(np.linalg.norm(local_point - expected_pos))
        # Compare rotations in the reference frame without a quaternion library.
        # R_expected_world = R_reference R_expected_local.
        rot_error = float(np.arccos(np.clip((np.trace(_rotation(orientation).T @ ref_matrix @ _rotation(expected_rot)) - 1) / 2, -1, 1)))
        angle_tolerance = float(condition.get("angle_tolerance_rad", tolerance))
        passed = pos_error <= tolerance and rot_error <= angle_tolerance
        return GeometryResult(
            passed,
            max(pos_error / max(tolerance, 1e-12), rot_error / max(angle_tolerance, 1e-12)),
            1.0,
            {"position_m": pos_error, "orientation_rad": rot_error},
            {"position": local_point.tolist(), "orientation_error_rad": rot_error},
        )

    if kind == "relative_displacement":
        expected = _vector(condition["expected"], 3, "expected")
        error = float(np.linalg.norm(local_point - expected))
        return GeometryResult(error <= tolerance, error, tolerance, {"displacement_m": error}, local_point.tolist())

    if kind == "relative_orientation":
        if orientation is None:
            raise ValueError("relative_orientation requires an observed orientation")
        expected = _quaternion(condition["expected"])
        # Compare R_observed with R_reference R_expected; result is invariant to q sign.
        cos_angle = np.clip((np.trace(_rotation(orientation).T @ ref_matrix @ _rotation(expected)) - 1) / 2, -1, 1)
        error = float(np.arccos(cos_angle))
        return GeometryResult(error <= tolerance, error, tolerance, {"orientation_rad": error}, error)

    if kind == "spatial_relation":
        relation = condition["expected"]
        margin = float(condition.get("margin", 0.0))
        if not np.isfinite(margin) or margin < 0:
            raise ValueError("margin must be finite and nonnegative")
        direction = {
            "right_of": (0, 1), "left_of": (0, -1),
            "in_front_of": (1, 1), "behind": (1, -1),
            "above": (2, 1), "below": (2, -1),
        }
        if relation in direction:
            axis, sign = direction[relation]
            signed_distance = float(sign * local_point[axis])
            error = max(0.0, margin - signed_distance)
        elif relation == "near":
            signed_distance = float(np.linalg.norm(local_point))
            error = signed_distance
        elif relation in ("inside_box", "on_top"):
            half_extents = _vector(condition["half_extents"], 3, "half_extents")
            if np.any(half_extents <= 0):
                raise ValueError("half_extents must be positive")
            if relation == "inside_box":
                error = float(np.linalg.norm(np.maximum(np.abs(local_point) - half_extents, 0.0)))
            else:
                horizontal = np.maximum(np.abs(local_point[:2]) - half_extents[:2], 0.0)
                vertical = abs(float(local_point[2] - half_extents[2]))
                error = float(np.linalg.norm([*horizontal, vertical]))
        else:
            raise ValueError(f"unsupported spatial relation: {relation}")
        return GeometryResult(error <= tolerance, error, tolerance, {"relation_error_m": error}, local_point.tolist())

    raise ValueError(f"unsupported geometry kind: {kind}")
