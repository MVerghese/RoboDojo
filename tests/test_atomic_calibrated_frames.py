"""Calibrated offsets follow live rigid roots; gripper arm needs real contact."""
from types import SimpleNamespace as NS
import unittest
import numpy as np
from test_atomic_physical_runtime import World
from task.atomic.contacts import ContactUnavailable
from task.atomic.session import AtomicSession
from task.atomic.spec import AtomicStage, _validate_selector
from task.atomic.geometry import _rotation


class CalibratedFrameTests(unittest.TestCase):
    def world(self):
        w=World();lm=w.env.scene_manager.layout_manager
        lm.get_instance_name=lambda env_idx,label:label
        lm.instance_type_by_env=[{'object':'rigid','target':'geometry'}]
        stage=AtomicStage.from_dict({'id':'s','family':'insert','instruction':'Observe',
            'success_checks':[{'name':'is_atomic_interaction','args':{}}]})
        return w,AtomicSession(w.env,stage,0)

    def test_offset_and_orientation_compose_with_live_root_once(self):
        w,s=self.world();w.poses['object'][:3]=[1,2,3]
        w.poses['object'][3:]=[2**-.5,0,0,2**-.5]
        c={'kind':'calibrated_frame','label':'object','local_pose':[.02,0,0,1,0,0,0],
           'calibration_id':'reviewed mouth mesh example'}
        _validate_selector(c,'mouth');p,source=s._resolve_with_source(c)
        np.testing.assert_allclose(p[:3],[1,2.02,3]);np.testing.assert_allclose(_rotation(p[3:]),_rotation(w.poses['object'][3:]),atol=1e-8)
        w.poses['object'][0]+=1
        np.testing.assert_allclose(s._resolve(c)[:3],[2,2.02,3])
        self.assertIn('root_pose',source)

    def test_no_rigid_root_proxy_for_articulated_or_cloth_and_no_empty_provenance(self):
        w,s=self.world();c={'kind':'calibrated_frame','label':'object','local_pose':[0,0,0,1,0,0,0],'calibration_id':'review'}
        for category in ['articulation','garment','fluid']:
            w.env.scene_manager.layout_manager.instance_type_by_env[0]['object']=category
            with self.assertRaisesRegex(RuntimeError,'rigid/static'):s._resolve(c)
        c['calibration_id']=''
        with self.assertRaisesRegex(ValueError,'provenance'):_validate_selector(c,'bad')

    def test_contacting_gripper_does_not_choose_nearest_uncontacted_arm(self):
        w,s=self.world();left=NS(arm_name='left');right=NS(arm_name='right')
        poses={'left':np.array([0,0,0,1,0,0,0]),'right':np.array([1,0,0,0,1,0,0])}
        w.env.robot_manager=NS(robot_list=[left,right],get_real_endpose=lambda r,**kw:[poses[r.arm_name]])
        c={'kind':'robot_ee_pose','label':'object','arm':'contacting','min_finger_bodies':2}
        with self.assertRaises(ContactUnavailable):s._resolve(c)
        w.hold(arm='right');p,source=s._resolve_with_source(c)
        np.testing.assert_allclose(p,poses['right']);self.assertEqual(source['resolved_arm'],'right')
        self.assertIn('arm_contact_evidence',source)


if __name__=='__main__':unittest.main()
