"""A whole turn needs contiguous held rotation, not an identical final quaternion."""
from copy import deepcopy
import math
import unittest
import numpy as np

from task.atomic.session import AtomicSession
from task.atomic.spec import AtomicStage
from task.atomic.twist_validation import validate_twist,validate_twist_diagnostic
from scripts.atomic.audit_scores import apply_recognition_validation
from test_atomic_physical_runtime import World,stage as physical_stage,recognition


def retained_twist():
    c=recognition('contact_constrained_twist');samples=[]
    for i in range(17):
        step=i+10;angle=i*math.pi/8
        hold={'label':'object','resolved_arm':'left','object_root':'/object','finger_bodies':['/f0','/f1'],
              'contact_interval_start_step':10,'consecutive_contact_steps':i+1,
              'contacts':[{'finger_body':f,'arm':'left','actor0':f,'actor1':'/object',
                           'impulse':[.01,0,0],'force_report_physics_step':step} for f in ('/f0','/f1')]}
        pair={'object_roots':['/object','/target'],'contacts':[{'actor0':'/object','actor1':'/target',
                    'impulse':[0,0,.01],'force_report_physics_step':step}]}
        samples.append({'physics_step':step,'object_pose':[0,0,-.01,math.cos(angle/2),0,0,math.sin(angle/2)],
                        'pivot_pose':[0,0,0,1,0,0,0],'held_contact':hold,'constraint_contact':pair})
    return {'recognition':c,'physical_events':{'rotation':{'physics_step':26,'signed_angle_rad':2*math.pi,
        'off_axis_rotation_rad':0.,'radius_m':0.,'depth_m':.01,'held_contact':deepcopy(samples[-1]['held_contact']),
        'rotation_samples':samples,'rotation_history_truncated':False}}}


class TwistWitnessTests(unittest.TestCase):
    def test_partial_interval_is_measured_without_claiming_completed_turn(self):
        s=retained_twist();event=s['physical_events']['rotation'];event['rotation_samples']=event['rotation_samples'][:5]
        event.update(physics_step=14,signed_angle_rad=math.pi/2,
                     held_contact=deepcopy(event['rotation_samples'][-1]['held_contact']))
        s['twist_rotation_diagnostic']=event;s['physical_events']={}
        result=validate_twist_diagnostic(s)
        self.assertEqual(result['status'],'consistent_evidence')
        self.assertAlmostEqual(result['metrics']['signed_angle_rad'],math.pi/2)
        self.assertEqual(validate_twist(s)['status'],'unobserved')

    def test_incomplete_turn_survives_contact_loss_as_a_diagnostic(self):
        w=World();w.hold();w.contacts.pairs=True;w.poses['object'][2]=-.01
        s=AtomicSession(w.env,physical_stage('contact_constrained_twist'),0)
        for i in range(5):
            angle=i*math.pi/8;w.poses['object'][3:]=[math.cos(angle/2),0,0,math.sin(angle/2)];w.tick(s)
        w.release();w.tick(s)
        summary=s.summary()
        self.assertFalse(summary['action_success']);self.assertNotIn('rotation',summary['physical_events'])
        self.assertAlmostEqual(summary['twist_rotation_diagnostic']['signed_angle_rad'],math.pi/2)

    def test_pivot_motion_cannot_claim_relative_twist_and_reverse_direction_is_signed(self):
        s=retained_twist()
        for row in s['physical_events']['rotation']['rotation_samples']:
            row['pivot_pose'][3:]=row['object_pose'][3:]
        result=validate_twist(s)
        self.assertAlmostEqual(result['metrics']['signed_angle_rad'],0)
        self.assertIn('rotation_declared_thresholds',result['failed_checks'])
        s=retained_twist();s['recognition']['direction']=-1
        s['physical_events']['rotation']['signed_angle_rad']=-2*math.pi
        for row in s['physical_events']['rotation']['rotation_samples']:row['object_pose'][6]*=-1
        self.assertEqual(validate_twist(s)['status'],'consistent_evidence')

    def test_full_turn_is_reproduced_from_contiguous_force_bound_pose_history(self):
        result=validate_twist(retained_twist())
        self.assertEqual(result['status'],'consistent_evidence')
        self.assertAlmostEqual(result['metrics']['signed_angle_rad'],2*math.pi)
        bad=retained_twist()
        for sample in bad['physical_events']['rotation']['rotation_samples']:
            sample['object_pose'][3:]=[1,0,0,0]
        result=validate_twist(bad)
        self.assertIn('rotation_signed_angle',result['failed_checks'])
        self.assertIn('rotation_declared_thresholds',result['failed_checks'])

    def test_stale_or_tampered_interval_force_and_constraint_witnesses_fail(self):
        for change,failed in (
            (lambda e:e['rotation_samples'].pop(4),'rotation_contiguous_samples'),
            (lambda e:e['rotation_samples'][5]['held_contact'].__setitem__('resolved_arm','right'),'rotation_same_hold_interval'),
            (lambda e:e['rotation_samples'][5]['held_contact']['contacts'][0].__setitem__('impulse',[0,0,0]),'rotation_finger_forces'),
            (lambda e:e['rotation_samples'][5]['constraint_contact']['contacts'][0].__setitem__('actor1','/other'),'rotation_constraint_actor_binding'),
            (lambda e:e['rotation_samples'][5]['object_pose'].__setitem__(0,.01),'rotation_constraint_geometry'),
            (lambda e:e.__setitem__('physics_step',27),'rotation_contiguous_samples'),
            (lambda e:e.__setitem__('signed_angle_rad',12*math.pi),'rotation_signed_angle'),
            (lambda e:e['rotation_samples'][5]['held_contact'].__setitem__('label','other'),'rotation_held_label'),
        ):
            s=retained_twist();change(s['physical_events']['rotation']);result=validate_twist(s)
            self.assertEqual(result['status'],'inconsistent_evidence');self.assertIn(failed,result['failed_checks'])

    def test_incompatible_history_cannot_enter_cached_geometry_aggregates(self):
        s=retained_twist();s['physical_events']['rotation']['rotation_samples'].pop(4)
        s['conditions']=[{'id':'angle_frame','event':{'kind':'recognition_event','name':'rotation'}}]
        output={'conditions':{'angle_frame':{'status':'reproduced','recorded_result':{'error':.01}}}}
        apply_recognition_validation(s,output)
        self.assertEqual(output['conditions']['angle_frame']['status'],'invalid_recognition_window')
        self.assertEqual(output['conditions']['angle_frame']['numerical_reproduction_status'],'reproduced')
        self.assertEqual(output['conditions']['angle_frame']['recorded_result']['error'],.01)

    def test_missing_and_truncated_history_are_partial_not_fabricated_failures(self):
        for change in (lambda e:e.pop('rotation_samples'),lambda e:e.__setitem__('rotation_history_truncated',True)):
            s=retained_twist();change(s['physical_events']['rotation'])
            self.assertEqual(validate_twist(s)['status'],'partial_evidence')
        self.assertEqual(validate_twist({'recognition':recognition('contact_constrained_twist')})['status'],'unobserved')

    def test_regrasp_after_completed_turn_cannot_keep_earlier_rotation_event(self):
        w=World();w.goal=False;w.hold();w.contacts.pairs=True;w.poses['object'][2]=-.01
        s=AtomicSession(w.env,physical_stage('contact_constrained_twist'),0)
        for i in range(17):
            angle=i*math.pi/8;w.poses['object'][3:]=[math.cos(angle/2),0,0,math.sin(angle/2)];w.tick(s)
        old=s.summary()['physical_events']['rotation']['physics_step']
        w.release();w.tick(s)
        self.assertNotIn('rotation',s.summary()['physical_events'])
        self.assertEqual(s.summary()['aborted_recognition_attempts'][0]['physical_events']['rotation']['physics_step'],old)
        w.hold();w.goal=True
        for i in range(18):
            angle=i*math.pi/8;w.poses['object'][3:]=[math.cos(angle/2),0,0,math.sin(angle/2)];w.tick(s)
        self.assertTrue(s.success)
        event=s.summary()['physical_events']['rotation']
        self.assertGreater(event['physics_step'],old)
        self.assertEqual(event['rotation_samples'][-1]['physics_step'],event['physics_step'])
        self.assertEqual(event['attempt_index'],1)


if __name__=='__main__':unittest.main()
