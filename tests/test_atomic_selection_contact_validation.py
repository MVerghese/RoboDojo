"""Selected-referent errors require the recorded physical identity witness."""
from copy import deepcopy
import unittest
from types import SimpleNamespace as NS
from test_atomic_contact_validation import sample
from task.atomic.contact_validation import validate_selection_contact_witness
from scripts.atomic.audit_scores import validate_cached_recognition
from scripts.atomic.continuous_report import collect_events


def selection():
    _,_,source=sample()
    return {'definition':{'arm':'right','min_finger_bodies':2,'min_contact_steps':2},
        'snapshot':{'object':{},'other':{}},'snapshot_physics_step':10,
        'candidate_roots':{'object':'/env/object','other':'/env/other'},'environment_index':0,
        'observed':{'physics_step':12,'contacts':[{'label':'object','contact_steps':2,'contact_source':source}]}}


class SelectionContactValidationTests(unittest.TestCase):
    def test_bounded_history_truncation_stays_partial(self):
        value=selection();value['snapshot_physics_step']=0;value['definition']['min_contact_steps']=257
        value['observed']['physics_step']=257;row=value['observed']['contacts'][0];row['contact_steps']=257
        sources=[]
        for step in range(2,258):
            s=deepcopy(row['contact_source']);s['physics_step']=step
            for c in s['contacts']:c['force_report_physics_step']=step
            sources.append(s)
        row['contact_source']=deepcopy(sources[-1])
        row['contact_history']={'sources':sources,'capacity':256,'retained_count':256,'observed_count':257,'truncated':True}
        result=validate_selection_contact_witness(value)
        self.assertEqual(result['status'],'consistent_contact_evidence')
        history=result['consecutive_contact_validation'];self.assertEqual(history['status'],'partial_evidence')
        self.assertIn('selection_force_history_truncated',history['candidates'][0]['unavailable'])

    def test_contiguous_raw_force_history_and_earlier_snapshot_corruption(self):
        value=selection();row=value['observed']['contacts'][0]
        before=deepcopy(row['contact_source']);before['physics_step']=11
        for c in before['contacts']:c['force_report_physics_step']=11
        row['contact_history']={'sources':[before,deepcopy(row['contact_source'])],
            'capacity':2,'retained_count':2,'observed_count':2,'truncated':False}
        witness=validate_selection_contact_witness(value)
        self.assertEqual(witness['consecutive_contact_validation']['status'],'consistent_evidence')
        for change in ('gap','force','root','arm','environment','copy','count','bounds'):
            bad=deepcopy(value);r=bad['observed']['contacts'][0];h=r['contact_history'];s=h['sources'][0]
            if change=='gap':s['physics_step']=10
            elif change=='force':s['contacts'][0]['impulse']=[0,0,0]
            elif change=='root':s['object_root']='/env/other'
            elif change=='arm':s['resolved_arm']='left'
            elif change=='environment':s['environment_index']=1
            elif change=='copy':h['sources'][-1]['environment_origin_world_m']=[0,0,0]
            elif change=='count':h['observed_count']=3
            else:h['capacity']=3
            with self.subTest(change=change):
                w=validate_selection_contact_witness(bad)
                self.assertEqual(w['status'],'inconsistent_contact_evidence')
                self.assertEqual(w['consecutive_contact_validation']['status'],'inconsistent_evidence')
        self.assertEqual(validate_selection_contact_witness(selection())['consecutive_contact_validation']['status'],'partial_evidence')

    def test_runtime_history_resets_on_missing_contact_and_skipped_steps(self):
        from test_atomic_physical_runtime import World
        from test_atomic_paths_selection import endpoint_stage,selection_definition
        from task.atomic.session import AtomicSession
        w=World();w.goal=False;w.poses['other'][0]=.2
        session=AtomicSession(w.env,endpoint_stage(selection=selection_definition()),0)
        w.hold();w.tick(session);w.release();w.tick(session)
        w.hold();w.tick(session)
        self.assertIsNone(session.summary()['selection']['observed'])
        w.contacts.steps+=1;w.tick(session) # Missing physics sample restarts the interval.
        self.assertIsNone(session.summary()['selection']['observed'])
        w.tick(session);row=session.summary()['selection']['observed']['contacts'][0]
        self.assertEqual([s['physics_step'] for s in row['contact_history']['sources']],[5,6])
        w.contacts.steps+=1
        self.assertEqual(row['contact_steps'],2);self.assertFalse(row['contact_history']['truncated'])

    def test_runtime_captures_initial_actual_roots_and_rejects_aliases(self):
        from test_atomic_physical_runtime import World
        from test_atomic_paths_selection import endpoint_stage,selection_definition
        from task.atomic.session import AtomicSession
        w=World();lm=w.env.scene_manager.layout_manager
        lm.get_instance_name=lambda env_idx,label:label
        roots={'object':'/env/object','other':'/env/other'}
        lm.get_scene_object=lambda env_idx,instance:NS(usd_prim_path=roots[instance])
        session=AtomicSession(w.env,endpoint_stage(selection=selection_definition()),0)
        roots['other']='/env/object'
        self.assertEqual(session.summary()['selection']['candidate_roots'],{'object':'/env/object','other':'/env/other'})
        with self.assertRaisesRegex(RuntimeError,'alias'):AtomicSession(w.env,endpoint_stage(selection=selection_definition()),0)

    def test_actual_named_force_snapshot_is_checked_without_claiming_unsaved_persistence(self):
        result=validate_selection_contact_witness(selection())
        self.assertEqual(result['status'],'consistent_contact_evidence')
        self.assertIn('not unsaved consecutive persistence',result['scope'])

    def test_wrong_candidate_identity_or_candidate_contact_label_is_rejected(self):
        for label in ('other','not_in_inventory'):
            value=selection();value['observed']['contacts'][0]['label']=label
            result=validate_selection_contact_witness(value)
            self.assertEqual(result['status'],'inconsistent_contact_evidence')
            self.assertIn('requested_object_label',result['failed_checks'])

    def test_corrupt_force_count_arm_and_physics_order_are_rejected(self):
        for change in ('force','count','arm','step','snapshot','duplicate','root','environment','source_kind'):
            value=selection();row=value['observed']['contacts'][0]
            if change=='force':row['contact_source']['contacts'][0]['impulse']=[0,0,0]
            elif change=='count':row['contact_steps']=1
            elif change=='arm':value['definition']['arm']='left'
            elif change=='step':value['observed']['physics_step']=13
            elif change=='snapshot':value['snapshot_physics_step']=13
            elif change=='root':value['candidate_roots']['object']='/env/other'
            elif change=='environment':value['environment_index']=1
            elif change=='source_kind':row['contact_source']['kind']='object_contact_points'
            else:value['observed']['contacts'].append(deepcopy(row))
            with self.subTest(change=change):
                self.assertEqual(validate_selection_contact_witness(value)['status'],'inconsistent_contact_evidence')

    def test_absent_and_legacy_incomplete_evidence_remain_explicit(self):
        value=selection();value['observed']=None
        self.assertEqual(validate_selection_contact_witness(value)['status'],'unobserved_selection_contact')
        value=selection();value['observed']['contacts'][0].pop('contact_source')
        self.assertEqual(validate_selection_contact_witness(value)['status'],'partial_contact_evidence')

    def test_cached_geometry_does_not_override_corrupt_selected_force_in_scalar_report(self):
        value=selection();value['observed']['contacts'][0]['contact_source']['contacts'][0]['impulse']=[0,0,0]
        raw={'stage_id':'select','geometry':{},'selection':value}
        report={'native_results':[{'details':{'0':{'atomic_sequence':{'stages':[raw]}}}}]}
        stage={'episode':'0','stage_id':'select','family':'pick','conditions':{},'selection':{
            'status':'reproduced','target_status':'resolved','observed':value['observed'],
            'candidates':{'object':{'referent':{'status':'reproduced','recorded_result':{'components':{'position_m':.01}}}}}}}
        validate_cached_recognition(report,[stage])
        self.assertEqual(stage['selection']['status'],'invalid_selection_witness')
        self.assertEqual(stage['selection']['numerical_reproduction_status'],'reproduced')
        event=collect_events({'atomic_scores':[stage]})[('select','selection/referent')]
        self.assertEqual(event['score']['status'],'invalid_selection_witness')
        self.assertNotIn('recorded_result',event['score'])


if __name__=='__main__':unittest.main()
