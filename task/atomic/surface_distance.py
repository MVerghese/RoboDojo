"""Exact triangle-boundary gap with bounding-volume pruning; no centre proxy."""
import heapq
import itertools
import numpy as np
from task.atomic.geometry import GeometryUnavailable
from task.atomic.segments import segment_distance


def _point_edge(p,a,b):
    u=b-a;length=u@u
    if length==0:return float(np.linalg.norm(p-a))
    return float(np.linalg.norm(p-a-np.clip((p-a)@u/length,0,1)*u))


def _point_triangle(p,t):
    a,b,c=t;u,v=b-a,c-a;n=np.cross(u,v);n2=n@n
    candidates=[_point_edge(p,x,y) for x,y in zip(t,np.roll(t,-1,axis=0))]
    if n2>0:
        projection=p-n*((p-a)@n/n2);w=projection-a
        # Area coordinates avoid cancellation in a Gram determinant for slivers.
        beta=np.cross(w,v)@n/n2;gamma=np.cross(u,w)@n/n2
        if beta>=0 and gamma>=0 and beta+gamma<=1:
            candidates.append(float(abs((p-a)@n)/np.sqrt(n2)))
    return min(candidates)


def _pierces(a,b,t):
    n=np.cross(t[1]-t[0],t[2]-t[0]);d0=(a-t[0])@n;d1=(b-t[0])@n
    if d0*d1>0 or d0==d1:return False
    alpha=d0/(d0-d1)
    return 0<=alpha<=1 and _point_triangle(a+alpha*(b-a),t)<=1e-12


def triangle_gap(a,b):
    for x,y in zip(a,np.roll(a,-1,axis=0)):
        if _pierces(x,y,b):return 0.
    for x,y in zip(b,np.roll(b,-1,axis=0)):
        if _pierces(x,y,a):return 0.
    candidates=[_point_triangle(p,b) for p in a]+[_point_triangle(p,a) for p in b]
    for x,y in zip(a,np.roll(a,-1,axis=0)):
        if np.linalg.norm(y-x)==0:continue
        for z,w in zip(b,np.roll(b,-1,axis=0)):
            if np.linalg.norm(w-z)>0:candidates.append(segment_distance([x,y],[z,w]))
    return min(candidates)


def _triangles(vertices,faces):
    v=np.asarray(vertices,dtype=float);f=np.asarray(faces)
    if v.ndim!=2 or v.shape[1]!=3 or not np.isfinite(v).all() or f.ndim!=2 or f.shape[1]!=3 or f.dtype.kind not in 'iu' or not len(f) or f.min()<0 or f.max()>=len(v):
        raise ValueError('surface gap needs finite actual vertices and valid triangles')
    q=v[f];regular=np.linalg.norm(np.cross(q[:,1]-q[:,0],q[:,2]-q[:,0]),axis=1)>0
    if not regular.any():raise GeometryUnavailable('surface gap has no nondegenerate material triangles')
    return q[regular],int((~regular).sum())


class _Node:
    def __init__(self,q,ids):
        self.low=q[ids].min(axis=(0,1));self.high=q[ids].max(axis=(0,1));self.children=();self.ids=ids
        if len(ids)>8:
            centers=q[ids].mean(axis=1);axis=int(np.ptp(centers,axis=0).argmax());order=ids[np.argsort(centers[:,axis])];middle=len(ids)//2
            self.children=(_Node(q,order[:middle]),_Node(q,order[middle:]));self.ids=None


def _bound(a,b):
    return float(np.linalg.norm(np.maximum(np.maximum(a.low-b.high,b.low-a.high),0)))


def mesh_surface_gap(vertices_a,triangles_a,vertices_b,triangles_b):
    a,discard_a=_triangles(vertices_a,triangles_a);b,discard_b=_triangles(vertices_b,triangles_b)
    ra,rb=_Node(a,np.arange(len(a))),_Node(b,np.arange(len(b)))
    serial=itertools.count();queue=[(_bound(ra,rb),next(serial),ra,rb)];best=float('inf');tested=0
    while queue:
        lower,_,x,y=heapq.heappop(queue)
        if lower>=best:continue
        if not x.children and not y.children:
            for i in x.ids:
                for j in y.ids:
                    tested+=1;best=min(best,triangle_gap(a[i],b[j]))
                    if best==0:return {'surface_distance_m':0.,'triangle_pairs_tested':tested,'ignored_zero_area_faces':[discard_a,discard_b],'numerical_intersection_tolerance_m':1e-12}
        else:
            split_x=bool(x.children) and (not y.children or np.linalg.norm(x.high-x.low)>=np.linalg.norm(y.high-y.low))
            pairs=[(c,y) for c in x.children] if split_x else [(x,c) for c in y.children]
            for u,v in pairs:
                lower=_bound(u,v)
                if lower<best:heapq.heappush(queue,(lower,next(serial),u,v))
    return {'surface_distance_m':best,'triangle_pairs_tested':tested,'ignored_zero_area_faces':[discard_a,discard_b],'numerical_intersection_tolerance_m':1e-12}
