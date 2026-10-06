"""Solid-mesh containment in a calibrated finite union of interior boxes.

An interior is authored independently of the receptacle's outer surface. Boxes
are axis-aligned in its selected live frame and may form a nonconvex region.
No object-centre or vertex-only containment shortcut is accepted.
"""
from itertools import combinations, product
import numpy as np
from scipy.spatial import ConvexHull, QhullError
from task.atomic.geometry import GeometryUnavailable


def validate_boxes(boxes):
    if not isinstance(boxes, list) or not 1 <= len(boxes) <= 16:
        raise ValueError('interior_boxes needs one to sixteen calibrated boxes')
    output = []
    for box in boxes:
        if not isinstance(box, dict) or set(box) != {'center', 'half_extents'}:
            raise ValueError('each interior box needs center and half_extents in metres')
        center, half = np.asarray(box['center'], dtype=float), np.asarray(box['half_extents'], dtype=float)
        if center.shape != (3,) or half.shape != (3,) or not np.isfinite([center, half]).all() or np.any(half <= 0):
            raise ValueError('interior boxes require finite centers and positive half-extents')
        output.append((center, half))
    return output


def validate_solid(vertices, triangles):
    vertices, triangles = np.asarray(vertices, dtype=float), np.asarray(triangles)
    if (vertices.ndim != 2 or vertices.shape[1] != 3 or not np.isfinite(vertices).all()
            or triangles.ndim != 2 or triangles.shape[1] != 3 or triangles.dtype.kind not in 'iu'
            or not len(triangles) or triangles.min() < 0 or triangles.max() >= len(vertices)):
        raise ValueError('solid containment requires a finite triangle mesh')
    # Rendering seams may duplicate positions without creating a physical hole.
    vertices, remap = np.unique(np.round(vertices, 12), axis=0, return_inverse=True)
    triangles = remap[triangles]
    edges = {}
    for face in triangles:
        a, b, c = vertices[face]
        if np.linalg.norm(np.cross(b-a, c-a)) <= 1e-15:
            raise GeometryUnavailable('solid containment requires nondegenerate faces')
        for i, j in zip(face, np.roll(face, -1)):
            key = tuple(sorted((int(i), int(j))))
            edges.setdefault(key, []).append(1 if i < j else -1)
    if any(len(signs) != 2 or sum(signs) != 0 for signs in edges.values()):
        raise GeometryUnavailable('solid containment requires a closed consistently oriented mesh')
    return vertices, triangles


def _intersection_volume(tetra, low, high):
    """All vertices of the convex intersection of one tetrahedron and one box."""
    eps = 1e-11
    try:
        planes = ConvexHull(tetra).equations
    except QhullError:
        return 0.
    def in_tetra(points):
        return np.all(points @ planes[:, :3].T + planes[:, 3] <= eps, axis=1)
    def in_box(points):
        return np.all((points >= low-eps) & (points <= high+eps), axis=1)
    bits = np.array(list(product((0, 1), repeat=3)))
    corners = low + bits * (high-low)
    points = list(tetra[in_box(tetra)]) + list(corners[in_tetra(corners)])
    for i, j in combinations(range(4), 2):
        a, delta = tetra[i], tetra[j] - tetra[i]
        for axis in range(3):
            if abs(delta[axis]) <= eps: continue
            for bound in (low[axis], high[axis]):
                alpha = (bound-a[axis]) / delta[axis]
                point = a + alpha*delta
                if -eps <= alpha <= 1+eps and in_box(point[None, :])[0]: points.append(point)
    for i, j in combinations(range(8), 2):
        if np.count_nonzero(bits[i] != bits[j]) != 1: continue
        a, delta = corners[i], corners[j]-corners[i]
        for plane in planes:
            denominator = delta @ plane[:3]
            if abs(denominator) <= eps: continue
            alpha = -(a @ plane[:3]+plane[3])/denominator
            point = a+alpha*delta
            if -eps <= alpha <= 1+eps and in_tetra(point[None, :])[0]: points.append(point)
    if len(points) < 4: return 0.
    points = np.unique(np.round(points, 12), axis=0)
    try:
        return float(ConvexHull(points).volume) if len(points) >= 4 else 0.
    except QhullError:
        return 0.


def region_containment(vertices, triangles, boxes, face_tolerance_m=0.):
    """Integrate solid volume outside the union, including enclosed holes.

    Signed tetrahedral integration handles nonconvex closed objects. Disjoint
    arrangement cells avoid double-counting overlapping interior boxes. Face
    tolerance expands each box in L-infinity distance, not Euclidean distance.
    Vertex distance is separately reported; it cannot certify whole-object fit.
    """
    vertices, triangles = validate_solid(vertices, triangles)
    boxes = validate_boxes(boxes)
    if not np.isfinite(face_tolerance_m) or face_tolerance_m < 0:
        raise ValueError('face tolerance must be finite and nonnegative')
    expanded = [(center, half+face_tolerance_m) for center, half in boxes]
    low, high = vertices.min(axis=0), vertices.max(axis=0)
    grids = []
    for axis in range(3):
        boundaries = [low[axis], high[axis]]
        boundaries += [np.clip(bound, low[axis], high[axis]) for center, half in expanded
                       for bound in (center[axis]-half[axis], center[axis]+half[axis])]
        grids.append(np.unique(boundaries))
    cell_count = np.prod([len(g)-1 for g in grids])
    if cell_count > 4096:
        raise ValueError('interior arrangement exceeds 4096 cells; simplify calibrated region')
    cells = []
    for index in product(*(range(len(g)-1) for g in grids)):
        a = np.array([g[i] for g, i in zip(grids, index)])
        b = np.array([g[i+1] for g, i in zip(grids, index)])
        midpoint = (a+b)/2
        if any(np.all(np.abs(midpoint-center) <= half) for center, half in expanded): cells.append((a, b))
    origin = (low+high)/2
    signed_total = signed_inside = 0.
    for face in triangles:
        triangle = vertices[face]
        signed = float(np.linalg.det(triangle-origin)/6)
        if abs(signed) <= 1e-18: continue
        tetra = np.vstack((origin, triangle))
        signed_total += signed
        tetra_low, tetra_high = tetra.min(axis=0), tetra.max(axis=0)
        sign = 1 if signed > 0 else -1
        for a, b in cells:
            if np.any(b <= tetra_low) or np.any(a >= tetra_high): continue
            signed_inside += sign*_intersection_volume(tetra, a, b)
    total = abs(signed_total)
    if total <= 1e-15:
        raise GeometryUnavailable('solid containment requires nonzero oriented material volume')
    inside = signed_inside*(1 if signed_total > 0 else -1)
    if not -1e-12 <= inside <= total+max(1e-12, total*1e-7):
        raise GeometryUnavailable('inconsistent solid orientation or containment integration')
    outside = max(0., total-inside)
    vertex_distance = np.min(np.stack([np.max(np.maximum(np.abs(vertices-center)-half, 0), axis=1)
                                      for center, half in boxes]), axis=0)
    vertex_error = float(vertex_distance.max())
    passed = outside <= max(1e-15, total*1e-7) and vertex_error <= face_tolerance_m+1e-10
    return {'passed': bool(passed), 'outside_volume_m3': outside,
            'object_volume_m3': total, 'outside_volume_fraction': outside/total,
            'vertex_containment_error_m': vertex_error,
            'certification': 'closed oriented solid mesh in calibrated interior-box union',
            'face_tolerance_metric': 'L-infinity expansion in the reference frame'}
