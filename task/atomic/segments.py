"""Exact geometry of finite material-endpoint chords, not infinite lines."""
import numpy as np


def endpoints(value):
    p=np.asarray(value.get('endpoints_m') if isinstance(value,dict) else value,dtype=float)
    if p.shape!=(2,3) or not np.isfinite(p).all() or np.linalg.norm(p[1]-p[0])==0:
        raise ValueError('segment requires two distinct finite actual material endpoints')
    return p


def point_segment_distance(p,a,b):
    u=b-a;alpha=float(np.clip((p-a)@u/(u@u),0,1))
    return float(np.linalg.norm(p-(a+alpha*u)))


def segment_distance(a,b):
    """The constrained quadratic minimum is on a boundary or stationary inside."""
    a,b=endpoints(a),endpoints(b);u=a[1]-a[0];v=b[1]-b[0];w=a[0]-b[0]
    candidates=[point_segment_distance(p,*b) for p in a]+[point_segment_distance(p,*a) for p in b]
    n=np.cross(u,v);n2=n@n
    if n2>0:
        r=-w;s=float(np.cross(r,v)@n/n2);t=float(np.cross(r,u)@n/n2)
        if 0<=s<=1 and 0<=t<=1:candidates.append(float(np.linalg.norm(w+s*u-t*v)))
    return min(candidates)


def segment_metrics(measured,reference):
    a,b=endpoints(measured),endpoints(reference)
    da=[point_segment_distance(p,*b) for p in a];db=[point_segment_distance(p,*a) for p in b]
    u,v=a[1]-a[0],b[1]-b[0]
    return {'segment_gap_m':segment_distance(a,b),
        'segment_hausdorff_m':max(*da,*db),
        'segment_axis_angle_rad':float(np.arccos(np.clip(abs(u@v)/(np.linalg.norm(u)*np.linalg.norm(v)),0,1))),
        'measurement_length_m':float(np.linalg.norm(u)),'reference_length_m':float(np.linalg.norm(v))}
