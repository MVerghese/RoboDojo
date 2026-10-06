"""Bind material regions to authored topology before policy deformation."""
import hashlib
import heapq
import numpy as np


def material_edge_path(vertices, triangles, start_id, end_id, asset_sha256):
    """Reviewable shortest authored edge path; persistent IDs, never live proximity.

    This selects a material line between declared anatomical anchors. It does
    not infer the location of a physical fold or crease.
    """
    v = np.asarray(vertices, dtype=float)
    t = np.asarray(triangles)
    if (v.ndim != 2 or v.shape[1] != 3 or not np.isfinite(v).all()
            or t.ndim != 2 or t.shape[1] != 3 or t.dtype.kind not in 'iu' or not len(t) or t.min() < 0 or t.max() >= len(v)
            or type(start_id) is not int or type(end_id) is not int
            or not 0 <= start_id < len(v) or not 0 <= end_id < len(v) or start_id == end_id):
        raise ValueError('material path needs actual authored mesh and two distinct valid vertex anchors')
    graph = [{} for _ in v]
    for face in t:
        for i, j in zip(face, np.roll(face, -1)):
            length = float(np.linalg.norm(v[i]-v[j]))
            if length > 0:
                graph[i][int(j)] = length
                graph[j][int(i)] = length
    distances = {start_id: 0.}
    previous = {}
    queue = [(0., start_id)]
    while queue:
        distance, i = heapq.heappop(queue)
        if distance != distances[i]:
            continue
        if i == end_id:
            break
        for j, length in sorted(graph[i].items()):
            candidate = distance+length
            if candidate < distances.get(j, float('inf')):
                distances[j] = candidate
                previous[j] = i
                heapq.heappush(queue, (candidate, j))
    if end_id not in distances:
        raise ValueError('material anchors belong to disconnected mesh components')
    ids = [end_id]
    while ids[-1] != start_id:
        ids.append(previous[ids[-1]])
    ids.reverse()
    if len(ids) > 128:
        raise ValueError('authored material path exceeds the bounded curve size; do not skip edges')
    return {'ids': ids, 'asset_sha256': asset_sha256,
            'topology_sha256': hashlib.sha256(np.asarray(t, dtype='<i8').tobytes()).hexdigest()}


def material_patch(vertices,triangles,seed_ids,radius_m,asset_sha256):
    """Same-side initial geodesic patch, with an initially upward tangent basis.

    Distance follows actual mesh edges, so nearby disconnected layers cannot
    silently become the measured material. Face IDs remain fixed after binding.
    This selects a local material patch, not an entire sleeve/body region.
    """
    v=np.asarray(vertices,dtype=float);t=np.asarray(triangles,dtype=np.int64)
    if (v.ndim!=2 or v.shape[1]!=3 or not np.isfinite(v).all() or t.ndim!=2 or t.shape[1]!=3
            or not len(t) or t.min()<0 or t.max()>=len(v) or not np.isfinite(radius_m) or radius_m<=0):
        raise ValueError('material patch needs finite authored mesh, valid faces and positive physical radius')
    if not seed_ids or any(type(i) is not int or not 0<=i<len(v) for i in seed_ids):
        raise ValueError('material patch seed IDs must belong to the authored mesh')
    graph=[{} for _ in v]
    for face in t:
        for i,j in zip(face,np.roll(face,-1)):
            length=float(np.linalg.norm(v[i]-v[j]));graph[i][int(j)]=length;graph[j][int(i)]=length
    distances=np.full(len(v),float('inf'));queue=[]
    for seed in seed_ids:distances[seed]=0.;heapq.heappush(queue,(0.,seed))
    while queue:
        distance,i=heapq.heappop(queue)
        if distance!=distances[i]:continue
        for j,length in graph[i].items():
            candidate=distance+length
            if candidate<=radius_m and candidate<distances[j]:
                distances[j]=candidate;heapq.heappush(queue,(candidate,j))
    q=v[t];normals=np.cross(q[:,1]-q[:,0],q[:,2]-q[:,0]);areas=np.linalg.norm(normals,axis=1)
    unit=np.divide(normals,areas[:,None],out=np.zeros_like(normals),where=areas[:,None]>1e-15)
    incident=np.flatnonzero(np.isin(t,seed_ids).any(1)&(areas>1e-15))
    if not len(incident):raise ValueError('material patch seed has no nondegenerate topology face')
    first=int(incident[np.argmax(np.abs(unit[incident,2]))]);normal=unit[first]
    selected=np.flatnonzero((distances[t]<=radius_m).all(1)&(areas>1e-15)&(unit@normal>=.5))
    if not len(selected):raise ValueError('no complete same-side material faces fit the declared geodesic radius')
    basis=int(selected[np.argmax(np.abs(normals[selected,2]))]);ids=t[basis].tolist()
    if unit[basis,2]<0:ids[1],ids[2]=ids[2],ids[1]
    return {'face_ids':selected.tolist(),'origin_id':ids[0],'x_id':ids[1],'y_id':ids[2],
            'asset_sha256':asset_sha256,'topology_sha256':hashlib.sha256(np.asarray(t,dtype='<i8').tobytes()).hexdigest()}
