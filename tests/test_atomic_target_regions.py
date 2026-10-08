"""Reject neighboring and ambiguous contact targets using retained physical points."""
from copy import deepcopy
from types import SimpleNamespace
import unittest

import numpy as np

from task.atomic.recognizers import PhysicalRecognizer, validate_recognition
from task.atomic.target_regions import region_membership, validate_target_regions
from scripts.atomic.validate_strike_evidence import validate_strike
from scripts.atomic.audit_scores import apply_recognition_validation
from test_atomic_strike_validation import retained_strike


def regional_strike():
    stage=retained_strike();c=stage['recognition'];c.update(label='mallet',arm='left',target_label='keys')
    c['target_candidates']=[deepcopy(c['target_point']),{**c['target_point'],'tag':'hit_1'}]
    c['target_identity_margin_m']=.002
    event=stage['physical_events']['impact']
    event['target_identity']={'kind':'nearest_landmark_region','candidate_selectors':deepcopy(c['target_candidates']),
        'candidate_poses':[[0,0,0,1,0,0,0],[.04,0,0,1,0,0,0]],
        'candidate_sources':[{**s,'frame':'environment_local_world','physics_step':101} for s in c['target_candidates']],
        'target_index':0,'margin_m':.002,'physics_step':101,'frame':'environment_local_world',
        'selected_distance_m':[0.],'nearest_competing_distance_m':[.04],'identity_gap_m':[.04]}
    return stage


class TargetRegionTests(unittest.TestCase):
    def test_pair_strengthening_retains_prompt_geometry_and_non_strike_stages(self):
        from scripts.atomic.generate_strike_region_suite import strengthen
        stages=[{'id':'pick','recognition':{'kind':'other'}}]
        for i in range(8):
            c=regional_strike()['recognition'];c.pop('target_candidates');c.pop('target_identity_margin_m')
            c['target_label']='xylophone';c['target_point'].update(label='xylophone',tag=f'hit_{i}')
            stages.append({'id':f'strike_{i}','recognition':c,'geometry':[{'id':'unchanged'}]})
        original={'geometric_instruction':'exact source prompt','stages':stages}
        changed=strengthen(original)
        self.assertEqual(changed['geometric_instruction'],original['geometric_instruction'])
        self.assertEqual(changed['stages'][0],original['stages'][0])
        for before,after in zip(original['stages'][1:],changed['stages'][1:]):
            self.assertEqual(before['geometry'],after['geometry'])
            self.assertEqual(len(after['recognition']['target_candidates']),8)
            self.assertEqual(after['recognition']['target_identity_margin_m'],.002)
            self.assertNotIn('target_candidates',before['recognition'])
        changed['stages'][2]['recognition']['target_point']['tag']='hit_0'
        with self.assertRaises(ValueError):strengthen(changed)

    def test_neighbor_overlap_and_boundary_do_not_identify_requested_target(self):
        poses=[[0,0,0,1,0,0,0],[.04,0,0,1,0,0,0]]
        result=region_membership([[.008,0,0],[.020,0,0],[.039,0,0]],poses,1,.002)
        self.assertEqual(result['eligible'],[False,False,True])
        self.assertAlmostEqual(result['selected_distance_m'][0],.032)
        self.assertAlmostEqual(result['identity_gap_m'][0],-.024)
        self.assertEqual(region_membership([[0,0,0]],[poses[0],poses[0]],0,.002)['eligible'],[False])

    def test_runtime_filters_force_rows_before_emitting_contact(self):
        c=regional_strike()['recognition'];c['target_point']=c['target_candidates'][1]
        tool=c['tool_point'];poses={s['tag']:np.array([x,0,0,1,0,0,0])
            for s,x in [(tool,.02),(c['target_candidates'][0],0),(c['target_candidates'][1],.04)]}
        session=SimpleNamespace(_resolve=lambda s:poses[s['tag']],
            _resolve_with_source=lambda s:(poses[s['tag']],{**s,'frame':'environment_local_world'}))
        recognizer=PhysicalRecognizer.__new__(PhysicalRecognizer)
        recognizer.c=c;recognizer.session=session;recognizer.contacts=SimpleNamespace(steps=101)
        pair={'measured_contact_points':{'points':[[.008,0,0],[.02,0,0],[.039,0,0]]},
              'contacts':[{'impulse':[0,0,v]} for v in (.01,.02,.03)]}
        event=recognizer._landmark_contact(pair)
        self.assertEqual(event['contact_points'],[[.039,0,0]])
        self.assertEqual(event['tool_target_contacts'],[pair['contacts'][2]])
        self.assertAlmostEqual(event['total_impulse_ns'],.03)
        self.assertEqual(event['target_identity']['all_contact_assignments']['eligible'],[False,False,True])
        self.assertTrue(all(s['physics_step']==101 for s in event['target_identity']['candidate_sources']))
        c.pop('target_candidates');c.pop('target_identity_margin_m')
        old=recognizer._landmark_contact(pair)
        self.assertEqual(len(old['contact_points']),3)
        self.assertNotIn('target_identity',old)

    def test_schema_rejects_ambiguous_or_unbound_candidate_definitions(self):
        c=regional_strike()['recognition']
        validate_recognition(c,'touch_with_tool',lambda *args:None)
        for change in (
            lambda c:c['target_candidates'].__setitem__(1,deepcopy(c['target_candidates'][0])),
            lambda c:c['target_candidates'][1].__setitem__('label','other'),
            lambda c:c['target_candidates'][1].__setitem__('time','initial'),
            lambda c:c['target_candidates'][1].__setitem__('kind','world_point'),
            lambda c:c['target_point'].__setitem__('tag','absent'),
            lambda c:c.__setitem__('target_identity_margin_m',float('nan')),
            lambda c:c.__setitem__('target_identity_margin_m',False),
            lambda c:c.pop('target_identity_margin_m'),
        ):
            changed=deepcopy(c);change(changed)
            with self.subTest(changed=changed),self.assertRaises(ValueError):
                validate_recognition(changed,'touch_with_tool',lambda *args:None)

    def test_independent_witness_rejects_changed_target_frame_and_contact(self):
        self.assertEqual(validate_strike(regional_strike())['status'],'consistent_evidence')
        for change,failed in (
            (lambda e:e['target_identity'].__setitem__('target_index',1),'target_region_binding'),
            (lambda e:e['target_identity']['candidate_sources'][0].__setitem__('tag','hit_1'),'target_region_sources'),
            (lambda e:e['target_identity']['candidate_sources'][0].__setitem__('physics_step',100),'target_region_sources'),
            (lambda e:e['target_identity']['candidate_poses'][1].__setitem__(0,0),'target_region_points'),
            (lambda e:e['target_identity']['identity_gap_m'].__setitem__(0,99),'target_region_distances'),
            (lambda e:e['contact_points'][0].__setitem__(0,.039),'target_region_points'),
            (lambda e:e['target_identity']['candidate_poses'][0].__setitem__(3,0),'target_region_fields'),
        ):
            stage=regional_strike();change(stage['physical_events']['impact'])
            result=validate_strike(stage)
            self.assertEqual(result['status'],'inconsistent_evidence')
            self.assertIn(failed,result['failed_checks'])

    def test_cached_geometry_excludes_contradictory_target_identity(self):
        stage=regional_strike();stage['physical_events']['impact']['target_identity']['identity_gap_m']=[99]
        stage['conditions']=[{'id':'point','event':{'kind':'recognition_event','name':'impact'}}]
        scores={'conditions':{'point':{'status':'reproduced','recorded_result':{'error':.004}}}}
        apply_recognition_validation(stage,scores)
        self.assertEqual(scores['conditions']['point']['status'],'invalid_recognition_window')
        self.assertEqual(scores['conditions']['point']['recorded_result']['error'],.004)
        self.assertEqual(scores['conditions']['point']['numerical_reproduction_status'],'reproduced')
        # Simple landmark contacts use the same independently checked assignment.
        stage['recognition']['kind']='held_tool_landmark_contact'
        stage['physical_events']['contact']=stage['physical_events']['impact']
        stage['conditions'][0]['event']['name']='contact'
        apply_recognition_validation(stage,scores)
        self.assertIn('target_region_distances',scores['recognition_witness']['failed_checks'])


if __name__=='__main__':unittest.main()
