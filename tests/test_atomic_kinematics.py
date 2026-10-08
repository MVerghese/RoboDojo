"""Replay fidelity must expose rotation/motion even when roots coincide."""
from copy import deepcopy
import math
from types import SimpleNamespace
import unittest
import numpy as np

from task.atomic.kinematics import capture_rigid_roots,compare_rigid_roots
from task.atomic.session import AtomicSession
from task.atomic.spec import AtomicStage
from test_atomic_physical_runtime import World


def capture_world():
    w=World();w.contacts.steps=25
    w.linear=np.array([.1,.2,.3]);w.angular=np.array([0.,0.,1.])
    lm=w.env.scene_manager.layout_manager
    lm.get_instance_name=lambda env_idx,label:label
    lm.instance_type_by_env={0:{'object':'rigid'}}
    lm.get_scene_object=lambda env_idx,inst_name:SimpleNamespace(_prim_path='/World/envs/env_0/rigid/object',
        get_linear_velocity=lambda:w.linear.copy(),get_angular_velocity=lambda:w.angular.copy())
    return w


class KinematicsTests(unittest.TestCase):
    def test_replay_report_keeps_velocity_units_and_historical_missing_values(self):
        from scripts.atomic.continuous_report import replay_validation_rows,REPLAY_HEADERS
        comparison={'positions':[{'position_error_mm':.5}], 'rigid_kinematics':{'objects':[
            {'orientation_error_deg':2.,'linear_velocity_error_mm_s':3.,'angular_velocity_error_deg_s':4.}]}}
        data={'replay_validations':[{'task':'task','episodes':[{'atomic_start':{'stage_id':'s'},
            'boundary_position_comparison':comparison}]}]}
        row=replay_validation_rows(data)[0]
        self.assertEqual(row[-8:-4],['0.5000','2.0000','3.0000','4.0000'])
        self.assertEqual(row[-4:],['N/A']*4)
        self.assertEqual(len(row),len(REPLAY_HEADERS))
        comparison.pop('rigid_kinematics')
        self.assertEqual(replay_validation_rows(data)[0][-7:],['N/A']*7)

    def test_activation_capture_is_immutable_and_uses_actual_solver_velocity(self):
        w=capture_world()
        stage=AtomicStage.from_dict({'id':'pick','family':'pick','instruction':'Pick object',
            'success_checks':[{'name':'is_atomic_interaction','args':{}}],
            'recognition':{'kind':'finger_contact_motion','label':'object','arm':'any',
                'min_contact_steps':2,'motion_threshold_m':.025}})
        session=AtomicSession(w.env,stage,0)
        initial=session.summary()['initial_object_states']['object']
        self.assertEqual(initial['status'],'observed_rigid_kinematics')
        self.assertEqual(initial['linear_velocity'],[.1,.2,.3])
        self.assertEqual(initial['angular_velocity'],[0.,0.,1.])
        self.assertEqual(initial['physics_step'],25)
        w.linear[:]=9;w.poses['object'][0]=1;w.contacts.steps+=1
        self.assertEqual(session.summary()['initial_object_states']['object'],initial)

    def test_missing_unsupported_and_failed_backends_remain_unavailable(self):
        w=capture_world();session=SimpleNamespace(env=w.env,env_idx=0,
            _object_pose=lambda label:w.poses[label])
        lm=w.env.scene_manager.layout_manager
        lm.instance_type_by_env[0]['object']='articulation'
        raw=capture_rigid_roots(session,['object'])['object']
        self.assertEqual(raw['status'],'unavailable');self.assertNotIn('linear_velocity',raw)
        lm.instance_type_by_env[0]['object']='rigid';w.linear[1]=float('nan')
        self.assertEqual(capture_rigid_roots(session,['object'])['object']['status'],'unavailable')
        lm.get_scene_object=lambda **kwargs:SimpleNamespace(_prim_path='/actual/body')
        self.assertEqual(capture_rigid_roots(session,['object'])['object']['status'],'unavailable')

    def test_equal_positions_do_not_hide_rotation_or_velocity_difference(self):
        w=capture_world();session=SimpleNamespace(env=w.env,env_idx=0,_object_pose=lambda label:w.poses[label])
        a=capture_rigid_roots(session,['object']);b=deepcopy(a)
        b['object']['physics_step']=100
        b['object']['pose'][3:]=[math.sqrt(.5),0,0,math.sqrt(.5)]
        b['object']['linear_velocity'][0]+=.003
        b['object']['angular_velocity'][2]+=math.pi/6
        out=compare_rigid_roots(a,b,25,100)['objects'][0]
        self.assertEqual(out['position_error_mm'],0)
        self.assertAlmostEqual(out['orientation_error_deg'],90)
        self.assertAlmostEqual(out['linear_velocity_error_mm_s'],3)
        self.assertAlmostEqual(out['angular_velocity_error_deg_s'],30)
        b=deepcopy(a);b['object']['pose'][3]=-1
        self.assertAlmostEqual(compare_rigid_roots(a,b,25,25)['objects'][0]['orientation_error_deg'],0)

    def test_identity_source_step_units_and_nonfinite_values_cannot_be_compared(self):
        w=capture_world();session=SimpleNamespace(env=w.env,env_idx=0,_object_pose=lambda label:w.poses[label])
        a=capture_rigid_roots(session,['object'])
        for change in (
            lambda r:r.__setitem__('physics_step',24),
            lambda r:r.__setitem__('frame','object_local'),
            lambda r:r.__setitem__('object_root','/other/body'),
            lambda r:r.__setitem__('label','other'),
            lambda r:r.__setitem__('environment_index',1),
            lambda r:r.__setitem__('linear_velocity_unit','millimetres_per_second'),
            lambda r:r['source'].__setitem__('velocity_apis',['estimated_from_actions']),
            lambda r:r['pose'].__setitem__(3,0),
            lambda r:r['angular_velocity'].__setitem__(0,float('inf')),
        ):
            b=deepcopy(a);change(b['object']);result=compare_rigid_roots(a,b,25,25)
            self.assertEqual(result['status'],'unavailable');self.assertEqual(len(result['unavailable']),1)


if __name__=='__main__':unittest.main()
