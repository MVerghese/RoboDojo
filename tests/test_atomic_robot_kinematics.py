"""Equal object poses must not hide different robot motion or gripper opening."""
from copy import deepcopy
import math
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import numpy as np

from task.atomic.robot_kinematics import capture_robot_joints, compare_robot_joints, _container, _joint_schema


ROOT = '/World/envs/env_0/robot0/base_link'
ASSET = '/World/envs/env_0/robot0'


def robot_session():
    key = SimpleNamespace(root_physx_view=SimpleNamespace(prim_paths=[ROOT]),
        cfg=SimpleNamespace(prim_path='{ENV_REGEX_NS}/robot0'), joint_names=['elbow', 'jaw'],
        data=SimpleNamespace(joint_pos=np.array([[.2, .01]]), joint_vel=np.array([[.3, .002]])))
    manager = SimpleNamespace(robot_list=[SimpleNamespace(), SimpleNamespace()], robot_key=[key, key],
        scene=SimpleNamespace(env_prim_paths=['/World/envs/env_0']))
    return SimpleNamespace(env_idx=0, env=SimpleNamespace(robot_manager=manager, _atomic_contacts=SimpleNamespace(steps=25)))


def schema(container, names):
    return [{'name': name, 'joint_path': container+'/joints/'+name,
             'kind': 'revolute' if name=='elbow' else 'prismatic'} for name in names]


class RobotKinematicsTests(unittest.TestCase):
    def capture(self):
        session=robot_session()
        with patch('task.atomic.robot_kinematics._joint_schema', side_effect=schema):
            return session,capture_robot_joints(session)

    def test_capture_copies_solver_state_and_deduplicates_coupled_arms(self):
        session,a=self.capture()
        self.assertEqual(list(a['articulations']),[ROOT])
        self.assertEqual([j['position_unit'] for j in a['articulations'][ROOT]['joints']],['radians','metres'])
        self.assertEqual(a['articulations'][ROOT]['joints'][1]['velocity'],.002)
        session.env.robot_manager.robot_key[0].data.joint_pos[:]=10
        self.assertEqual(a['articulations'][ROOT]['joints'][1]['position'],.01)

    def test_joint_types_keep_independent_units_and_full_turns_are_not_wrapped(self):
        _,a=self.capture();b=deepcopy(a);joints=b['articulations'][ROOT]['joints']
        joints[0]['position']+=2*math.pi;joints[0]['velocity']+=math.pi/6
        joints[1]['position']+=.003;joints[1]['velocity']+=.004
        out=compare_robot_joints(a,b,25,25)
        self.assertEqual(out['status'],'observed_joint_comparison')
        values={j['name']:j for j in out['joints']}
        self.assertAlmostEqual(values['elbow']['position_error'],360)
        self.assertAlmostEqual(values['elbow']['velocity_error'],30)
        self.assertAlmostEqual(values['jaw']['position_error'],3)
        self.assertAlmostEqual(values['jaw']['velocity_error'],4)
        # Solver ordering can change, provided names/paths and local indices bind it.
        joints.reverse()
        for i,j in enumerate(joints):j['solver_index']=i
        reordered=compare_robot_joints(a,b,25,25)['joints']
        self.assertEqual([(j['name'],j['position_error'],j['velocity_error']) for j in reordered],
                         [(j['name'],j['position_error'],j['velocity_error']) for j in out['joints']])

    def test_wrong_joint_units_sources_paths_clocks_and_nonfinite_data_are_unavailable(self):
        _,a=self.capture()
        changes=[lambda r:r.__setitem__('physics_step',24),lambda r:r.__setitem__('environment_index',1),
            lambda r:r['source'].__setitem__('position_api','commanded_joint_position'),
            lambda r:r['joints'][0].__setitem__('position_unit','degrees'),
            lambda r:r['joints'][1].__setitem__('kind','revolute'),
            lambda r:r['joints'][0].__setitem__('joint_path',ASSET+'/different/elbow'),
            lambda r:r['joints'][0].__setitem__('solver_index',1),
            lambda r:r['joints'][0].__setitem__('position',float('nan')),
            lambda r:r['joints'].pop()]
        for change in changes:
            b=deepcopy(a);change(b['articulations'][ROOT])
            out=compare_robot_joints(a,b,25,25)
            self.assertEqual(out['status'],'unavailable');self.assertEqual(out['joints'],[])
        self.assertEqual(compare_robot_joints(None,a,25,25)['status'],'unavailable')
        session=robot_session();session.env.robot_manager.robot_key[0].data.joint_vel[:]=float('inf')
        with patch('task.atomic.robot_kinematics._joint_schema',side_effect=schema):
            self.assertEqual(capture_robot_joints(session)['status'],'unavailable')
        self.assertEqual(capture_robot_joints(SimpleNamespace(env=SimpleNamespace(),env_idx=0))['status'],'unavailable')

    def test_actual_articulation_root_cannot_bind_adjacent_environment_or_robot(self):
        self.assertEqual(_container(ROOT,'/World/envs/env_0','{ENV_REGEX_NS}/robot0'),ASSET)
        for root,expression in [(ROOT.replace('env_0','env_1'),'{ENV_REGEX_NS}/robot0'),
                (ROOT,'{ENV_REGEX_NS}/robot1'),(ROOT,'{ENV_REGEX_NS}/.*')]:
            with self.assertRaises(ValueError):_container(root,'/World/envs/env_0',expression)

    def test_live_usd_name_ambiguity_and_unsupported_joint_type_fail_closed(self):
        revolute=object();prismatic=object()
        def prim(name,kind):
            return SimpleNamespace(GetName=lambda:name,IsA=lambda cls:cls is kind,
                GetPath=lambda:ASSET+'/joints/'+name)
        children=[prim('elbow',revolute),prim('jaw',prismatic)]
        root=SimpleNamespace(IsValid=lambda:True)
        usd=SimpleNamespace(get_context=lambda:SimpleNamespace(get_stage=lambda:SimpleNamespace(GetPrimAtPath=lambda path:root)))
        pxr=SimpleNamespace(Usd=SimpleNamespace(PrimRange=lambda p:children),
            UsdPhysics=SimpleNamespace(RevoluteJoint=revolute,PrismaticJoint=prismatic))
        with patch.dict('sys.modules',{'omni':SimpleNamespace(usd=usd),'omni.usd':usd,'pxr':pxr}):
            self.assertEqual([j['kind'] for j in _joint_schema(ASSET,['elbow','jaw'])],['revolute','prismatic'])
            children.append(prim('elbow',revolute))
            with self.assertRaises(ValueError):_joint_schema(ASSET,['elbow','jaw'])
            children[:]=[prim('elbow',None),prim('jaw',prismatic)]
            with self.assertRaises(ValueError):_joint_schema(ASSET,['elbow','jaw'])

    def test_replay_report_keeps_four_joint_columns_separate_from_object_units(self):
        from scripts.atomic.continuous_report import replay_validation_rows,REPLAY_HEADERS
        _,a=self.capture();b=deepcopy(a)
        b['articulations'][ROOT]['joints'][0]['position']+=math.pi/6
        b['articulations'][ROOT]['joints'][1]['velocity']+=.004
        comparison=compare_robot_joints(a,b,25,25)
        data={'replay_validations':[{'task':'task','episodes':[{'atomic_start':{'stage_id':'s'},
            'boundary_position_comparison':{'robot_kinematics':comparison}}]}]}
        row=replay_validation_rows(data)[0]
        self.assertEqual(row[-4:],['30.0000','0.0000','0.0000','4.0000'])
        self.assertEqual(row[-8:-4],['N/A']*4)
        self.assertEqual(len(row),len(REPLAY_HEADERS))


if __name__=='__main__':unittest.main()
