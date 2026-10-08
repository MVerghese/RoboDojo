"""Stable endpoints cannot hide a moving or unsupported settling window."""
from copy import deepcopy
import unittest
from task.atomic.session import AtomicSession
from task.atomic.settling_validation import validate_settling
from scripts.atomic.audit_scores import apply_recognition_validation
from test_atomic_physical_runtime import World,stage as physical_stage,recognition
from test_atomic_persistent_support import world as support_world


def retained_settling():
    c=recognition('supported_release');c['support_labels']=['support']
    backend,_=support_world();support=backend.support_evidence('object',['support'],0)
    pose=[0,0,0,1,0,0,0];hold={'resolved_arm':'left','contact_interval_start_step':1,'consecutive_contact_steps':5}
    final={'physics_step':12,'held_contact':deepcopy(hold),'pose':pose,'stable_steps':3,
        'settle_anchor_pose':pose,'settle_anchor_step':10,'settle_displacement_m':0.,'settle_angle_rad':0.,
        'transport_m':.03,'support':support,'robot_touching':False,'separated_since_step':10,'separated_steps':3,
        'settling_samples':[{'physics_step':step,'pose':deepcopy(pose),'dt_s':.01,'robot_touching':False,
                             'support':deepcopy(support)} for step in range(10,13)]}
    return {'recognition':c,'physical_events':{'release':{'physics_step':9,'held_contact':hold},'settled':final}}


class SettlingWitnessTests(unittest.TestCase):
    def test_actual_stable_window_reproduces_duration_motion_and_support(self):
        result=validate_settling(retained_settling())
        self.assertEqual(result['status'],'consistent_evidence')
        self.assertAlmostEqual(result['metrics']['observed_duration_s'],.02)
        self.assertEqual(result['metrics']['max_position_step_m'],0)

    def test_same_endpoints_do_not_hide_midwindow_motion_or_rotations(self):
        for pose,failed in (([.005,0,0,1,0,0,0],'settling_step_bounds'),
                            ([0,0,0,0,0,0,1],'settling_anchor_bounds')):
            s=retained_settling();s['physical_events']['settled']['settling_samples'][1]['pose']=pose
            result=validate_settling(s)
            self.assertEqual(result['status'],'inconsistent_evidence');self.assertIn(failed,result['failed_checks'])

    def test_clock_force_identity_and_robot_recontact_cannot_be_hidden(self):
        for change,failed in (
            (lambda e:e['settling_samples'][1].__setitem__('physics_step',10),'settling_contiguous_window'),
            (lambda e:e['settling_samples'][1]['support']['contacts'][0].__setitem__('impulse',[0,0,-.01]),'settling_support_forces'),
            (lambda e:e['settling_samples'][1]['support'].__setitem__('object','other'),'settling_named_support'),
            (lambda e:e['settling_samples'][1].__setitem__('robot_touching',True),'settling_recorded_robot_separation'),
            (lambda e:e['settling_samples'][1].__setitem__('dt_s',.02),'settling_fixed_dt'),
            (lambda e:e.__setitem__('settle_displacement_m',.0005),'settling_final_residuals'),
        ):
            s=retained_settling();change(s['physical_events']['settled']);result=validate_settling(s)
            self.assertEqual(result['status'],'inconsistent_evidence');self.assertIn(failed,result['failed_checks'])

    def test_corrupted_pose_window_excludes_cached_settled_geometry(self):
        s=retained_settling();s['physical_events']['settled']['settling_samples'][1]['pose'][0]=.005
        s['conditions']=[{'id':'placed','event':{'kind':'recognition_event','name':'settled'}}]
        scores={'conditions':{'placed':{'status':'reproduced','recorded_result':{'error':0.}}}}
        apply_recognition_validation(s,scores)
        self.assertEqual(scores['conditions']['placed']['status'],'invalid_recognition_window')
        self.assertEqual(scores['conditions']['placed']['recorded_result']['error'],0.)

    def test_missing_historical_motion_remains_partial(self):
        s=retained_settling();s['physical_events']['settled'].pop('settling_samples')
        self.assertEqual(validate_settling(s)['status'],'partial_evidence')
        s['physical_events'].pop('settled')
        self.assertEqual(validate_settling(s)['status'],'unobserved')

    def test_runtime_resets_history_after_motion_and_records_first_qualified_window(self):
        w=World();w.env.dt=.01;w.hold();s=AtomicSession(w.env,physical_stage('supported_release'),0)
        w.tick(s,2);w.poses['object'][0]=.03;w.tick(s);w.release();w.tick(s)
        w.poses['object'][0]=.05;w.tick(s);w.tick(s,2)
        final=s.summary()['physical_events']['settled'];samples=final['settling_samples']
        self.assertEqual([p['physics_step'] for p in samples],list(range(final['physics_step']-2,final['physics_step']+1)))
        self.assertEqual(final['settle_anchor_step'],samples[0]['physics_step'])
        self.assertTrue(all(p['pose'][0]==.05 for p in samples))


if __name__=='__main__':unittest.main()
