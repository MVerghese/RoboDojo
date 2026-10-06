"""Projected material patch coverage and exact linear triangle layer gaps."""
import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree
from task.atomic.geometry import GeometryUnavailable


def patch_layers(a,at,b,bt,min_gap_m,max_gap_m,min_overlap_fraction=.5,tolerance_m=0.):
    """Compare real material faces in the target's current tangent frame.

    Every overlapping triangle pair is checked at vertices of its projected
    intersection. Their height difference is affine, so these extrema bound
    the complete overlap, including penetrations hidden by a landmark gap.
    Coverage denominator is the moving patch footprint, not the smaller patch.
    This is local selected-patch layering; it is not whole-cloth collision or
    force-bearing support, and ignores zero-area vertical projected faces.
    """
    if not np.isfinite([min_gap_m,max_gap_m,min_overlap_fraction,tolerance_m]).all() or min_gap_m<0 or max_gap_m<min_gap_m or tolerance_m<0 or not 0<min_overlap_fraction<=1:
        raise ValueError('patch layers require valid physical gaps, overlap fraction and tolerance')
    def projected(vertices,triangles):
        rows=[]
        for face in triangles:
            values=np.asarray(vertices)[face];polygon=Polygon(values[:,:2])
            if polygon.area<=1e-14:continue
            coefficients=np.linalg.solve(np.column_stack((values[:,:2],np.ones(3))),values[:,2])
            rows.append((polygon,coefficients))
        if not rows:raise GeometryUnavailable('material patch has no nondegenerate tangent-plane footprint')
        return rows,unary_union([p for p,_ in rows])
    ar,pa=projected(a,at);br,pb=projected(b,bt)
    overlap=pa.intersection(pb).area;fraction=float(overlap/pa.area)
    result={'moving_footprint_m2':float(pa.area),'target_footprint_m2':float(pb.area),
        'footprint_overlap_m2':float(overlap),'footprint_overlap_fraction':fraction,
        'overlap_shortfall_fraction':max(0.,min_overlap_fraction-fraction),
        'footprint_gap_m':float(pa.distance(pb)),
        'layer_gap_shortfall_m':0.,'layer_gap_excess_m':0.,'gap_observed':False,
        'passed':False,'interpretation':'selected material patch overlap and all triangle-pair gaps; no grasp/support/global self-intersection claim'}
    if overlap<=1e-15:return result
    polygons=[p for p,_ in br];index={id(p):i for i,p in enumerate(polygons)};tree=STRtree(polygons)
    low=float('inf');high=-float('inf')
    for p,coeff in ar:
        for hit in tree.query(p):
            j=int(hit) if isinstance(hit,(int,np.integer)) else index[id(hit)]
            other,other_coeff=br[j];intersection=p.intersection(other)
            pieces=list(intersection.geoms) if hasattr(intersection,'geoms') else [intersection]
            for piece in pieces:
                if piece.geom_type!='Polygon' or piece.area<=1e-15:continue
                xy=np.asarray(piece.exterior.coords)
                gaps=np.column_stack((xy,np.ones(len(xy))))@(coeff-other_coeff)
                low=min(low,float(gaps.min()));high=max(high,float(gaps.max()))
    if not np.isfinite([low,high]).all():raise GeometryUnavailable('patch overlap could not resolve linear material layer gaps')
    shortfall=max(0.,min_gap_m-low);excess=max(0.,high-max_gap_m)
    result.update(minimum_layer_gap_m=low,maximum_layer_gap_m=high,
        layer_gap_shortfall_m=shortfall,layer_gap_excess_m=excess,gap_observed=True,
        passed=bool(fraction>=min_overlap_fraction and shortfall<=tolerance_m and excess<=tolerance_m))
    return result
