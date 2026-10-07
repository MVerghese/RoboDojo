"""Source-core escape alone must not certify actual source-mouth passage."""
from copy import deepcopy
import math
import unittest
import numpy as np

from task.atomic.flow import SourceExitObserver, score_source_exit, validate_source_exit
from task.atomic.geometry import _rotation
from task.atomic.session import AtomicSession
from task.atomic.spec import AtomicStage, _validate_selector
from task.atomic.material_validation import initial_fluid_witness, validate_flow_witness
from scripts.atomic.validate_material_witnesses import validate_report_materials
from test_atomic_materials import pour_world, pour_stage
from test_atomic_material_witness import evidence
import test_atomic_physical_runtime as rigid_runtime

FRAME=[0,0,0,1,0,0,0]
C={'opening':{'kind':'calibrated_frame','label':'object',
             'local_pose':[0,0,.2,1,0,0,0],'calibration_id':'reviewed-mouth'},
   'aperture_profile':{'outer':[[-.02,-.02],[.02,-.02],[.02,.02],[-.02,.02]],
                       'holes':[[[-.003,-.003],[.003,-.003],[.003,.003],[-.003,.003]]]}}


class SourceMouthTests(unittest.TestCase):
    def test_real_aperture_holes_and_outward_direction_are_required(self):
        validate_source_exit(C,_validate_selector,'object')
        for x,passed in [(0,False),(.01,True),(.03,False)]:
            a={'position':[x,0,-.01],'opening':FRAME,'dt_s':.004}
            b={'position':[x,0,.01],'opening':FRAME,'dt_s':.004}
            self.assertEqual(score_source_exit(C,a,b)['passed'],passed)
            self.assertEqual(score_source_exit(C,b,a)['status'],'no_outward_crossing')
        with self.assertRaises(ValueError):validate_source_exit(C,_validate_selector,'another-source')

    def test_moving_mouth_and_sampling_limits_use_adjacent_persistent_ids(self):
        o=SourceExitObserver(C)
        o.observe({'7':[.01,0,-.01]},FRAME,{'7'},1,.004)
        moved=[.1,0,0,1,0,0,0]
        row=o.observe({'7':[.11,0,.01]},moved,{'7'},2,.004)['7']
        self.assertTrue(row['result']['passed'])
        np.testing.assert_allclose(row['result']['relative_velocity_m_s'],[0,0,5],atol=1e-12)
        self.assertEqual(o.observe({'7':[.11,0,-.01]},moved,{'7'},3,.004),{})
        self.assertEqual(o.reentries,{'7'})
        self.assertFalse(o.observe({'7':[.11,0,.01]},moved,{'7'},5,.004))
        self.assertEqual(o.summary()['failures'][0]['status'],'sampling_gap_or_dt_change')
        self.assertFalse(o.observe({'8':[.11,0,-.01]},moved,{'8'},6,.004))
        tilted=[.1,0,0,math.cos(.1),0,math.sin(.1),0]
        row=o.observe({'8':[.11,0,.01]},tilted,{'8'},7,.004)['8']
        self.assertEqual(row['result']['status'],'opening_rotation_sampling_limit')

    def world(self):
        w,data=pour_world();w.env.dt=.004
        c=deepcopy(pour_stage().recognition);c['source_exit']=deepcopy(C)
        c['source_exit']['aperture_profile'].pop('holes')
        stage=AtomicStage.from_dict({'id':'pour','family':'pour','instruction':'Pour',
            'success_checks':[{'name':'is_atomic_interaction','args':{}}],'recognition':c})
        s=AtomicSession(w.env,stage,0)
        w.hold();w.tick(s);w.tick(s)
        w.poses['object'][3:]=[math.cos(.25),0,math.sin(.25),0]
        w.tick(s)
        rotation=_rotation(w.poses['object'][3:])
        w.poses['target'][:3]=rotation@[0,0,.3]
        return w,data,s,rotation

    def test_core_escape_waits_for_held_tilted_actual_mouth_crossing(self):
        w,data,s,r=self.world()
        data['positions_local'][0]=r@[0,0,.15]
        w.tick(s);w.tick(s)
        self.assertFalse(s.summary()['physical_events'])
        data['positions_local'][0]=r@[0,0,.21]
        w.tick(s)
        self.assertTrue(w.tick(s))
        p=s.summary()['interaction_evidence']['particles'][7]
        self.assertTrue(p['source_mouth_crossing']['result']['passed'])
        self.assertEqual(p['exit_physics_step'],p['source_mouth_crossing']['after']['physics_step'])

    def test_side_escape_unheld_crossing_and_gap_cannot_be_borrowed_later(self):
        for invalid in ('side','unheld','gap'):
            with self.subTest(invalid=invalid):
                w,data,s,r=self.world()
                data['positions_local'][0]=r@[0,0,.15];w.tick(s)
                if invalid=='unheld':w.release()
                if invalid=='gap':w.contacts.steps+=2
                data['positions_local'][0]=r@([.05,0,.21] if invalid=='side' else [0,0,.21])
                w.tick(s);w.hold();w.tick(s);w.tick(s)
                self.assertFalse(s.summary()['physical_events'])

    def test_rigid_center_mouth_crossing_keeps_whole_mesh_target_containment(self):
        w=rigid_runtime.PhysicalTests().material_world();w.env.dt=.004
        lm=w.env.scene_manager.layout_manager
        lm.get_instance_name=lambda env_idx,label:label
        lm.instance_type_by_env=[{label:'rigid' for label in w.poses}]
        w.env._atomic_surfaces.center_pose=lambda label,env_idx,pose:pose.copy()
        original=rigid_runtime.stage('rigid_material_transfer')
        c=deepcopy(original.recognition);c['source_exit']=deepcopy(C)
        c['source_exit']['aperture_profile'].pop('holes')
        s=AtomicSession(w.env,AtomicStage.from_dict({'id':'pour','family':'pour','instruction':'Pour',
            'success_checks':list(original.success_checks),'recognition':c}),0)
        w.hold();w.tick(s,2)
        w.poses['object'][3:]=[math.cos(.25),0,math.sin(.25),0];w.tick(s)
        r=_rotation(w.poses['object'][3:]);w.poses['target'][:3]=r@[0,0,.3]
        w.poses['other'][:3]=r@[0,0,.15];w.tick(s,2)
        self.assertFalse(s.summary()['physical_events'])
        w.poses['other'][:3]=r@[0,0,.21];w.tick(s)
        w.poses['other'][:3]=w.poses['target'][:3];w.tick(s)
        self.assertTrue(w.tick(s))
        self.assertTrue(s.summary()['interaction_evidence']['materials']['other']['source_mouth_crossing']['result']['passed'])

    def test_source_reentry_clears_exit_and_cannot_borrow_later_hold(self):
        w,data,s,r=self.world();w.poses['target'][0]=2
        for z in (.15,.21):data['positions_local'][0]=r@[0,0,z];w.tick(s)
        self.assertTrue(s._physical_recognizer.fluid[7]['exited_while_held_and_tilted'])
        data['positions_local'][0]=r@[0,0,.19];w.tick(s)
        self.assertFalse(s._physical_recognizer.fluid[7]['exited_while_held_and_tilted'])
        w.release();data['positions_local'][0]=r@[0,0,.21];w.tick(s)
        w.hold();w.tick(s,3)
        self.assertFalse(s._physical_recognizer.fluid[7]['exited_while_held_and_tilted'])

    def test_probe_diagnostics_never_promote_unmapped_callbacks_to_force_grasp(self):
        for headers in (0,10):
            detail={'layout_id':0,'success':False,'contact_instrumentation':{'cloth_contact_probe':{
                'counts':{'headers':headers,'finger_force_points':headers},'native_samples':[]}}}
            result=validate_report_materials({'native_results':[{'details':{'0':detail}}]})
            probe=result['episodes'][0]['cloth_probe']
            self.assertFalse(probe['force_grasp_supported'])
            self.assertEqual(probe['status'],'no_native_cloth_callbacks_observed' if not headers
                             else 'native_callbacks_without_verified_material_correspondence')

    def test_raw_audit_rejects_fabricated_mouth_witness_or_future_exit(self):
        c,i,row=evidence();c['source_exit']=deepcopy(C)
        p=row['source_exit_provenance']
        r=_rotation(p['exit_source_frame'][3:]);mouth=list(r@[0,0,.2])+p['exit_source_frame'][3:]
        p['exit_position']=(r@[.01,0,.21]).tolist()
        m={'before':{'position':(r@[.01,0,.19]).tolist(),'opening':mouth,'dt_s':.004,'physics_step':4},
           'after':{'position':p['exit_position'],'opening':mouth,'dt_s':.004,'physics_step':5,
                    'opening_source':{'root_pose':p['exit_source_frame']}}}
        m['result']=score_source_exit(C,m['before'],m['after']);p['source_mouth_crossing']=m
        self.assertEqual(validate_flow_witness('7',row,c,initial_fluid_witness(c,i))['status'],'consistent_source_evidence')
        m['after']['opening'][0]+=.001
        self.assertIn('source_mouth_frame_position_binding',validate_flow_witness('7',row,c)['failed_checks'])
        m['after']['opening'][0]-=.001
        m['result']['substep_fraction']=.25
        self.assertIn('source_mouth_numerical_witness',validate_flow_witness('7',row,c)['failed_checks'])
        m['after']['physics_step']=6
        self.assertIn('source_mouth_adjacent_samples',validate_flow_witness('7',row,c)['failed_checks'])


if __name__=='__main__':unittest.main()
