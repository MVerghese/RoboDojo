"""Measured solid cross-section fit at a calibrated opening plane."""
import numpy as np
from shapely.geometry import LineString, MultiLineString, Polygon
from shapely.ops import polygonize, unary_union

from task.atomic.geometry import GeometryUnavailable
from task.atomic.regions import validate_solid


def aperture_polygon(profile):
    if not isinstance(profile, dict) or set(profile) - {'outer', 'holes'} or 'outer' not in profile:
        raise ValueError('aperture_profile requires a calibrated outer ring and optional holes')
    rings = [profile['outer']] + profile.get('holes', [])
    for ring in rings:
        points = np.asarray(ring, dtype=float)
        if points.ndim != 2 or points.shape[1] != 2 or len(points) < 3 or not np.isfinite(points).all():
            raise ValueError('aperture rings require at least three finite XY points in metres')
    polygon = Polygon(profile['outer'], profile.get('holes', []))
    if not polygon.is_valid or polygon.area <= 1e-15:
        raise ValueError('aperture profile must be a valid finite region with positive area')
    return polygon


def _inside_solid(point, vertices, triangles):
    vectors = vertices[triangles]-point
    a, b, c = vectors[:, 0], vectors[:, 1], vectors[:, 2]
    la, lb, lc = (np.linalg.norm(v, axis=1) for v in (a, b, c))
    numerator = np.einsum('ij,ij->i', a, np.cross(b, c))
    denominator = la*lb*lc + np.einsum('ij,ij->i', a, b)*lc + np.einsum('ij,ij->i', b, c)*la + np.einsum('ij,ij->i', c, a)*lb
    winding = float(np.sum(2*np.arctan2(numerator, denominator))/(4*np.pi))
    return abs(winding) > .5


def material_section(vertices, triangles):
    """Closed solid material cut at z=0, preserving holes and disconnected parts."""
    vertices, triangles = validate_solid(vertices, triangles)
    eps = 1e-10
    lines, coplanar = [], []
    for face in triangles:
        points = vertices[face]
        if np.all(np.abs(points[:, 2]) <= eps):
            polygon = Polygon(points[:, :2])
            if polygon.area > 1e-15: coplanar.append(polygon)
            continue
        hits = []
        for a, b in zip(points, np.roll(points, -1, axis=0)):
            if abs(a[2]) <= eps: hits.append(a[:2])
            if a[2]*b[2] < 0:
                hits.append((a+(b-a)*(-a[2]/(b[2]-a[2])))[:2])
        if hits:
            hits = np.unique(np.round(hits, 12), axis=0)
            if len(hits) == 2 and np.linalg.norm(hits[0]-hits[1]) > eps:
                lines.append(LineString(hits))
    polygons = list(coplanar)
    if lines:
        for polygon in polygonize(unary_union(lines)):
            point = polygon.representative_point()
            if _inside_solid(np.array([point.x, point.y, 0.]), vertices, triangles): polygons.append(polygon)
    if not polygons:
        raise GeometryUnavailable('no closed solid cross-section intersects the opening plane')
    return unary_union(polygons)


def oriented_trace_section(vertices, triangles):
    """Material at z=0 from closed, consistently directed surface cut traces.

    The mesh may have open ends away from this plane. No missing surface is
    filled: only the actual plane traces certify this local section. Open,
    duplicate, branching, coplanar or inconsistently oriented traces fail.
    """
    from collections import Counter
    v, t = np.asarray(vertices, dtype=float), np.asarray(triangles)
    if (v.ndim != 2 or v.shape[1] != 3 or not np.isfinite(v).all()
            or t.ndim != 2 or t.shape[1] != 3 or t.dtype.kind not in 'iu'
            or not len(t) or t.min() < 0 or t.max() >= len(v)):
        raise ValueError('plane traces require actual finite vertices and integer topology')
    q = v[t]
    normals = np.cross(q[:,1]-q[:,0], q[:,2]-q[:,0])
    nondegenerate = np.linalg.norm(normals,axis=1) > 1e-15
    intersects = nondegenerate & (q[:,:,2].min(1) <= 0) & (q[:,:,2].max(1) >= 0)
    starts, ends = Counter(), Counter()
    segments = []; maximum_shift = 0.
    for face, normal in zip(q[intersects], normals[intersects]):
        hits = []
        for a,b in zip(face,np.roll(face,-1,axis=0)):
            if a[2] == 0 and b[2] == 0:
                raise GeometryUnavailable('opening plane coincides with a material mesh edge/face')
            if a[2]*b[2] < 0:
                hits.append((a+(b-a)*(-a[2]/(b[2]-a[2])))[:2])
            elif a[2] == 0:
                hits.append(a[:2])
        if not hits:
            continue
        raw = np.asarray(hits)
        rounded = np.round(raw,12)
        maximum_shift = max(maximum_shift,float(np.linalg.norm(raw-rounded,axis=1).max()))
        points = np.unique(rounded,axis=0)
        if len(points) == 1:  # One tangent vertex contributes no finite section.
            continue
        if len(points) != 2:
            raise GeometryUnavailable('ambiguous actual material plane trace')
        a,b = points
        tangent = np.array([-normal[1],normal[0]])
        direction = float((b-a)@tangent)
        if direction == 0:
            raise GeometryUnavailable('degenerate directed material plane trace')
        if direction < 0:
            a,b = b,a
        a,b = tuple(a),tuple(b)
        starts[a] += 1;ends[b] += 1
        segments.append((a,b))
    if not segments:
        raise GeometryUnavailable('no material cross-section intersects the opening plane')
    if any(starts[p] != 1 or ends[p] != 1 for p in starts.keys()|ends.keys()):
        raise GeometryUnavailable('material plane traces are open, duplicate, branching or inconsistently oriented')
    lines = [LineString([a,b]) for a,b in segments]
    if not MultiLineString(lines).is_simple:
        raise GeometryUnavailable('material plane traces cross or overlap away from their endpoints')
    polygons = list(polygonize(unary_union(lines)))
    if not polygons:
        raise GeometryUnavailable('material plane traces do not enclose a finite section')
    selected = []
    for polygon in polygons:
        point = np.asarray(polygon.representative_point().coords[0])
        uv = np.asarray(segments)-point
        a,b = uv[:,0],uv[:,1]
        winding = float(np.arctan2(a[:,0]*b[:,1]-a[:,1]*b[:,0],
                                  np.einsum('ij,ij->i',a,b)).sum()/(2*np.pi))
        count = round(winding)
        if abs(winding-count)>1e-6 or abs(count)>1:
            raise GeometryUnavailable('self-overlapping or ambiguous oriented section winding')
        if abs(count) == 1:
            selected.append(polygon)
    if not selected:
        raise GeometryUnavailable('no material interior certified by the oriented section traces')
    return unary_union(selected), {
        'plane_trace_segments':len(segments),
        'ignored_zero_area_faces':int((~nondegenerate).sum()),
        'maximum_endpoint_weld_displacement_m':maximum_shift,
        'certification':'closed oriented actual surface cut at one plane; not whole-solid certification'}


def trace_section_fit(vertices, triangles, profile, required_clearance_m=0., tolerance_m=0.):
    section, proof = oriented_trace_section(vertices,triangles)
    return {**_compare_section(section,profile,required_clearance_m,tolerance_m), **proof,
            'measurement':'actual material from closed oriented surface traces at calibrated local z=0',
            'interpretation':'fit of this local section only; no whole-solid/volume/seating claim'}


def section_fit(vertices, triangles, profile, required_clearance_m=0., tolerance_m=0.):
    """Compare actual solid material at z=0 with the calibrated aperture.

    Hole regions stay forbidden, including holes engulfed by the section.
    This certifies fit at one plane, not seating force or thread engagement.
    """
    section = material_section(vertices, triangles)
    return _compare_section(section,profile,required_clearance_m,tolerance_m)


def _compare_section(section,profile,required_clearance_m,tolerance_m):
    aperture = aperture_polygon(profile)
    if not np.isfinite([required_clearance_m, tolerance_m]).all() or min(required_clearance_m, tolerance_m) < 0:
        raise ValueError('clearance and tolerance must be finite and nonnegative')
    # Positive tolerance expands the calibrated aperture; required clearance
    # shrinks it. Both distances are explicitly in its physical XY plane.
    allowed = aperture.buffer(tolerance_m-required_clearance_m, join_style=2)
    outside = section.difference(allowed)
    passed = outside.area <= max(1e-15, section.area*1e-8)
    raw_outside = section.difference(aperture).area
    return {'passed': bool(passed), 'section_area_m2': float(section.area),
            'outside_aperture_area_m2': float(raw_outside),
            'outside_allowed_area_m2': float(outside.area),
            'boundary_distance_m': float(section.distance(aperture.boundary)),
            'required_clearance_m': float(required_clearance_m),
            'measurement': 'solid material cross-section at calibrated opening local z=0',
            'interpretation': 'geometric fit at one plane; no seating/contact/thread claim'}


def seating_metrics(seat_pose, rim_pose):
    """Gap and tilt of actual annotated seating/rim frames, including failures."""
    from task.atomic.geometry import _rotation
    seat, rim = np.asarray(seat_pose, dtype=float), np.asarray(rim_pose, dtype=float)
    if seat.shape != (7,) or rim.shape != (7,) or not np.isfinite([seat, rim]).all():
        raise ValueError('seating requires two finite annotated live poses')
    local = _rotation(rim[3:]).T @ (seat[:3]-rim[:3])
    cosine = _rotation(seat[3:])[:, 2] @ _rotation(rim[3:])[:, 2]
    return {'seating_gap_m': float(local[2]), 'seating_lateral_error_m': float(np.linalg.norm(local[:2])),
            'seating_axis_error_rad': float(np.arccos(np.clip(cosine, -1, 1)))}
