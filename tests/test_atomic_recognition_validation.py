"""Detect boundary archive corruption without trusting action success flags."""
from copy import deepcopy
import unittest
from task.atomic.recognition_validation import validate_recognition_window
from scripts.atomic.audit_scores import apply_recognition_validation


def hold(arm,start=5,count=2):
    return {'resolved_arm':arm,'contact_interval_start_step':start,'consecutive_contact_steps':count}


def handover():
    return {'recognition':{'kind':'grip_transfer','min_contact_steps':2,'giver_arm':'left',
        'receiver_arm':'right','overlap_steps':2,'receiver_steps':2},
        'physical_events':{'giver_hold':{'physics_step':6,'contact':hold('left')},
            'overlap':{'physics_step':9,'giver_contact':hold('left',5,5),'receiver_contact':hold('right',7,3)},
            'receiver_only':{'physics_step':11,'giver_contact':hold('left'),
                'receiver_contact':hold('right',7,5),'overlap_steps':2,'receiver_only_steps':2}}}


class RecognitionValidationTests(unittest.TestCase):
    def test_stale_giver_does_not_invalidate_the_valid_receiver_only_geometry(self):
        raw=handover();self.assertEqual(validate_recognition_window(raw)['status'],'consistent_boundary_evidence')
        raw['physical_events']['giver_hold']['contact']['contact_interval_start_step']=1
        result=validate_recognition_window(raw)
        self.assertEqual(result['invalid_event_names'],['giver_hold'])
        raw['conditions']=[{'id':e,'event':{'kind':'recognition_event','name':e}}
                           for e in ('giver_hold','receiver_only')]
        scores={'conditions':{e:{'status':'reproduced'} for e in ('giver_hold','receiver_only')},'trajectories':{}}
        apply_recognition_validation(raw,scores)
        self.assertEqual(scores['conditions']['giver_hold']['status'],'invalid_recognition_window')
        self.assertEqual(scores['conditions']['receiver_only']['status'],'reproduced')

    def test_receiver_reacquisition_and_attempt_mismatch_are_detected(self):
        for field in ('receiver','epoch'):
            raw=handover()
            if field=='receiver':raw['physical_events']['receiver_only']['receiver_contact']=hold('right',10)
            else:
                for event in raw['physical_events'].values():event['attempt_index']=0
                raw['physical_events']['receiver_only']['attempt_index']=1
            result=validate_recognition_window(raw)
            self.assertEqual(result['status'],'inconsistent_evidence')

    def test_entry_before_latest_hold_is_invalid_and_missing_events_are_unobserved(self):
        for kind in ('held_insertion','held_multi_tip_insertion'):
            raw={'recognition':{'kind':kind,'min_contact_steps':2,'arm':'any'},'physical_events':{
                'entry':{'physics_step':6},'inserted':{'physics_step':10,'held_contact':hold('left',8,3)}}}
            result=validate_recognition_window(raw)
            self.assertEqual(result['invalid_event_names'],['entry'])
            raw['physical_events'].pop('inserted')
            self.assertEqual(validate_recognition_window(raw)['status'],'unobserved')

    def test_release_from_another_transport_interval_fails_and_missing_metrics_stay_partial(self):
        raw={'recognition':{'kind':'supported_release','min_contact_steps':2,'settle_steps':2,
                           'transport_threshold_m':.02},'physical_events':{
            'release':{'physics_step':9,'held_contact':hold('left')},
            'settled':{'physics_step':12,'held_contact':hold('left'),'stable_steps':3,
                       'transport_m':.03,'settle_displacement_m':.001,'settle_angle_rad':.01}}}
        self.assertEqual(validate_recognition_window(raw)['status'],'consistent_boundary_evidence')
        raw['physical_events']['release']['held_contact']=hold('right')
        self.assertEqual(validate_recognition_window(raw)['invalid_event_names'],['release'])
        raw['physical_events']['release']['held_contact']=hold('left')
        raw['physical_events']['settled'].pop('transport_m')
        self.assertEqual(validate_recognition_window(raw)['status'],'partial_evidence')
