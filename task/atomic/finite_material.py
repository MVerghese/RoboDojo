"""Conservative finite rigid-mesh bounds for sampled mouth crossings."""
import math
import numpy as np
from shapely.geometry import Point
from task.atomic.geometry import _rotation
from task.atomic.regions import validate_solid


def _mesh(vertices,triangles):
    vertices=np.asarray(vertices,dtype=float);triangles=np.asarray(triangles)
    if (vertices.ndim!=2 or vertices.shape[1]!=3 or not len(vertices) or not np.isfinite(vertices).all()
            or triangles.ndim!=2 or triangles.shape[1]!=3 or triangles.dtype.kind not in 'iu'
            or not len(triangles) or triangles.min()<0 or triangles.max()>=len(vertices)):
        raise ValueError('finite material needs actual finite vertices and integer mesh triangles')
    try:validate_solid(vertices,triangles);closed=True
    except ValueError:closed=False
    return vertices,triangles,closed


def capture_material_bound(session, label):
    row={'label':label,'environment_index':session.env_idx,
         'physics_step':getattr(getattr(session.env,'_atomic_contacts',None),'steps',None),
         'frame':'scaled_object_root_local','length_unit':'metres'}
    try:
        lm=session.env.scene_manager.layout_manager
        name=lm.get_instance_name(env_idx=session.env_idx,label=label)
        if lm.instance_type_by_env[session.env_idx].get(name)!='rigid':
            raise ValueError('finite rigid bound requires a live rigid material object')
        obj=lm.get_scene_object(env_idx=session.env_idx,inst_name=name)
        root=getattr(obj,'_prim_path',None) or getattr(obj,'prim_path',None)
        pose=np.asarray(session._object_pose(label),dtype=float)
        geometry=session.env._atomic_surfaces.resolve(label,session.env_idx,pose)
        if (not isinstance(root,str) or not root.startswith('/') or geometry['prim_path']!=root
                or geometry.get('selected_mesh_paths') is not None):
            raise ValueError('whole actual rigid material mesh binding unavailable')
        vertices=(np.asarray(geometry['vertices'],dtype=float)-pose[:3])@_rotation(pose[3:])
        vertices,triangles,closed=_mesh(vertices,geometry['triangles'])
        center=(vertices.min(0)+vertices.max(0))/2
        radius=float(np.linalg.norm(vertices-center,axis=1).max())
        row.update(status='observed_finite_rigid_bound',object_root=root,
            local_vertices_m=vertices.tolist(),triangles=triangles.tolist(),
            local_center_m=center.tolist(),enclosing_radius_m=radius,
            closed_oriented_mesh=closed,
            source='ObjectSurfaces.resolve whole scaled root-relative USD mesh triangles; no solid-volume inference')
        validate_material_bound(row)
    except Exception as error:
        row.update(status='unavailable',reason=type(error).__name__+': '+str(error))
    return row


def validate_material_bound(bound):
    if (bound.get('status')!='observed_finite_rigid_bound'
            or bound.get('frame')!='scaled_object_root_local' or bound.get('length_unit')!='metres'
            or type(bound.get('physics_step')) is not int or bound['physics_step']<0
            or type(bound.get('environment_index')) is not int or bound['environment_index']<0
            or not isinstance(bound.get('label'),str) or not bound['label']
            or not isinstance(bound.get('object_root'),str) or not bound['object_root'].startswith('/')
            or bound.get('source')!='ObjectSurfaces.resolve whole scaled root-relative USD mesh triangles; no solid-volume inference'):
        raise ValueError('finite material bound has invalid source, identity, frame or clock')
    vertices,_,closed=_mesh(bound['local_vertices_m'],bound['triangles'])
    if type(bound.get('closed_oriented_mesh')) is not bool or bound['closed_oriented_mesh']!=closed:
        raise ValueError('saved mesh closure differs from actual retained topology')
    center=(vertices.min(0)+vertices.max(0))/2
    radius=float(np.linalg.norm(vertices-center,axis=1).max())
    if (type(bound['enclosing_radius_m']) not in (int,float) or not math.isfinite(bound['enclosing_radius_m'])
            or radius<=1e-12 or not np.isclose(radius,bound['enclosing_radius_m'],rtol=1e-7,atol=1e-9)
            or np.asarray(bound['local_center_m']).shape!=(3,)
            or not np.allclose(center,bound['local_center_m'],rtol=1e-7,atol=1e-9)):
        raise ValueError('finite material radius or center differs from actual saved mesh')
    return radius


def bound_aperture_result(aperture, point, bound):
    """A mesh-enclosing sphere's projected disk must avoid every aperture boundary.

    This is sufficient, conservative fit of every finite mesh triangle at the
    interpolated center crossing. Open seams remain recorded, without filling
    them or inferring solid volume. It does not prove wall-thickness passage.
    """
    radius=validate_material_bound(bound)
    center=Point(np.asarray(point,dtype=float)[:2])
    distance=float(center.distance(aperture.boundary))
    clearance=(distance if aperture.covers(center) else -distance)-radius
    return bool(clearance>=0),{'finite_bound_radius_m':radius,
        'finite_bound_clearance_m':clearance,'finite_bound_shortfall_m':max(0.,-clearance)}
