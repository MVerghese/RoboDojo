"""Physical source contradictions cannot leave a transfer-event geometry score valid."""
from copy import deepcopy
import unittest
import numpy as np
import test_atomic_source_candidates as candidates
import test_atomic_source_mouth as mouth
import test_atomic_physical_runtime as runtime
from task.atomic.session import AtomicSession
from task.atomic.spec import AtomicStage
from task.atomic.material_boundaries import validate_material_event
from scripts.atomic.audit_scores import apply_recognition_validation


def fixture():
    config,row=candidates.candidate();q=row['qualification'];pose=row['after']['material_pose']
    p={'eligible':True,'initial_in_source':True,'initial_in_target':False,'exited_while_held_and_tilted':True,
        'exit_physics_step':12,'exit_tilt_rad':q['tilt_rad'],'exit_contact':q['held_contact'],
        'exit_source_frame':q['source_frame'],'initial_source_frame':q['initial_source_frame'],
        'source_mouth_crossing':{k:row[k] for k in ('before','after','result')}}
    event={'name':'first_transfer','physics_step':13,'material_label':'other','source_exit':p,
        'environment_index':0,'material_pose':deepcopy(pose),
        'current_region_frames':{'source':deepcopy(q['source_frame']),'target':deepcopy(pose)},
        'current_region_sources':{'source':{'label':'object','root_pose':deepcopy(q['source_frame']),'physics_step':13},
            'target':{'label':'target','root_pose':deepcopy(pose),'physics_step':13}}}
    return {'family':'pour','recognition':config,'stage_id':'pour','action_success':True,
        'material_bounds':{'other':row['after']['material_bound']},'physical_events':{'first_transfer':event},
        'physical_metrics':{'source_mouth_sampling':{'candidate_witnesses':[deepcopy(row)]}}}


class MaterialBoundaryTests(unittest.TestCase):
    def test_actual_source_window_and_current_core_are_checked_without_destination_crossing(self):
        stage=fixture();out=validate_material_event(stage,'first_transfer')
        self.assertEqual(out['status'],'consistent_evidence',out)
        self.assertTrue(out['checks']['material_current_target_containment'])
        self.assertNotIn('material_flow',stage)
        for edit in [lambda s:s['physical_events']['first_transfer']['source_exit']['exit_contact']['contacts'][0].__setitem__('impulse',[0,0,0]),
            lambda s:s['physical_events']['first_transfer'].__setitem__('physics_step',11),
            lambda s:s['physical_events']['first_transfer']['current_region_frames']['target'].__setitem__(0,5),
            lambda s:s['physical_events']['first_transfer']['material_pose'].__setitem__(0,5),
            lambda s:s['physical_events']['first_transfer']['current_region_sources']['source'].__setitem__('label','wrong')]:
            broken=deepcopy(stage);edit(broken)
            self.assertEqual(validate_material_event(broken,'first_transfer')['status'],'inconsistent_evidence')
            self.assertTrue(broken['action_success'])

    def test_missing_historical_core_is_partial_and_missing_event_is_unobserved(self):
        stage=fixture();event=stage['physical_events']['first_transfer'];event.pop('current_region_frames')
        self.assertEqual(validate_material_event(stage,'first_transfer')['status'],'partial_evidence')
        self.assertEqual(validate_material_event(stage,'source_exit')['status'],'unobserved')
        stage['physical_events']['source_exit']={'physics_step':12,'material_label':'other'}
        self.assertEqual(validate_material_event(stage,'source_exit')['status'],'consistent_evidence')
        stage['physical_events']['source_exit']['material_label']='wrong'
        self.assertEqual(validate_material_event(stage,'source_exit')['status'],'inconsistent_evidence')

    def test_bad_source_or_measurement_clock_excludes_condition_preserving_numerical_value(self):
        stage=fixture();stage['conditions']=[{'id':'spout','event':{'kind':'recognition_event','name':'first_transfer'}}]
        stage['geometry']={'spout':{'event':stage['conditions'][0]['event'],'measurement_physics_step':13,
            'event_evidence':deepcopy(stage['physical_events']['first_transfer'])}}
        for change in ('source_force','measurement_clock','event_copy'):
            broken=deepcopy(stage)
            if change=='source_force':broken['physical_events']['first_transfer']['source_exit']['exit_contact']['contacts'][0]['impulse']=[0,0,0]
            elif change=='measurement_clock':broken['geometry']['spout']['measurement_physics_step']=12
            else:broken['geometry']['spout']['event_evidence']['material_label']='wrong'
            score={'conditions':{'spout':{'status':'reproduced','recorded_result':{'error':.003}}},'trajectories':{}}
            apply_recognition_validation(broken,score)
            self.assertEqual(score['conditions']['spout']['status'],'invalid_recognition_window')
            self.assertEqual(score['conditions']['spout']['recorded_result']['error'],.003)
            self.assertTrue(broken['action_success'])

    def test_runtime_retains_same_step_source_provenance_and_both_current_core_frames(self):
        w,data=mouth.pour_world();config=dict(mouth.pour_stage().recognition)
        stage=AtomicStage.from_dict({'id':'pour','family':'pour','instruction':'Pour',
            'success_checks':[{'name':'is_atomic_interaction','args':{}}],'recognition':config})
        session=AtomicSession(w.env,stage,0);w.hold();w.tick(session,2)
        w.poses['object'][3:]=[np.cos(.25),0,np.sin(.25),0]
        data['positions_local'][0]=[.5,0,0];w.tick(session)
        raw=session.summary();events=raw['physical_events']
        self.assertEqual(events['source_exit']['source_exit_provenance']['exit_physics_step'],events['source_exit']['physics_step'])
        event=events['first_transfer']
        self.assertEqual(event['current_region_sources']['target']['physics_step'],event['physics_step'])
        self.assertEqual(event['current_region_sources']['source']['physics_step'],event['physics_step'])
        self.assertEqual(event['current_region_frames']['target'],w.poses['target'].tolist())
