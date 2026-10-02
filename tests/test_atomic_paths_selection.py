"""Adversarial temporal/identity cases, rather than endpoint-only examples."""
from copy import deepcopy
from dataclasses import replace
import math
import unittest

import numpy as np
from test_atomic_physical_runtime import World, stage
from task.atomic.spec import AtomicStage
from task.atomic.session import AtomicSession
from task.atomic.trajectory import path_sample, aggregate_path
from scripts.atomic.audit_scores import audit_atomic


def endpoint_stage(**extra):
    return AtomicStage.from_dict({'id':'move','family':'place','instruction':'Move the object',
        'success_checks':[{'name':'is_test_goal','args':{}}],'geometry':[],**extra})


def path_definition(**extra):
    return {'id':'path','slot':'sweep segment','measurement':{'kind':'object_position','label':'object'},
        'reference':{'kind':'object_pose','label':'target'},'expected':[[0,0,0],[.1,0,0]],
        'axes':[0,1],'tolerance':.005,'min_samples':3,'start_event':{'kind':'stage_start'},
        'end_event':{'kind':'stage_success'},**extra}


def pre_condition():
    return {'id':'approach','slot':'hand approach','kind':'relative_displacement',
        'measurement':{'kind':'object_pose','label':'object'},'reference':{'kind':'object_pose','label':'target'},
        'expected':[.01,0,0],'tolerance':.001,
        'event':{'kind':'before_contact','measurement':{'kind':'contact_points','label':'object','arm':'any'}}}


def selection_definition(**extra):
    return {'candidates':['object','other'],'arm':'any','min_finger_bodies':2,'min_contact_steps':2,
        'conditions':[{'id':'referent','slot':'object','kind':'point','measurement':{'kind':'object_position','label':'@candidate'},
                       'expected':[0,0,0],'tolerance':.01}],**extra}


def strike_stage():
    return AtomicStage.from_dict({'id':'strike','family':'touch_with_tool','instruction':'Strike and raise the mallet',
        'success_checks':[{'name':'is_atomic_interaction','args':{}}], 'recognition':{
            'kind':'held_tool_strike','label':'object','arm':'any','min_contact_steps':2,'target_label':'target',
            'tool_point':{'kind':'object_pose','label':'object'},'target_point':{'kind':'object_pose','label':'target'},
            'tool_radius_m':.04,'target_radius_m':.04,'min_impulse_ns':.005,
            'min_approach_speed_m_s':.1,'min_retraction_m':.025,'min_retraction_steps':2,'max_retraction_steps':8}})


def strike_world():
    w=World(); w.env.dt=.01
    old=w.contacts.resolve_object_pair
    def pair(selector,idx):
        _,source=old(selector,idx)
        return {'points':[[0,0,0]],'position':[0,0,0]},source
    w.contacts.resolve_object_pair=pair
    return w


def impact(w,s):
    w.hold(); w.poses['object'][2]=.03; w.tick(s)
    w.poses['object'][2]=.02; w.tick(s)
    w.poses['object'][2]=0.; w.contacts.pairs=True
    return w.tick(s)


class TemporalGeometryTests(unittest.TestCase):
    def test_before_contact_uses_previous_pose_and_reference_not_contact_pose(self):
        w=World(); w.goal=False
        s=AtomicSession(w.env,endpoint_stage(geometry=[pre_condition()]),0)
        w.poses['object'][0]=.01; w.tick(s)
        w.poses['object'][0]=.3; w.poses['target'][0]=.2; w.hold(); w.tick(s)
        saved=s.summary()['geometry']['approach']
        self.assertTrue(saved['result']['passed'])
        np.testing.assert_allclose(saved['measured_state'][:3],[.01,0,0])
        self.assertEqual(saved['measurement_physics_step'],1)
        self.assertEqual(saved['event_evidence']['contact_physics_step'],2)
        self.assertEqual(audit_atomic(s.summary())['conditions']['approach']['status'],'reproduced')

    def test_before_contact_missing_or_skipped_sample_stays_unscored(self):
        for skip in (False,True):
            w=World(); w.goal=False; s=AtomicSession(w.env,endpoint_stage(geometry=[pre_condition()]),0)
            if skip:
                w.tick(s); w.contacts.steps+=3
            w.hold(); w.tick(s)
            self.assertFalse(s.summary()['geometry'])
            self.assertEqual(s.summary()['measurement_failures']['approach']['status'],'preceding_sample_missing')
            w.release(); w.tick(s); w.hold(); w.tick(s)
            self.assertFalse(s.summary()['geometry']) # Do not substitute a later attempt.
        bad=pre_condition(); bad['measurement']={'kind':'contact_points','label':'object'}
        with self.assertRaises(ValueError): endpoint_stage(geometry=[bad])

    def test_path_excursion_fails_even_with_correct_endpoints(self):
        w=World(); w.env.dt=.01; w.goal=False
        s=AtomicSession(w.env,endpoint_stage(trajectories=[path_definition()]),0)
        w.tick(s); w.poses['object'][:3]=[.05,.03,0]; w.tick(s)
        w.poses['object'][:3]=[.1,0,0]; w.goal=True; w.tick(s)
        result=s.summary()['trajectories']['path']['result']
        self.assertEqual(result['status'],'scored'); self.assertFalse(result['passed'])
        self.assertAlmostEqual(result['max_deviation_m'],.03)
        self.assertAlmostEqual(result['duration_s'],.02)
        self.assertEqual(audit_atomic(s.summary())['trajectories']['path']['status'],'reproduced')

    def test_ordered_polyline_and_backtracking_are_distinct_from_line_proximity(self):
        c=path_definition(expected=[[0,0,0],[.1,0,0],[.1,.1,0]])
        rows=[{'physics_step':i,'dt_s':.01,'measured_state':point,'reference_state':None}
              for i,point in enumerate([[0,0,0],[.1,0,0],[.1,.1,0]])]
        self.assertTrue(aggregate_path(c,rows,[],True)['passed'])
        rows[1]['measured_state']=[.1,.1,0]; rows.insert(2,{**rows[1],'physics_step':2,'measured_state':[.1,0,0]})
        rows[-1]['physics_step']=3
        result=aggregate_path(c,rows,[],True)
        self.assertFalse(result['passed']); self.assertAlmostEqual(result['backtracking_m'],.1)

    def test_closed_path_cannot_pass_with_stationary_samples_or_skipped_corners(self):
        c=path_definition(expected=[[0,0,0],[.1,0,0],[.1,.1,0],[0,0,0]])
        def samples(points):
            return [{'physics_step':i,'dt_s':.01,'measured_state':point,'reference_state':None}
                    for i,point in enumerate(points)]
        result=aggregate_path(c,samples([[0,0,0]]*5),[],True)
        self.assertFalse(result['passed']);self.assertEqual(result['visited_waypoints'],1)
        self.assertTrue(aggregate_path(c,samples(c['expected']),[],True)['passed'])
        c=path_definition(expected=[[0,0,0],[.1,0,0],[.1,.1,0]])
        result=aggregate_path(c,samples([[0,0,0],[.1,.05,0],[.1,.1,0]]),[],True)
        self.assertFalse(result['passed']) # All three samples lie on the polyline, but miss its corner.

    def test_path_gap_duplicate_chunk_calls_and_incomplete_windows(self):
        w=World(); w.env.dt=.01; w.goal=False
        s=AtomicSession(w.env,endpoint_stage(trajectories=[path_definition()]),0)
        w.tick(s); s.step(); s.step()
        self.assertEqual(len(s.summary()['trajectories']['path']['samples']),1)
        self.assertIsNone(s.summary()['trajectories']['path']['result'].get('passed'))
        w.contacts.steps+=3; w.poses['object'][0]=.05; w.tick(s)
        w.poses['object'][0]=.1; w.goal=True; w.tick(s)
        row=s.summary()['trajectories']['path']
        self.assertEqual(row['result']['status'],'coverage_failed')
        self.assertIsNone(row['result']['passed'])
        self.assertEqual(row['failures'][0]['reason'],'sampling_gap')
        tampered=deepcopy(row); tampered['failures']=[]
        self.assertEqual(aggregate_path(tampered['condition'],tampered['samples'],[],True)['status'],'coverage_failed')

    def test_path_frozen_reference_does_not_move_with_target(self):
        w=World(); w.env.dt=.01; w.goal=False
        c=path_definition(reference={'kind':'object_pose','label':'target','time':'stage_start'})
        s=AtomicSession(w.env,endpoint_stage(trajectories=[c]),0)
        w.tick(s); w.poses['target'][0]=3.; w.poses['object'][0]=.05; w.tick(s)
        w.poses['object'][0]=.1; w.goal=True; w.tick(s)
        self.assertTrue(s.summary()['trajectories']['path']['result']['passed'])
        # Identical point motion around a live moving frame describes a different path.
        self.assertGreater(path_sample(c,[.1,0,0],w.poses['target'])['deviation_m'],2.)

    def test_initial_selection_records_wrong_object_before_objects_move(self):
        w=World(); w.goal=False; w.poses['other'][0]=.2
        s=AtomicSession(w.env,endpoint_stage(selection=selection_definition()),0)
        w.poses['other'][0]=0.; w.poses['object'][0]=.2 # Move them after initial candidate snapshot.
        w.hold(label='other'); w.tick(s); w.tick(s)
        row=s.summary()['selection']
        self.assertEqual(row['eligible_candidates'],['object']);self.assertFalse(row['passed'])
        self.assertEqual(row['observed']['contacts'][0]['label'],'other')
        audit=audit_atomic(s.summary())['selection'];self.assertEqual(audit['status'],'reproduced')
        self.assertFalse(audit['passed'])

    def test_selection_ambiguity_and_simultaneous_grasps_are_not_guessed(self):
        w=World(); w.goal=False; s=AtomicSession(w.env,endpoint_stage(selection=selection_definition()),0)
        w.hold(); w.tick(s); w.tick(s)
        self.assertEqual(s.summary()['selection']['target_status'],'ambiguous_target')
        self.assertIsNone(s.summary()['selection']['passed'])
        w=World(); w.goal=False; w.poses['other'][0]=.2
        s=AtomicSession(w.env,endpoint_stage(selection=selection_definition()),0)
        w.hold();w.hold(label='other');w.tick(s);w.tick(s)
        self.assertEqual(s.summary()['selection']['status'],'ambiguous_contact')
        self.assertIsNone(s.summary()['selection']['passed'])

    def test_selection_one_finger_or_arm_switch_cannot_form_a_grasp(self):
        w=World(); w.goal=False; w.poses['other'][0]=.2
        s=AtomicSession(w.env,endpoint_stage(selection=selection_definition()),0)
        w.hold(fingers=1);w.tick(s);w.tick(s)
        self.assertIsNone(s.summary()['selection']['observed'])
        w.hold();w.tick(s);w.release();w.hold(arm='right');w.tick(s)
        self.assertIsNone(s.summary()['selection']['observed'])
        w.tick(s);self.assertTrue(s.summary()['selection']['passed'])

    def test_variants_preserve_path_and_selection_and_do_not_relax_recognition(self):
        original=endpoint_stage(trajectories=[path_definition()],selection=selection_definition())
        changed=original.with_variant({'stage_id':'move','instruction':'different prompt'})
        self.assertEqual(changed.trajectories,original.trajectories)
        self.assertEqual(changed.selection,original.selection)


class StrikeTests(unittest.TestCase):
    def test_impact_needs_approach_contact_and_held_retraction(self):
        w=strike_world();s=AtomicSession(w.env,strike_stage(),0)
        self.assertFalse(impact(w,s))
        self.assertIn('impact',s.summary()['physical_events'])
        w.poses['object'][2]=.04; self.assertFalse(w.tick(s)) # Still touching target.
        w.contacts.pairs=False; self.assertFalse(w.tick(s))
        self.assertTrue(w.tick(s))
        evidence=s.summary()['interaction_evidence']
        self.assertAlmostEqual(evidence['impact']['toward_surface_speed_m_s'],1.)
        self.assertEqual(evidence['separated_steps'],2)
        self.assertEqual(set(s.summary()['physical_events']),{'impact','retracted','strike'})

    def test_resting_contact_and_moving_target_cannot_borrow_approach_speed(self):
        w=strike_world();s=AtomicSession(w.env,strike_stage(),0)
        w.hold();w.tick(s);w.tick(s);w.contacts.pairs=True
        self.assertFalse(w.tick(s));self.assertFalse(s.summary()['physical_events'])
        w=strike_world();s=AtomicSession(w.env,strike_stage(),0)
        w.hold();w.poses['object'][2]=.03;w.tick(s)
        w.poses['object'][2]=.02;w.poses['target'][2]=-.01;w.tick(s)
        w.contacts.pairs=True;self.assertFalse(w.tick(s));self.assertFalse(s.summary()['physical_events'])

    def test_wrong_tip_low_impulse_and_sampling_gap_do_not_strike(self):
        for mode in ('wrong_tip','low_impulse','gap'):
            w=strike_world();s=AtomicSession(w.env,strike_stage(),0)
            w.hold();w.poses['object'][2]=.03;w.tick(s)
            w.poses['object'][2]=.02;w.tick(s)
            if mode=='wrong_tip':w.poses['object'][0]=.2
            if mode=='low_impulse':w.contacts.impulse=.0001
            if mode=='gap':w.contacts.steps+=3
            w.contacts.pairs=True;w.poses['object'][2]=0.;w.tick(s)
            self.assertFalse(s.summary()['physical_events'])

    def test_release_and_late_unrelated_raise_cannot_complete_strike(self):
        for mode in ('release','timeout'):
            w=strike_world();s=AtomicSession(w.env,strike_stage(),0);impact(w,s)
            if mode=='release':w.release()
            else:
                for _ in range(9):w.tick(s)
            w.contacts.pairs=False;w.poses['object'][2]=.1
            self.assertFalse(w.tick(s));self.assertFalse(w.tick(s))
