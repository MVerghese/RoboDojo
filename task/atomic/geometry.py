"""Continuous geometric scores in an environment-local world frame.

Quaternions are scalar-first (w, x, y, z). Distances are metres and angular
errors are radians. This module deliberately has no Isaac Sim dependency.
"""

from dataclasses import dataclass
from typing import Any

import numpy as np


class GeometryUnavailable(ValueError):
    """Valid condition whose live geometric representation cannot certify it."""


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
    scale = np.max(np.abs(q))
    if scale == 0:
        raise ValueError("quaternion must have nonzero norm")
    # Quaternion scale has no physical meaning. Normalize without overflowing
    # or underflowing when finite nonzero data has an unusual magnitude.
    q = q / scale
    return q / np.linalg.norm(q)


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
        return _vector(value["position"], 3, f"{name}.position"), _quaternion(value.get("orientation", [1, 0, 0, 0]))
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

    # A contact patch contains multiple surface points. Scoring its centroid can
    # hide two wrong contacts on opposite sides of an object, so score all points.
    if isinstance(measured, dict) and 'points' in measured:
        points = np.asarray(measured['points'], dtype=float)
        if points.ndim != 2 or points.shape[1] != 3 or not len(points) or not np.isfinite(points).all():
            raise ValueError('contact measurement requires nonempty finite Nx3 points')
        if kind in ('pose', 'relative_orientation'):
            raise ValueError('contact points do not define an SE(3) orientation; use an explicit contact frame')
        results = [evaluate_geometry(condition, p, reference) for p in points]
        worst = max(results, key=lambda r: r.error)
        count_key='material_points' if measured.get('point_kind') in ('cloth','fluid') else 'contact_points'
        return GeometryResult(all(r.passed for r in results), worst.error, worst.tolerance,
                              {**worst.components, count_key: float(len(points))},
                              {'centroid_in_reference': local_point.tolist(),
                               'per_contact': [r.observed for r in results]})

    axes = condition.get('axes', [0, 1, 2])
    if not isinstance(axes, list) or not axes or len(set(axes)) != len(axes) or any(i not in (0, 1, 2) for i in axes):
        raise ValueError('axes must be a nonempty subset of [0,1,2]')

    if kind == "point":
        expected = _vector(condition["expected"], 3, "expected")
        error = float(np.linalg.norm((local_point - expected)[axes]))
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
        if angle_tolerance < 0 or not np.isfinite(angle_tolerance):
            raise ValueError('angle_tolerance_rad must be finite and nonnegative')
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
        error = float(np.linalg.norm((local_point - expected)[axes]))
        return GeometryResult(error <= tolerance, error, tolerance, {"displacement_m": error}, local_point.tolist())

    if kind == "relative_orientation":
        if orientation is None:
            raise ValueError("relative_orientation requires an observed orientation")
        expected = _quaternion(condition["expected"])
        # Compare R_observed with R_reference R_expected; result is invariant to q sign.
        cos_angle = np.clip((np.trace(_rotation(orientation).T @ ref_matrix @ _rotation(expected)) - 1) / 2, -1, 1)
        error = float(np.arccos(cos_angle))
        if condition.get('orientation_axes'):
            axes = condition['orientation_axes']
            if not isinstance(axes, list) or not axes or any(i not in (0, 1, 2) for i in axes):
                raise ValueError('orientation_axes must be axis indices')
            observed_matrix = _rotation(orientation)
            expected_matrix = ref_matrix @ _rotation(expected)
            error = max(float(np.arccos(np.clip(observed_matrix[:, i] @ expected_matrix[:, i], -1, 1))) for i in axes)
        return GeometryResult(error <= tolerance, error, tolerance, {"orientation_rad": error}, error)

    if kind == "spatial_relation":
        relation = condition["expected"]
        margin = float(condition.get("margin", 0.0))
        if not np.isfinite(margin) or margin < 0:
            raise ValueError("margin must be finite and nonnegative")
        if condition.get('relation_scope')=='segments':
            from task.atomic.segments import segment_metrics
            components=segment_metrics(measured,reference)
            if relation not in ('intersects_segment','coincides_with_segment'):
                raise ValueError('unsupported finite material segment relation')
            error=components['segment_gap_m' if relation=='intersects_segment' else 'segment_hausdorff_m']
            return GeometryResult(error<=tolerance,error,tolerance,components,components)
        if condition.get('relation_scope') == 'objects':
            return _object_relation(condition, measured, reference, ref_pos, ref_matrix, local_point, tolerance)
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


def _object_relation(condition, measured, reference, ref_pos, ref_matrix, local_point, tolerance):
    """Directional separation plus projected *mesh* overlap; no centre-only pass."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    def surface(value):
        if not isinstance(value, dict) or 'vertices' not in value or 'triangles' not in value:
            raise ValueError('object relations require live mesh vertices and triangles for both objects')
        vertices = np.asarray(value['vertices'], dtype=float)
        triangles = np.asarray(value['triangles'], dtype=int)
        if vertices.ndim != 2 or vertices.shape[1] != 3 or not np.isfinite(vertices).all():
            raise ValueError('invalid mesh vertices')
        if triangles.ndim != 2 or triangles.shape[1] != 3 or not len(triangles) or triangles.min() < 0 or triangles.max() >= len(vertices):
            raise ValueError('invalid mesh triangles')
        return (vertices - ref_pos) @ ref_matrix, triangles
    a, at = surface(measured)
    b, bt = surface(reference)
    relation = condition['expected']
    direction = {'above': (2, 1), 'below': (2, -1), 'right_of': (0, 1), 'left_of': (0, -1),
                 'in_front_of': (1, 1), 'behind': (1, -1), 'on_top': (2, 1)}
    if relation == 'layered_over':
        from task.atomic.layers import patch_layers
        result=patch_layers(a,at,b,bt,condition['min_layer_gap_m'],condition['max_layer_gap_m'],
            condition.get('min_overlap_fraction',.5),tolerance)
        return GeometryResult(result['passed'],max(result['layer_gap_shortfall_m'],result['layer_gap_excess_m']),
            tolerance,{k:v for k,v in result.items() if k.endswith(('_m','_m2','_fraction'))},result)
    if relation == 'inside_region':
        from task.atomic.regions import region_containment
        result = region_containment(a, at, condition['interior_boxes'], tolerance)
        components = {k: v for k, v in result.items() if k.endswith(('_m', '_m3', '_fraction'))}
        return GeometryResult(result['passed'], result['outside_volume_fraction'], 0., components, result)
    if relation == 'inside_aperture':
        from task.atomic.fit import section_fit
        result = section_fit(a, at, condition['aperture_profile'], condition.get('required_clearance_m', 0.), tolerance)
        components = {k: v for k, v in result.items() if k.endswith(('_m', '_m2'))}
        return GeometryResult(result['passed'], result['outside_allowed_area_m2'], 0., components, result)
    if relation == 'inside_box':
        half = _vector(condition['half_extents'], 3, 'half_extents')
        if np.any(half <= 0):
            raise ValueError('half_extents must be positive')
        error = float(np.linalg.norm(np.maximum(np.abs(a) - half, 0), axis=1).max())
        return GeometryResult(error <= tolerance, error, tolerance, {'containment_error_m': error}, local_point.tolist())
    if relation == 'near':
        raise ValueError('object near requires a surface distance implementation; centre distance is not accepted')
    if relation not in direction:
        raise ValueError(f'unsupported object relation {relation}')
    axis, sign = direction[relation]
    projection_axes = [i for i in range(3) if i != axis]
    def footprint(vertices, triangles):
        polygons = [Polygon(vertices[t][:, projection_axes]) for t in triangles]
        polygons = [p for p in polygons if p.area > 1e-12]
        if not polygons:
            raise ValueError('degenerate projected footprint')
        return unary_union(polygons)
    pa, pb = footprint(a, at), footprint(b, bt)
    overlap = float(pa.intersection(pb).area)
    denominator = min(pa.area, pb.area)
    fraction = overlap / denominator
    required_fraction = float(condition.get('min_overlap_fraction', 0.1))
    if not 0 < required_fraction <= 1:
        raise ValueError('min_overlap_fraction must be in (0,1]')
    # Selected landmark ordering (mesh centre or explicitly named root) is
    # separate from footprint overlap. For on_top,
    # use the surface-to-surface gap and require support contact supplied by sim.
    signed = sign * float(local_point[axis])
    error = max(0.0, float(condition.get('margin', 0)) - signed)
    if relation == 'on_top':
        error = abs(float(a[:, axis].min() - b[:, axis].max()))
    footprint_gap = float(pa.distance(pb))
    contact_ok = relation != 'on_top' or measured.get('support_contact', False)
    shortfall = max(0.0, required_fraction - fraction)
    normalized = max(error / max(tolerance, 1e-12), (1 + shortfall / required_fraction) if shortfall > 0 else 0,
                     0 if contact_ok else 1.000001)
    passed = error <= tolerance and fraction >= required_fraction and contact_ok
    return GeometryResult(passed, normalized, 1.0,
                          {'relation_error_m': error, 'signed_separation_m': signed,
                           'footprint_overlap_m2': overlap, 'footprint_overlap_fraction': fraction,
                           'required_overlap_fraction': required_fraction, 'footprint_gap_m': footprint_gap,
                           'overlap_shortfall_fraction': shortfall, 'vertical_tolerance_m': tolerance,
                           'support_contact_observed': float(bool(measured.get('support_contact', False)))},
                          local_point.tolist())
