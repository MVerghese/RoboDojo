"""Immutable activation-time rigid root kinematics for scoped replay comparisons."""
from copy import deepcopy
import math
import numpy as np
from task.atomic.geometry import _quaternion, _angular_error


def _vector(value,size):
    if hasattr(value,'detach'):value=value.detach().cpu().numpy()
    result=np.asarray(value,dtype=float).reshape(-1)
    if result.shape!=(size,) or not np.isfinite(result).all():raise ValueError('nonfinite or incorrectly shaped live state')
    return result


def capture_rigid_roots(session,labels):
    """Read solver velocity APIs; absent/failed readbacks never become zeroes."""
    result={};step=getattr(getattr(session.env,'_atomic_contacts',None),'steps',None)
    for label in sorted(labels):
        row={'label':label,'environment_index':session.env_idx,'physics_step':step,
             'frame':'environment_local_world','pose_unit':'metres_wxyz',
             'linear_velocity_unit':'metres_per_second','angular_velocity_unit':'radians_per_second'}
        try:
            if type(step) is not int or step<0:raise ValueError('activation physics timestamp unavailable')
            lm=session.env.scene_manager.layout_manager
            name=lm.get_instance_name(env_idx=session.env_idx,label=label)
            if lm.instance_type_by_env[session.env_idx].get(name)!='rigid':
                raise ValueError('only rigid solver roots have this activation kinematics adapter')
            obj=lm.get_scene_object(env_idx=session.env_idx,inst_name=name)
            root=obj._prim_path
            if not isinstance(root,str) or not root.startswith('/'):raise ValueError('actual rigid actor path unavailable')
            pose=_vector(session._object_pose(label),7);_quaternion(pose[3:])
            linear=_vector(obj.get_linear_velocity(),3);angular=_vector(obj.get_angular_velocity(),3)
            row.update(status='observed_rigid_kinematics',object_root=root,pose=pose.tolist(),
                linear_velocity=linear.tolist(),angular_velocity=angular.tolist(),
                source={'category':'rigid','object_class':type(obj).__name__,
                        'pose_api':'LayoutManager.get_instance_pose',
                        'velocity_apis':['get_linear_velocity','get_angular_velocity']})
        except Exception as error:
            # Auxiliary fidelity evidence must not interrupt policy evaluation.
            row.update(status='unavailable',reason=type(error).__name__+': '+str(error))
        result[label]=row
    return result


def compare_rigid_roots(recorded,replayed,recorded_step,replayed_step):
    """Report independent physical-unit residuals, without asserting restoration."""
    rows=[];unavailable=[]
    scope='activation-time named rigid roots only; no robot joints, drives, materials, game state or full simulator restoration'
    if not isinstance(recorded,dict) or not isinstance(replayed,dict) or not recorded or not replayed:
        return {'status':'unavailable','objects':[], 'unavailable':[{'reason':'activation rigid readback maps absent or malformed'}], 'scope':scope}
    for label in sorted(recorded.keys()|replayed.keys()):
        try:
            a,b=recorded[label],replayed[label]
            if any(r.get('status')!='observed_rigid_kinematics' for r in (a,b)):
                raise ValueError('one or both solver readbacks unavailable')
            if type(recorded_step) is not int or type(replayed_step) is not int:
                raise ValueError('activation timestamp unavailable')
            if a['physics_step']!=recorded_step or b['physics_step']!=replayed_step:
                raise ValueError('kinematics timestamp differs from activation boundary')
            for key,value in [('label',label),('frame','environment_local_world'),('pose_unit','metres_wxyz'),
                    ('linear_velocity_unit','metres_per_second'),('angular_velocity_unit','radians_per_second')]:
                if a.get(key)!=value or b.get(key)!=value:raise ValueError('inconsistent identity, coordinate frame or units')
            if (a['object_root']!=b['object_root'] or not a['object_root'].startswith('/')
                    or type(a['environment_index']) is not int or type(b['environment_index']) is not int
                    or a['environment_index']<0 or a['environment_index']!=b['environment_index']):
                raise ValueError('different physical object/environment binding')
            for r in (a,b):
                source=r['source']
                if (source.get('category')!='rigid' or source.get('pose_api')!='LayoutManager.get_instance_pose'
                        or source.get('velocity_apis')!=['get_linear_velocity','get_angular_velocity']):
                    raise ValueError('unrecognized solver root source')
            pa,pb=_vector(a['pose'],7),_vector(b['pose'],7)
            va,vb=_vector(a['linear_velocity'],3),_vector(b['linear_velocity'],3)
            wa,wb=_vector(a['angular_velocity'],3),_vector(b['angular_velocity'],3)
            rows.append({'label':label,'object_root':a['object_root'],
                'position_error_mm':float(np.linalg.norm(pb[:3]-pa[:3])*1000),
                'orientation_error_deg':math.degrees(_angular_error(pa[3:],pb[3:])),
                'linear_velocity_error_mm_s':float(np.linalg.norm(vb-va)*1000),
                'angular_velocity_error_deg_s':math.degrees(float(np.linalg.norm(wb-wa))),
                'recorded':deepcopy(a),'replayed':deepcopy(b)})
        except (KeyError,ValueError,TypeError,AttributeError) as error:
            unavailable.append({'label':label,'reason':str(error)})
    return {'status':'observed_kinematics_comparison' if rows else 'unavailable',
        'objects':rows,'unavailable':unavailable,
        'scope':scope}
