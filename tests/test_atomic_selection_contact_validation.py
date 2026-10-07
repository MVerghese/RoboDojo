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
