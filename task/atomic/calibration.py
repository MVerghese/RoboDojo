"""Read-only live asset evidence for selecting and reviewing geometric bindings."""
from collections.abc import Mapping
import numpy as np


def primitive(value):
    if hasattr(value, 'detach'):
        value = value.detach().cpu().numpy()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Mapping):
        return {str(k): primitive(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [primitive(v) for v in value]
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    return str(value)


def opening_section(vertices,triangles,z_m,xy_m=(0.,0.)):
    """Calibrate a finite void from closed wall traces at one physical plane.

    This requires nested closed intersection loops enclosing the requested XY
    point. It certifies the opening cross-section, not a whole vessel cavity or
    a globally watertight material mesh. Open/nonmanifold traces fail closed.
    Endpoints are welded on a 1 nm grid; the bound is recorded explicitly.
    """
    from collections import Counter
    from shapely.geometry import LineString,Point,Polygon
    from shapely.ops import polygonize,unary_union
    v=np.asarray(vertices,dtype=float);t=np.asarray(triangles)
    if (v.ndim!=2 or v.shape[1]!=3 or not np.isfinite(v).all() or t.ndim!=2 or t.shape[1]!=3
            or t.dtype.kind not in 'iu' or not len(t) or t.min()<0 or t.max()>=len(v)
            or not np.isfinite(z_m)):
        raise ValueError('opening section requires finite physical mesh coordinates and valid triangles')
    points=v[t];points[:,:,2]-=z_m
    candidates=points[(points[:,:,2].min(axis=1)<0)&(points[:,:,2].max(axis=1)>0)]
    area=np.linalg.norm(np.cross(candidates[:,1]-candidates[:,0],candidates[:,2]-candidates[:,0]),axis=1)
    degenerate_count=int(np.count_nonzero(area<=1e-15));candidates=candidates[area>1e-15]
    segments=[];degrees=Counter();maximum_shift=0.
    for face in candidates:
        hits=[]
        for a,b in zip(face,np.roll(face,-1,axis=0)):
            if a[2]*b[2]<0:hits.append((a+(b-a)*(-a[2]/(b[2]-a[2])))[:2])
            elif a[2]==0:hits.append(a[:2])
        if not hits:continue
        hits=np.asarray(hits);rounded=np.round(hits,9)
        maximum_shift=max(maximum_shift,float(np.linalg.norm(rounded-hits,axis=1).max()))
        rounded=np.unique(rounded,axis=0)
        if len(rounded)==1:continue
        if len(rounded)!=2:raise ValueError('ambiguous opening-plane intersection; choose a plane away from coplanar vertices')
        a,b=map(tuple,rounded)
        if a==b:continue
        segments.append(LineString([a,b]));degrees[a]+=1;degrees[b]+=1
    if not segments or any(count!=2 for count in degrees.values()):
        raise ValueError('opening wall traces are open, duplicate or nonmanifold at this plane')
    polygons=list(polygonize(unary_union(segments)));point=Point(xy_m);rings=[]
    for p in polygons:
        for ring in [p.exterior,*p.interiors]:
            filled=Polygon(ring)
            if not any(filled.equals(other) for other in rings):rings.append(filled)
    enclosing=[ring for ring in rings if ring.covers(point)]
    if len(enclosing)<2:raise ValueError('no enclosed wall-trace void contains the requested opening point')
    if len(enclosing)%2!=0:raise ValueError('requested opening point lies in a material island')
    hole=min(enclosing,key=lambda p:p.area)
    # A material island inside the chosen void remains a forbidden aperture hole.
    enclosed=[ring for ring in rings if not ring.equals(hole) and hole.contains(ring)]
    obstacles=[p.exterior for p in enclosed if not any(not other.equals(p) and other.contains(p) for other in enclosed)]
    aperture=Polygon(hole.exterior,obstacles)
    if not aperture.is_valid:raise ValueError('opening trace void has invalid nested obstacle geometry')
    if not aperture.covers(point):raise ValueError('requested opening point lies in a material island')
    return {'z_m':float(z_m),'aperture_profile':{'outer':list(map(list,aperture.exterior.coords)),
            'holes':[list(map(list,ring.coords)) for ring in aperture.interiors]},
        'aperture_area_m2':float(aperture.area),'plane_trace_segments':len(segments),
        'maximum_endpoint_weld_displacement_m':maximum_shift,
        'ignored_zero_area_candidate_faces':degenerate_count,
        'certification':'enclosed void from closed material wall traces at this plane; not whole-cavity certification'}


def interior_core_box(vertices,triangles,center,half_extents,mouth_z_m):
    """Certify a bounded, material-free box in an observed enclosed void.

    The mid-plane footprint must lie in the measured void, no material triangle
    may touch/intersect the box, and it stays below the calibrated mouth and
    above the mesh's lowest material. This is an explicit conservative core,
    not the complete cavity. A source cohort restricted to it must be reported.
    """
    from shapely.geometry import Polygon
    from task.atomic.fit import aperture_polygon
    v=np.asarray(vertices,dtype=float);t=np.asarray(triangles);c=np.asarray(center,dtype=float);h=np.asarray(half_extents,dtype=float)
    if c.shape!=(3,) or h.shape!=(3,) or not np.isfinite([c,h]).all() or np.any(h<=0):
        raise ValueError('interior core requires finite physical center and positive half-extents')
    section=opening_section(v,t,float(c[2]),c[:2])
    footprint=Polygon([[c[0]+sx*h[0],c[1]+sy*h[1]] for sx,sy in [(-1,-1),(1,-1),(1,1),(-1,1)]])
    if not aperture_polygon(section['aperture_profile']).covers(footprint):
        raise ValueError('interior core footprint exceeds the actual enclosed void')
    if c[2]+h[2]>mouth_z_m or c[2]-h[2]<v[:,2].min():
        raise ValueError('interior core extends above the calibrated mouth or below material bounds')
    # Separating-axis theorem for each triangle and the box: 3 box normals,
    # the triangle normal and 9 triangle-edge/box-axis cross products.
    q=v[t]-c
    candidates=q[(q.min(1)<=h).all(1)&(q.max(1)>=-h).all(1)]
    intersects=np.ones(len(candidates),dtype=bool)
    edges=np.roll(candidates,-1,axis=1)-candidates
    axes=[np.broadcast_to(axis,(len(candidates),3)) for axis in np.eye(3)]
    axes.append(np.cross(edges[:,0],edges[:,1]))
    axes.extend(np.cross(edges[:,edge],axis) for edge in range(3) for axis in np.eye(3))
    for axis in axes:
        dots=np.einsum('nij,nj->ni',candidates,axis);radius=np.abs(axis)@h
        epsilon=np.linalg.norm(axis,axis=1)*1e-12
        intersects&=~((dots.min(1)>radius+epsilon)|(dots.max(1)<-radius-epsilon))
    if intersects.any():raise ValueError('actual material triangles touch or intersect the proposed interior core')
    return {'center':c.tolist(),'half_extents':h.tolist(),'volume_m3':float(np.prod(2*h)),
        'mouth_z_m':float(mouth_z_m),'midplane_section':section,
        'triangle_box_intersections':0,'certification':'bounded material-free core in measured enclosed void; not complete cavity'}


def snapshot_scene(session):
    """Export initial live frames, material IDs and asset annotations, not targets.

    This diagnostic does not establish contact, cavity geometry, or action
    recognition. Errors are retained per asset; they never become measurements.
    """
    env, idx = session.env, session.env_idx
    lm = env.scene_manager.layout_manager
    if not hasattr(lm, 'get_labels_by_prefix'):
        return {'status': 'unavailable', 'reason': 'layout inventory unavailable', 'objects': {}}
    labels = sorted(lm.get_labels_by_prefix(env_idx=idx, prefix=''))
    objects = {}
    for label in labels:
        row = {'label': label, 'errors': [], 'landmarks': {}}
        objects[label] = row
        try:
            name = lm.get_instance_name(env_idx=idx, label=label)
            category = lm.instance_type_by_env[idx][name]
            metadata = lm.get_instance_metadata(env_idx=idx, label=label)
            row.update(instance=name, category=category, metadata=primitive(metadata))
            if category in ('garment', 'fluid'):
                from task.atomic.materials import material_state
                state = material_state(env, label, 'cloth' if category == 'garment' else 'fluid', idx)
                row['material'] = {'ids': state['ids'].tolist(),
                                   'initial_positions': state['positions'].tolist(),
                                   'triangles': state.get('triangles'),
                                   'source': state['source'], 'nominal_mass_kg': state['nominal_mass_kg']}
                obj = lm.get_scene_object(env_idx=idx, inst_name=name)
                view = getattr(obj, '_cloth_prim_view', None)
                row['backend_contact_methods'] = [key for key in dir(view) if 'contact' in key or 'force' in key]
            else:
                pose = session._object_pose(label)
                row['initial_root_pose'] = pose.tolist()
                if getattr(env, '_atomic_surfaces', None) is not None:
                    surface = env._atomic_surfaces.resolve(label, idx, pose)
                    vertices = np.asarray(surface['vertices'])
                    from task.atomic.geometry import _rotation
                    local = (vertices - pose[:3]) @ _rotation(pose[3:])
                    row['local_mesh_bounds_m'] = [local.min(axis=0).tolist(), local.max(axis=0).tolist()]
                    row['surface_representation'] = surface['geometry_representation']
                    if label != 'camera_stand' and len(surface['triangles']) <= 100000:
                        row['local_mesh'] = {'vertices': local.tolist(), 'triangles': surface['triangles'],
                                             'frame': 'object_root',
                                             'interpretation': 'actual outer/material surface; not an interior annotation'}
                for role in ('active', 'passive'):
                    for category_name, kind in (('functional', 'functional_point'), ('support', 'support_point')):
                        for tag, item in metadata.get(role, {}).get(category_name, {}).items():
                            count = len(item.get('frame' if kind == 'functional_point' else 'center', []))
                            for index in range(count):
                                selector = {'kind': kind, 'label': label, 'tag': tag, 'type': role, 'index': index}
                                try:
                                    value, source = session._resolve_with_source(selector)
                                    row['landmarks'][f'{role}/{category_name}/{tag}/{index}'] = {
                                        'selector': selector, 'pose': primitive(value), 'source': primitive(source)}
                                except Exception as error:
                                    row['errors'].append(f'{tag}/{index}: {type(error).__name__}: {error}')
        except Exception as error:
            row['errors'].append(f'{type(error).__name__}: {error}')
    return {'status': 'captured', 'physics_step': getattr(getattr(env, '_atomic_contacts', None), 'steps', None),
            'coordinate_frame': 'environment_local_world', 'quaternion_order': 'wxyz',
            'objects': objects, 'interpretation': 'asset/frame evidence; cavity and contact calibration remain separate'}
