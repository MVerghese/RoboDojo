#!/usr/bin/env python3
"""Bind authored hit landmarks to unique actual collision-mesh components.

This is geometry calibration, not live collider-part identity or acoustics.
"""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import sys
import numpy as np

REPO=Path(__file__).resolve().parents[2];sys.path.insert(0,str(REPO))
from task.atomic.surface_distance import point_surface_distances
from scripts.atomic.storage import atomic_write_json


def mesh_components(vertices,triangles,weld_tolerance_m):
    vertices=np.asarray(vertices,dtype=float);triangles=np.asarray(triangles)
    if (vertices.ndim!=2 or vertices.shape[1]!=3 or not np.isfinite(vertices).all()
            or triangles.ndim!=2 or triangles.shape[1]!=3 or triangles.dtype.kind not in 'iu'
            or not len(triangles) or triangles.min()<0 or triangles.max()>=len(vertices)
            or type(weld_tolerance_m) not in (float,int) or not np.isfinite(weld_tolerance_m)
            or weld_tolerance_m<=0):raise ValueError('invalid actual mesh or weld tolerance')
    # Welding assigns connectivity only; distance uses unchanged actual vertices.
    _,indices=np.unique(np.round(vertices/weld_tolerance_m).astype(np.int64),axis=0,return_inverse=True)
    parent=np.arange(indices.max()+1)
    def find(value):
        while parent[value]!=value:parent[value]=parent[parent[value]];value=parent[value]
        return value
    for face in indices[triangles]:
        roots=[find(value) for value in face]
        for value in roots[1:]:parent[value]=roots[0]
    components=defaultdict(list)
    for i,face in enumerate(triangles):components[int(find(indices[face[0]]))].append(i)
    return list(components.values())


def calibrate(asset,mesh_path,tags,weld_tolerance_m=1e-7,identity_margin_m=.002,max_anchor_distance_m=.01):
    if asset.get('status')!='exported':raise ValueError('actual exported asset required')
    if any(type(value) not in (float,int) or not np.isfinite(value) or value<=0
        for value in (identity_margin_m,max_anchor_distance_m)):raise ValueError('positive physical calibration tolerances required')
    matches=[m for m in asset['meshes'] if m['path']==mesh_path and m['has_collision_api']]
    if len(matches)!=1:raise ValueError('one explicitly named actual collision mesh required')
    mesh=matches[0];scale=np.asarray(asset['authored_root_scale'])
    if not np.allclose(scale,[1,1,1],rtol=0,atol=1e-12):
        raise ValueError('non-unit annotation scaling requires a separate reviewed binding')
    if not tags or len(set(tags))!=len(tags):raise ValueError('distinct authored landmark tags required')
    v=np.asarray(asset['root_relative_mesh']['vertices'])[mesh['point_offset']:mesh['point_offset']+mesh['points']]*scale
    offset=sum(m['triangles'] for m in asset['meshes'][:asset['meshes'].index(mesh)])
    t=np.asarray(asset['root_relative_mesh']['triangles'])[offset:offset+mesh['triangles']]-mesh['point_offset']
    components=mesh_components(v,t,weld_tolerance_m);bindings={};selected=set();excluded=[]
    for tag in tags:
        frames=np.asarray(asset['metadata']['passive']['functional'][tag]['frame'],dtype=float)
        if frames.ndim!=2 or frames.shape[1]!=7 or not len(frames) or not np.isfinite(frames).all():raise ValueError('finite authored landmark frames required')
        distances=[]
        for index,faces in enumerate(components):
            try:distance=float(point_surface_distances([frames[0,:3]],v,t[faces])[0])
            except ValueError:
                if index not in excluded:excluded.append(index)
                continue
            distances.append((distance,index))
        distances.sort()
        if (len(distances)<2 or distances[0][0]>max_anchor_distance_m
                or distances[1][0]-distances[0][0]<identity_margin_m):
            raise ValueError('landmark has no unambiguous nearby surface component: '+tag)
        distance,index=distances[0]
        if index in selected:raise ValueError('multiple landmarks alias the same mesh component')
        selected.add(index);faces=components[index];points=v[np.unique(t[faces])]
        bindings[tag]={'landmark_root_pose':frames[0].tolist(),'component_index':index,
            'triangle_indices':faces,'expected_triangles_m':v[t[faces]].tolist(),
            'component_bounds_m':[points.min(0).tolist(),points.max(0).tolist()],
            'anchor_surface_distance_m':distance,'nearest_competing_surface_distance_m':distances[1][0],
            'identity_gap_m':distances[1][0]-distance}
    root=asset['default_prim'].rstrip('/')+'/'
    if not mesh_path.startswith(root):raise ValueError('collision mesh must belong to actual default root')
    return {'asset_sha256':asset['asset_sha256'],'metadata_sha256':asset['metadata_sha256'],
        'scaled_bounds_m':asset['authored_scaled_bounds'],'mesh_path':mesh_path[len(root):],
        'weld_tolerance_m':weld_tolerance_m,'identity_margin_m':identity_margin_m,
        'max_anchor_distance_m':max_anchor_distance_m,'component_count':len(components),
        'excluded_degenerate_components':excluded,'bindings':bindings,
        'scope':'authored collision-mesh surface regions bound by distinct nearest hit landmarks; no live cooked-collider part identity, exclusive impact, sound or timing claim'}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--assets',type=Path,required=True);p.add_argument('--asset-key',required=True)
    p.add_argument('--mesh',required=True);p.add_argument('--tags',nargs='+',required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    data=json.loads(a.assets.read_text());result=calibrate(data['assets'][a.asset_key],a.mesh,a.tags)
    result.update(asset_key=a.asset_key,export_sha256=hashlib.sha256(a.assets.read_bytes()).hexdigest())
    atomic_write_json(a.output,result)
    print(json.dumps({'output':str(a.output),'components':result['component_count'],
        'bindings':{k:{field:v[field] for field in ('anchor_surface_distance_m','identity_gap_m')} for k,v in result['bindings'].items()}}))
