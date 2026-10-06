"""Continuous distance between explicit finite material polylines.

Hausdorff distance considers edge interiors. Vertex-only distances can report
zero for curves traversing the same vertices along different paths.
"""
import numpy as np

from task.atomic.segments import segment_distance


def curve_points(value):
    points = np.asarray(value.get('polyline_m') if isinstance(value, dict) else value, dtype=float)
    if (points.ndim != 2 or points.shape[1] != 3 or not 2 <= len(points) <= 128
            or not np.isfinite(points).all()
            or np.any(np.sum(np.diff(points, axis=0)**2, axis=1) == 0)):
        raise ValueError('curve needs 2–128 finite ordered points with nonzero adjacent edges')
    return points


def _pieces(a, edge, target):
    """Distance-squared quadratic pieces from one source edge to target edges."""
    pieces = []
    for b, c in zip(target, target[1:]):
        v = c-b
        w = a-b
        denominator = v@v
        intercept, slope = float(w@v/denominator), float(edge@v/denominator)
        cuts = [0., 1.]
        if slope:
            cuts += [t for t in (-intercept/slope, (1-intercept)/slope) if 0 < t < 1]
        cuts = sorted(set(cuts))
        for low, high in zip(cuts, cuts[1:]):
            projection = intercept+slope*(low+high)/2
            if projection <= 0:
                r, u = w, edge
            elif projection >= 1:
                r, u = w-v, edge
            else:
                r, u = w-intercept*v, edge-slope*v
            pieces.append((low, high, np.array([u@u, 2*r@u, r@r])))
    return pieces


def directed_hausdorff(source, target):
    """Maximum of the lower envelope of piecewise convex quadratics.

    Between projection breakpoints and pairwise intersections the nearest
    target segment is fixed, so the convex quadratic's maximum is at an
    interval endpoint. This is continuous polyline geometry, not sampling.
    """
    source, target = curve_points(source), curve_points(target)
    maximum = 0.
    for a, b in zip(source, source[1:]):
        edge = b-a
        pieces = _pieces(a, edge, target)
        candidates = {0., 1., *(t for low, high, _ in pieces for t in (low, high))}
        # Batched quadratic roots avoid thousands of tiny eigensolver calls.
        lows, highs = np.asarray([(low, high) for low, high, _ in pieces]).T
        coefficients = np.asarray([c for _, _, c in pieces])
        i, j = np.triu_indices(len(pieces), 1)
        low, high = np.maximum(lows[i], lows[j]), np.minimum(highs[i], highs[j])
        valid = low < high
        low, high = low[valid], high[valid]
        difference = coefficients[i[valid]]-coefficients[j[valid]]
        scale = np.maximum(np.max(np.abs(difference), axis=1), 1e-300)
        tiny = 64*np.finfo(float).eps*scale
        aa, bb, cc = difference.T
        linear = (np.abs(aa) <= tiny) & (np.abs(bb) > tiny)
        roots = -cc[linear]/bb[linear]
        candidates.update(roots[(roots >= low[linear]) & (roots <= high[linear])].tolist())
        discriminant = bb*bb-4*aa*cc
        quadratic = (np.abs(aa) > tiny) & (discriminant >= 0)
        aq, bq, cq = aa[quadratic], bb[quadratic], cc[quadratic]
        # The stable q form preserves small roots when b and sqrt(D) cancel.
        q = -.5*(bq+np.copysign(np.sqrt(discriminant[quadratic]), bq))
        first = q/aq
        second = np.divide(cq, q, out=-bq/(2*aq), where=q != 0)
        for roots in (first, second):
            candidates.update(roots[(roots >= low[quadratic]) & (roots <= high[quadratic])].tolist())
        ts = np.asarray(sorted(candidates))
        starts, edges = target[:-1], np.diff(target, axis=0)
        offsets = a+ts[:, None]*edge
        offsets = offsets[:, None, :]-starts[None, :, :]
        fractions = np.clip(np.einsum('kij,ij->ki', offsets, edges)/np.einsum('ij,ij->i', edges, edges), 0, 1)
        residual = offsets-fractions[:, :, None]*edges
        maximum = max(maximum, float(np.max(np.min(np.einsum('kij,kij->ki', residual, residual), axis=1))))
    return float(np.sqrt(maximum))


def curve_metrics(measured, reference):
    a, b = curve_points(measured), curve_points(reference)
    return {'curve_gap_m': min(segment_distance(x, y)
                for x in zip(a, a[1:]) for y in zip(b, b[1:])),
            'curve_hausdorff_m': max(directed_hausdorff(a, b), directed_hausdorff(b, a)),
            'measurement_curve_length_m': float(np.linalg.norm(np.diff(a, axis=0), axis=1).sum()),
            'reference_curve_length_m': float(np.linalg.norm(np.diff(b, axis=0), axis=1).sum())}
