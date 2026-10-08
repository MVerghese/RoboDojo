"""Activation-time robot solver joints, bound to live USD joint types and paths."""
from copy import deepcopy
import math
import re
import numpy as np


def _values(value, count):
    if hasattr(value, 'detach'):
        value = value.detach().cpu().numpy()
    result = np.asarray(value, dtype=float)
    if result.shape != (count,) or not np.isfinite(result).all():
        raise ValueError('invalid solver joint vector')
    return result.copy()


def _joint_schema(container, names):
    """Names must uniquely identify actual typed joint prims in this robot subtree."""
    import omni.usd
    from pxr import Usd, UsdPhysics
    prim = omni.usd.get_context().get_stage().GetPrimAtPath(container)
    if not prim or not prim.IsValid():
        raise ValueError('robot asset subtree absent')
    found = {name: [] for name in names}
    for child in Usd.PrimRange(prim):
        name = child.GetName()
        if name not in found:
            continue
        kind = ('revolute' if child.IsA(UsdPhysics.RevoluteJoint) else
                'prismatic' if child.IsA(UsdPhysics.PrismaticJoint) else None)
        if kind:
            found[name].append({'name': name, 'joint_path': str(child.GetPath()), 'kind': kind})
    if any(len(rows) != 1 for rows in found.values()):
        raise ValueError('joint name absent, ambiguous or unsupported in live robot USD')
    return [found[name][0] for name in names]


def _container(root, environment_root, expression):
    if (not isinstance(root, str) or not isinstance(environment_root, str)
            or not environment_root.startswith('/') or not root.startswith(environment_root + '/')):
        raise ValueError('solver articulation outside the selected environment')
    expression = expression.replace('{ENV_REGEX_NS}', re.escape(environment_root))
    matches = []
    path = root
    while path.startswith(environment_root + '/'):
        if re.fullmatch(expression, path):
            matches.append(path)
        path = path.rsplit('/', 1)[0]
    if len(matches) != 1:
        raise ValueError('configured robot subtree does not uniquely bind solver root')
    return matches[0]


def capture_robot_joints(session):
    """Capture solver state and separately identified commanded drive targets."""
    result = {}; step = getattr(getattr(session.env, '_atomic_contacts', None), 'steps', None)
    manager = getattr(session.env, 'robot_manager', None)
    if manager is None or not getattr(manager, 'robot_list', None):
        return {'status': 'unavailable', 'reason': 'robot manager or robot list absent', 'articulations': {}}
    for index, robot in enumerate(manager.robot_list):
        row = {'environment_index': session.env_idx, 'physics_step': step}
        try:
            if type(step) is not int or step < 0:
                raise ValueError('activation physics timestamp unavailable')
            key = manager.robot_key[index]
            root = key.root_physx_view.prim_paths[session.env_idx]
            environment_root = manager.scene.env_prim_paths[session.env_idx]
            container = _container(root, environment_root, key.cfg.prim_path)
            if root in result:
                # Coupled arms can share one articulation. Read every solver DOF once.
                continue
            names = list(key.joint_names)
            if (not names or len(names) > 4096 or len(set(names)) != len(names)
                    or any(not isinstance(name, str) or not name for name in names)):
                raise ValueError('invalid solver joint names')
            schema = _joint_schema(container, names)
            positions = _values(key.data.joint_pos[session.env_idx], len(names))
            velocities = _values(key.data.joint_vel[session.env_idx], len(names))
            joints = []
            for i, binding in enumerate(schema):
                angular = binding['kind'] == 'revolute'
                joints.append({**binding, 'solver_index': i,
                    'position': float(positions[i]), 'velocity': float(velocities[i]),
                    'position_unit': 'radians' if angular else 'metres',
                    'velocity_unit': 'radians_per_second' if angular else 'metres_per_second'})
            row.update(status='observed_robot_joints', articulation_root=root,
                asset_root=container, environment_root=environment_root, joints=joints,
                source={'position_api': 'IsaacLab.Articulation.data.joint_pos',
                    'velocity_api': 'IsaacLab.Articulation.data.joint_vel',
                    'binding_api': 'root_physx_view.prim_paths + joint_names + live USD joint types',
                    'articulation_class': type(key).__name__})
            row['drive_targets']=_capture_drive_targets(key,session.env_idx,joints)
            result[root] = row
        except Exception as error:
            row.update(status='unavailable', reason=type(error).__name__ + ': ' + str(error))
            result['robot_manager_index_' + str(index)] = row
    return {'status': 'observed_robot_joints' if any(r['status'] == 'observed_robot_joints' for r in result.values())
            else 'unavailable', 'articulations': result}


def _capture_drive_targets(key,env_idx,joints):
    try:
        positions=_values(key.data.joint_pos_target[env_idx],len(joints))
        velocities=_values(key.data.joint_vel_target[env_idx],len(joints))
        rows=[]
        for i,joint in enumerate(joints):
            rows.append({**{k:joint[k] for k in ('name','joint_path','kind','solver_index','position_unit','velocity_unit')},
                'position_target':float(positions[i]),'velocity_target':float(velocities[i])})
        return {'status':'observed_command_targets','joints':rows,
            'source':{'position_api':'IsaacLab.Articulation.data.joint_pos_target',
                      'velocity_api':'IsaacLab.Articulation.data.joint_vel_target'},
            'scope':'current IsaacLab command buffers; not measured position, torque or solver drive effort'}
    except Exception as error:
        return {'status':'unavailable','reason':type(error).__name__+': '+str(error)}


def _bound_joints(row, root, step):
    if row.get('status') != 'observed_robot_joints':
        raise ValueError('solver joint readback unavailable')
    if (type(step) is not int or step < 0 or row.get('physics_step') != step
            or type(row.get('environment_index')) is not int or row['environment_index'] < 0
            or row.get('articulation_root') != root):
        raise ValueError('joint activation time or articulation identity mismatch')
    container = row['asset_root']; environment_root = row['environment_root']
    if _container(root, environment_root, re.escape(container)) != container:
        raise ValueError('invalid joint asset/environment binding')
    source = row['source']
    if (source.get('position_api') != 'IsaacLab.Articulation.data.joint_pos'
            or source.get('velocity_api') != 'IsaacLab.Articulation.data.joint_vel'
            or source.get('binding_api') != 'root_physx_view.prim_paths + joint_names + live USD joint types'):
        raise ValueError('unrecognized actual joint state source')
    joints = row['joints']; bound = {}
    if not joints or len(joints) > 4096:
        raise ValueError('invalid joint count')
    for i, joint in enumerate(joints):
        name = joint['name']; path = joint['joint_path']; kind = joint['kind']
        if (not isinstance(name, str) or not name or name in bound or type(joint['solver_index']) is not int
                or joint['solver_index'] != i or not path.startswith(container + '/')
                or path.rsplit('/', 1)[-1] != name or kind not in ('revolute', 'prismatic')):
            raise ValueError('invalid or ambiguous physical joint binding')
        angular = kind == 'revolute'
        if (joint['position_unit'] != ('radians' if angular else 'metres')
                or joint['velocity_unit'] != ('radians_per_second' if angular else 'metres_per_second')
                or any(type(joint[k]) not in (float, int) or not math.isfinite(joint[k]) for k in ('position', 'velocity'))):
            raise ValueError('joint type/units or finite values invalid')
        bound[name] = joint
    return bound


def compare_robot_joints(recorded, replayed, recorded_step, replayed_step):
    """Per-joint absolute residuals without angle wrapping or a fidelity threshold."""
    scope = 'activation robot solver DOF positions/velocities and separate command-target buffers; no effort, root state or full simulator restoration'
    rows = []; unavailable = []
    drives=[];drive_unavailable=[]
    old = recorded.get('articulations') if isinstance(recorded, dict) else None
    new = replayed.get('articulations') if isinstance(replayed, dict) else None
    if not isinstance(old, dict) or not isinstance(new, dict) or not old or not new:
        return {'status': 'unavailable', 'joints': [], 'unavailable': [{'reason': 'robot joint maps absent'}], 'scope': scope}
    for root in sorted(old.keys() | new.keys()):
        try:
            a = _bound_joints(old[root], root, recorded_step); b = _bound_joints(new[root], root, replayed_step)
            if (set(a) != set(b) or any(old[root][k] != new[root][k]
                    for k in ('asset_root', 'environment_root', 'environment_index'))):
                raise ValueError('different robot/environment or joint sets')
            pending = []
            for name in sorted(a):
                x, y = a[name], b[name]
                if x['kind'] != y['kind'] or x['joint_path'] != y['joint_path']:
                    raise ValueError('physical joint binding changed')
                angular = x['kind'] == 'revolute'; scale = 180 / math.pi if angular else 1000
                pending.append({'articulation_root': root, 'name': name, 'joint_path': x['joint_path'], 'kind': x['kind'],
                    'position_error': abs(y['position'] - x['position']) * scale,
                    'velocity_error': abs(y['velocity'] - x['velocity']) * scale,
                    'position_error_unit': 'degrees' if angular else 'mm',
                    'velocity_error_unit': 'degrees_per_second' if angular else 'mm_per_second',
                    'recorded': deepcopy(x), 'replayed': deepcopy(y)})
            rows.extend(pending)
            try:
                da=_bound_drive_targets(old[root],a);db=_bound_drive_targets(new[root],b)
                for name in sorted(a):
                    x,y=da[name],db[name];angular=a[name]['kind']=='revolute';scale=180/math.pi if angular else 1000
                    drives.append({'articulation_root':root,'name':name,'kind':a[name]['kind'],'joint_path':a[name]['joint_path'],
                        'position_target_error':abs(y['position_target']-x['position_target'])*scale,
                        'velocity_target_error':abs(y['velocity_target']-x['velocity_target'])*scale,
                        'position_target_error_unit':'degrees' if angular else 'mm',
                        'velocity_target_error_unit':'degrees_per_second' if angular else 'mm_per_second',
                        'recorded':deepcopy(x),'replayed':deepcopy(y)})
            except (KeyError,ValueError,TypeError,AttributeError) as error:
                drive_unavailable.append({'articulation_root':root,'reason':str(error)})
        except (KeyError, ValueError, TypeError, AttributeError) as error:
            unavailable.append({'articulation_root': root, 'reason': str(error)})
            drive_unavailable.append({'articulation_root':root,'reason':'physical joint binding unavailable'})
    return {'status': 'observed_joint_comparison' if rows else 'unavailable',
            'joints': rows, 'unavailable': unavailable, 'scope': scope,
            'drive_targets':{'status':'observed_command_target_comparison' if drives else 'unavailable',
                'joints':drives,'unavailable':drive_unavailable,
                'scope':'current IsaacLab position/velocity target buffers only; not gains, efforts, actuator memory or full controller-state fidelity'}}


def _bound_drive_targets(row,physical):
    targets=row['drive_targets']
    if targets.get('status')!='observed_command_targets':raise ValueError('command target buffers unavailable')
    source=targets['source']
    if (source.get('position_api')!='IsaacLab.Articulation.data.joint_pos_target'
            or source.get('velocity_api')!='IsaacLab.Articulation.data.joint_vel_target'):
        raise ValueError('unrecognized command target source')
    rows=targets['joints'];bound={}
    if len(rows)!=len(physical):raise ValueError('command target DOF count mismatch')
    for joint in rows:
        name=joint['name']
        if name in bound or name not in physical:raise ValueError('command target joint name mismatch')
        if any(joint[k]!=physical[name][k] for k in ('name','joint_path','kind','solver_index','position_unit','velocity_unit')):
            raise ValueError('command target physical joint binding or units mismatch')
        if any(type(joint[k]) not in (int,float) or not math.isfinite(joint[k]) for k in ('position_target','velocity_target')):
            raise ValueError('nonfinite command target')
        bound[name]=joint
    return bound
