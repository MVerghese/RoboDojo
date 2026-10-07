"""Flow arithmetic alone cannot certify source identity, hold or event ordering."""
from copy import deepcopy
import math
import unittest
import numpy as np
from task.atomic.material_validation import initial_fluid_witness,validate_flow_witness
from scripts.atomic.audit_scores import audit_flow,apply_flow_validation
from task.atomic.flow import score_crossing
from task.atomic.session import AtomicSession
from test_atomic_materials import pour_world,pour_stage


def evidence():
    config=dict(pour_stage().recognition)
    initial={'ids':[7,11],'positions':[[0,0,0],[.5,0,0]],
        'region_frames':{'source':[0,0,0,1,0,0,0],'target':[.5,0,0,1,0,0,0]},
        'initial_in_source':[True,False],'initial_in_target':[False,True]}
    hold={'label':'object','resolved_arm':'left_arm','physics_step':5,
        'contact_interval_start_step':3,'consecutive_contact_steps':3,
        'finger_bodies':['f0','f1'],'contacts':[
            {'finger_body':f,'arm':'left_arm','force_report_physics_step':5,'impulse':[0,0,.001]}
            for f in ('f0','f1')]}
    row={'before':{'physics_step':6,'dt_s':.004,'position':[.5,0,.01],'opening':[.5,0,0,1,0,0,0]},
         'after':{'physics_step':7,'dt_s':.004,'position':[.5,0,-.01],'opening':[.5,0,0,1,0,0,0]},
         'source_exit_provenance':{'eligible':True,'exited_while_held_and_tilted':True,
             'exit_physics_step':5,'exit_tilt_rad':.5,'exit_contact':hold,
             'exit_position':[.5,0,0],
             'initial_source_frame':[0,0,0,1,0,0,0],
             'exit_source_frame':[0,0,0,math.cos(.25),0,math.sin(.25),0]}}
    return config,initial,row


class MaterialWitnessTests(unittest.TestCase):
    def test_initial_cohort_recomputes_actual_source_only_membership(self):
        c,i,r=evidence();cohort=initial_fluid_witness(c,i)
        self.assertEqual(cohort['eligible_ids'],{7})
        self.assertEqual(validate_flow_witness('7',r,c,cohort)['status'],'consistent_source_evidence')
        witness=validate_flow_witness('11',r,c,cohort)
        self.assertIn('initial_source_only',witness['failed_checks'])
        i['initial_in_target'][1]=False
        self.assertFalse(initial_fluid_witness(c,i)['checks']['target_initial_mask'])

    def test_future_exit_sampling_gap_wrong_source_and_nonforce_grip_fail(self):
        c,i,r=evidence();cohort=initial_fluid_witness(c,i)
        variants=[]
        x=deepcopy(r);x['source_exit_provenance']['exit_physics_step']=8;variants.append((x,'exit_precedes_sampled_crossing'))
        x=deepcopy(r);x['after']['physics_step']=8;variants.append((x,'adjacent_samples'))
        x=deepcopy(r);x['source_exit_provenance']['exit_contact']['label']='other';variants.append((x,'held_source_identity'))
        x=deepcopy(r);x['source_exit_provenance']['exit_contact']['contacts'][1]['impulse']=[0,0,0];variants.append((x,'synchronized_force_contacts'))
        x=deepcopy(r);x['source_exit_provenance']['exit_tilt_rad']=.1;variants.append((x,'exit_tilt_threshold'))
        x=deepcopy(r);x['source_exit_provenance']['exit_source_frame'][3:]=[1,0,0,0];variants.append((x,'tilt_from_raw_frames'))
        for row,name in variants:
            with self.subTest(name=name):
                witness=validate_flow_witness('7',row,c,cohort)
                self.assertEqual(witness['status'],'inconsistent_evidence');self.assertIn(name,witness['failed_checks'])

    def test_historical_missing_witnesses_are_partial_and_invalid_new_witnesses_exclude_scores(self):
        c,i,row=evidence()
        flow={'opening':{'kind':'object_pose','label':'target'},'aperture_profile':{'outer':[[-.02,-.02],[.02,-.02],[.02,.02],[-.02,.02]]},
              'target_xy_m':[0,0],'position_tolerance_m':.005,'angle_tolerance_rad':.2}
        row['result']=score_crossing(flow,row['before'],row['after'])
        raw={'recognition':c,'material_transfer_initial_state':i,
             'material_flow':{'condition':flow,'crossings':{'7':row},'failures':[]}}
        audited={'material_flow':audit_flow(raw['material_flow'])}
        apply_flow_validation(raw,audited)
        self.assertEqual(audited['material_flow']['crossings']['7']['source_witness']['status'],'consistent_source_evidence')
        del i['region_frames'];del row['source_exit_provenance']['exit_contact']
        apply_flow_validation(raw,audited)
        self.assertEqual(audited['material_flow']['crossings']['7']['status'],'reproduced')
        self.assertEqual(audited['material_flow']['witness_summary'],{'partial_evidence':1})
        row['source_exit_provenance']['exit_physics_step']=999
        apply_flow_validation(raw,audited)
        score=audited['material_flow']['crossings']['7']
        self.assertEqual(score['status'],'invalid_source_witness')
        self.assertEqual(score['numerical_reproduction_status'],'reproduced')
        self.assertTrue(score['recorded_result']['passed'])

    def test_actual_runtime_retains_each_particle_exit_contact_and_initial_region_frames(self):
        w,data=pour_world();s=AtomicSession(w.env,pour_stage(),0)
        initial=s.summary()['material_transfer_initial_state']
        self.assertEqual(initial['initial_in_source'],[True,True,False])
        self.assertEqual(initial['initial_in_target'],[False,False,True])
        w.hold();w.tick(s);w.tick(s)
        w.poses['object'][3:]=[math.cos(.25),0,math.sin(.25),0]
        data['positions_local'][0]=[.5,0,0];w.tick(s);w.tick(s)
        p=s.summary()['interaction_evidence']['particles'][7]
        self.assertEqual(p['exit_contact']['physics_step'],p['exit_physics_step'])
        self.assertEqual(p['exit_contact']['resolved_arm'],'left')
        self.assertEqual(p['initial_source_frame'],initial['region_frames']['source'])
        self.assertAlmostEqual(p['exit_tilt_rad'],.5)
