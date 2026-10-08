"""Rejected source crossings retain geometry and the exact physical gate snapshot."""
from copy import deepcopy
import math
from types import SimpleNamespace
import unittest
import numpy as np
from task.atomic.flow import SourceExitObserver,score_source_exit
from task.atomic.geometry import _rotation
from task.atomic.session import AtomicSession
from task.atomic.spec import AtomicStage
from task.atomic.source_candidates import audit_source_candidates,validate_candidate
from test_atomic_finite_material import bound,mesh
from test_atomic_source_mouth import C,FRAME
import test_atomic_source_mouth as mouth_runtime
from test_atomic_contact_validation import sample
import test_atomic_physical_runtime as runtime


def candidate():
    c=deepcopy(runtime.recognition('rigid_material_transfer'));c['source_exit']=deepcopy(C)
    c['source_exit']['aperture_profile'].pop('holes');c['source_exit']['finite_material_bound']=True
    pose=np.array([0,0,0,math.cos(.25),0,math.sin(.25),0]);r=_rotation(pose[3:])
    opening=pose.copy();opening[:3]=r@[0,0,.2]
    a={'position':(r@[.01,0,.19]).tolist(),'opening':opening.tolist(),'physics_step':11,'dt_s':.004}
    b={'position':(r@[.01,0,.21]).tolist(),'opening':opening.tolist(),'physics_step':12,'dt_s':.004,
        'material_bound':bound(),'material_pose':[*list(r@[.01,0,.21]),*pose[3:]],
        'opening_source':{'root_pose':pose.tolist()}}
    _,_,hold=sample();hold.update(consecutive_contact_steps=3,contact_interval_start_step=10)
    row={'material_id':'other','before':a,'after':b,'result':score_source_exit(c['source_exit'],a,b),
        'qualification':{'context':'source_exit_candidate_qualification','initial_cohort_eligible':True,
            'inside_source':False,'reentered_source':False,'already_qualified_before':False,
            'held_contact':hold,'tilt_rad':.5,'source_frame':pose.tolist(),'initial_source_frame':FRAME,
            'eligible_for_source_exit':True}}
    return c,row


class SourceCandidateTests(unittest.TestCase):
    def test_reproduces_named_force_tilt_mesh_center_and_qualification_then_rejects_corruption(self):
        c,row=candidate();bounds={'other':deepcopy(row['after']['material_bound'])}
        result=validate_candidate(row,c,bounds);self.assertEqual(result['status'],'consistent_evidence',result)
        changes=[lambda r:r['qualification'].__setitem__('eligible_for_source_exit',False),
            lambda r:r['qualification'].__setitem__('tilt_rad',.6),
            lambda r:r['qualification'].__setitem__('inside_source',True),
            lambda r:r['after'].__setitem__('physics_step',13),
            lambda r:r['after']['material_pose'].__setitem__(0,1),
            lambda r:r['qualification']['held_contact']['contacts'][0].__setitem__('impulse',[0,0,0]),
            lambda r:r.__setitem__('material_id','wrong'),
            lambda r:r['after']['opening_source']['root_pose'].__setitem__(0,1)]
        for mutate in changes:
            broken=deepcopy(row);mutate(broken)
            self.assertEqual(validate_candidate(broken,c,bounds)['status'],'inconsistent_evidence')

    def test_unheld_geometric_pass_is_retained_without_inventing_qualified_exit(self):
        c,row=candidate();row['qualification']['held_contact']=None;row['qualification']['eligible_for_source_exit']=False
        result=validate_candidate(row,c,{'other':row['after']['material_bound']})
        self.assertEqual(result['status'],'consistent_evidence');self.assertTrue(result['result']['passed'])
        self.assertFalse(result['qualification']['eligible_for_source_exit'])
        c,row=candidate();c['min_tilt_rad']=.7;row['qualification']['eligible_for_source_exit']=False
        self.assertEqual(validate_candidate(row,c,{'other':row['after']['material_bound']})['status'],'consistent_evidence')

    def test_runtime_retains_exact_unheld_and_held_crossing_states_without_changing_recognition(self):
        w=runtime.PhysicalTests().material_world();w.env.dt=.004;v,t=mesh()
        lm=w.env.scene_manager.layout_manager;lm.get_instance_name=lambda env_idx,label:label
        lm.instance_type_by_env=[{label:'rigid' for label in w.poses}]
        lm.get_scene_object=lambda env_idx,inst_name:SimpleNamespace(_prim_path='/World/envs/env_0/rigid/'+inst_name)
        w.env._atomic_surfaces.resolve=lambda label,env_idx,pose:{'vertices':(v@_rotation(pose[3:]).T+pose[:3]).tolist(),
            'triangles':t.tolist(),'prim_path':'/World/envs/env_0/rigid/'+label,'selected_mesh_paths':None}
        w.env._atomic_surfaces.center_pose=lambda label,env_idx,pose:pose.copy()
        c,_=candidate();s=AtomicSession(w.env,AtomicStage.from_dict({'id':'pour','family':'pour','instruction':'Pour',
            'success_checks':[{'name':'is_atomic_interaction','args':{}}],'recognition':c}),0)
        w.poses['object'][3:]=[math.cos(.25),0,math.sin(.25),0];r=_rotation(w.poses['object'][3:])
        for z in [.15,.21]:w.poses['other'][:3]=r@[0,0,z];w.tick(s)
        first=s.summary()['physical_metrics']['source_mouth_sampling']['candidate_witnesses'][0]
        self.assertTrue(first['result']['passed']);self.assertIsNone(first['qualification']['held_contact'])
        self.assertFalse(first['qualification']['eligible_for_source_exit']);self.assertNotIn('source_exit',s.summary()['physical_events'])
        w.poses['other'][:3]=r@[0,0,.15];w.hold();w.tick(s,2)
        w.poses['other'][:3]=r@[0,0,.21];w.tick(s)
        second=s.summary()['physical_metrics']['source_mouth_sampling']['candidate_witnesses'][1]
        self.assertTrue(second['qualification']['eligible_for_source_exit']);self.assertIn('source_exit',s.summary()['physical_events'])
        self.assertIsNotNone(second['after']['material_pose'])
        self.assertEqual(audit_source_candidates(s.summary())['status'],'partial_evidence') # Fake force source has no actor bindings.

    def test_bounded_history_keeps_first_crossings_and_full_counts_without_duplicate_steps(self):
        o=SourceExitObserver(C);points={str(i):[.01,0,-.01] for i in range(40)}
        o.observe(points,FRAME,set(points),1,.004);points={i:[.01,0,.01] for i in points}
        o.observe(points,FRAME,set(points),2,.004);saved=o.summary()
        self.assertEqual(saved['candidate_crossings'],40);self.assertEqual(len(saved['candidate_witnesses']),32)
        self.assertTrue(saved['candidate_history_truncated']);self.assertEqual(saved['candidate_outcomes'],{'inside_aperture':40})
        o.observe(points,FRAME,set(points),2,.004);self.assertEqual(o.summary(),saved)
        saved['candidate_witnesses'][0]['before']['position'][0]=99
        self.assertEqual(o.summary()['candidate_witnesses'][0]['before']['position'][0],.01)

    def test_fluid_cohort_source_core_and_legacy_missing_history_are_separate(self):
        w,data,s,r=mouth_runtime.SourceMouthTests().world()
        for z in [.15,.21]:data['positions_local'][0]=r@[0,0,z];w.tick(s)
        raw=s.summary();out=audit_source_candidates(raw)
        self.assertEqual(out['status'],'partial_evidence',out) # Host fake contact metadata is partial.
        self.assertTrue(out['candidates'][0]['checks']['source_containment_from_geometry'])
        self.assertTrue(out['candidates'][0]['checks']['initial_particle_cohort'])
        legacy=deepcopy(raw);legacy['physical_metrics']['source_mouth_sampling'].pop('candidate_witnesses')
        old=audit_source_candidates(legacy);self.assertEqual(old['status'],'partial_evidence')
        self.assertEqual(old['candidate_crossings'],1);self.assertNotIn('candidates',old)
        broken=deepcopy(raw);broken['material_transfer_initial_state']['initial_in_source'][0]=False
        self.assertEqual(audit_source_candidates(broken)['status'],'inconsistent_evidence')


if __name__=='__main__':unittest.main()
