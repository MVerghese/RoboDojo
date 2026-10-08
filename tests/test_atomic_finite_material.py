"""A center crossing must not certify finite material over an edge or hole."""
from copy import deepcopy
import math
from types import SimpleNamespace
import unittest
import numpy as np

from task.atomic.finite_material import capture_material_bound,validate_material_bound
from task.atomic.flow import score_source_exit,score_crossing,FlowObserver,SourceExitObserver
from task.atomic.geometry import _rotation
from task.atomic.session import AtomicSession
from task.atomic.spec import AtomicStage
from task.atomic.material_validation import validate_flow_witness
from scripts.atomic.audit_scores import audit_flow,apply_flow_validation
from test_atomic_source_mouth import C,FRAME
from test_atomic_material_witness import evidence
import test_atomic_physical_runtime as runtime


def mesh(radius=.006):
    v=np.array([[radius,0,0],[-radius,0,0],[0,radius,0],[0,-radius,0],[0,0,radius],[0,0,-radius]])
    t=[]
    for x in (0,1):
        for y in (2,3):
            for z in (4,5):
                face=[x,y,z];a,b,c=v[face]
                if np.cross(b-a,c-a)@a<0:face.reverse()
                t.append(face)
    return v,np.array(t)


def bound(radius=.006):
    v,t=mesh(radius)
    return {'status':'observed_finite_rigid_bound','label':'other','environment_index':0,'physics_step':0,
        'frame':'scaled_object_root_local','length_unit':'metres','object_root':'/World/envs/env_0/rigid/other',
        'local_vertices_m':v.tolist(),'triangles':t.tolist(),'local_center_m':[0,0,0],'enclosing_radius_m':radius,
        'closed_oriented_mesh':True,
        'source':'ObjectSurfaces.resolve whole scaled root-relative USD mesh triangles; no solid-volume inference'}


def samples(x):
    return ({'position':[x,0,-.01],'opening':FRAME,'dt_s':.004},
            {'position':[x,0,.01],'opening':FRAME,'dt_s':.004,'material_bound':bound()})


class FiniteMaterialTests(unittest.TestCase):
    def test_center_inside_outer_boundary_can_still_fail_finite_mesh_fit(self):
        c=deepcopy(C);c['aperture_profile'].pop('holes');a,b=samples(.018)
        self.assertTrue(score_source_exit(c,a,b)['passed'])
        c['finite_material_bound']=True;r=score_source_exit(c,a,b)
        self.assertFalse(r['passed']);self.assertAlmostEqual(r['finite_bound_clearance_m'],-.004)
        self.assertAlmostEqual(r['finite_bound_shortfall_m'],.004)
        a,b=samples(.01);self.assertTrue(score_source_exit(c,a,b)['passed'])
        self.assertAlmostEqual(score_source_exit(c,a,b)['finite_bound_clearance_m'],.004)

    def test_enclosing_disk_must_avoid_aperture_holes(self):
        a,b=samples(.007)
        self.assertTrue(score_source_exit(C,a,b)['passed'])
        result=score_source_exit(dict(C,finite_material_bound=True),a,b)
        self.assertFalse(result['passed']);self.assertAlmostEqual(result['finite_bound_shortfall_m'],.002)

    def test_missing_forged_or_open_mesh_bounds_never_fall_back_to_center_success(self):
        c=dict(C,finite_material_bound=True);a,b=samples(.01)
        for mutate in (lambda b:b.pop('material_bound'),lambda b:b['material_bound'].__setitem__('enclosing_radius_m',.0001),
                lambda b:b['material_bound']['triangles'].pop(),lambda b:b['material_bound'].__setitem__('length_unit','mm')):
            row=deepcopy(b);mutate(row);r=score_source_exit(c,a,row)
            self.assertEqual(r['status'],'finite_material_bound_unavailable');self.assertIsNone(r['passed'])
        # Open actual triangles can still be enclosed, with closure explicitly false.
        row=deepcopy(b);row['material_bound']['triangles'].pop();row['material_bound']['closed_oriented_mesh']=False
        self.assertTrue(score_source_exit(c,a,row)['passed'])
        from scripts.atomic.audit_scores import audit_material_bounds
        self.assertEqual(audit_material_bounds({'other':row['material_bound']})['other']['status'],'consistent_evidence')
        self.assertEqual(audit_material_bounds({'wrong':row['material_bound']})['wrong']['status'],'inconsistent_evidence')

    def test_target_flow_keeps_clearance_scalar_and_actual_sampled_bound(self):
        c={'opening':{'kind':'object_pose','label':'target'},'aperture_profile':deepcopy(C['aperture_profile']),
           'target_xy_m':[.007,0],'position_tolerance_m':.01,'angle_tolerance_rad':.2,'finite_material_bound':True}
        a,b=samples(.007);a,b=b,a;b['material_bound']=bound()
        r=score_crossing(c,a,b);self.assertFalse(r['passed'])
        self.assertAlmostEqual(r['components']['finite_bound_shortfall_m'],.002)
        o=FlowObserver(c);provenance={'other':{'eligible':True,'exited_while_held_and_tilted':True}}
        o.observe({'other':[.007,0,.01]},FRAME,provenance,1,.004,material_bounds={'other':bound()})
        o.observe({'other':[.007,0,-.01]},FRAME,provenance,2,.004,material_bounds={'other':bound()})
        self.assertEqual(o.crossings['other']['after']['material_bound']['label'],'other')
        self.assertFalse(o.crossings['other']['result']['passed'])
        from scripts.atomic.continuous_report import component_names,component_unit
        names=component_names({'kind':'stream_crossing','definitions':[{'condition':c}],
            'baseline':{'components':{}},'conditioned':{'components':{}}})
        self.assertIn('finite_bound_clearance_m',names)
        self.assertEqual(component_unit('finite_bound_clearance_m')[1],1000)

    def test_grazing_inward_center_invalidates_an_earlier_exit(self):
        c=deepcopy(C);c['aperture_profile'].pop('holes');c['finite_material_bound']=True
        o=SourceExitObserver(c)
        o.observe({'other':[.018,0,.01]},FRAME,{'other'},1,.004,material_bounds={'other':bound()})
        o.observe({'other':[.018,0,-.01]},FRAME,{'other'},2,.004,material_bounds={'other':bound()})
        self.assertEqual(o.reentries,{'other'})
        r=o.observe({'other':[.018,0,.01]},FRAME,{'other'},3,.004,material_bounds={'other':bound()})['other']
        self.assertFalse(r['result']['passed'])

    def test_fluid_schema_cannot_invent_a_finite_particle_radius(self):
        from test_atomic_materials import pour_stage
        original=pour_stage();c=deepcopy(original.recognition);c['source_exit']=dict(C,finite_material_bound=True)
        with self.assertRaisesRegex(ValueError,'fluid radius is not inferred'):
            AtomicStage.from_dict({'id':'pour','family':'pour','instruction':'Pour',
                'success_checks':list(original.success_checks),'recognition':c})

    def test_actual_rigid_runtime_captures_immutable_bound_and_qualifies_finite_exit(self):
        w=runtime.PhysicalTests().material_world();w.env.dt=.004;v,t=mesh()
        lm=w.env.scene_manager.layout_manager;lm.get_instance_name=lambda env_idx,label:label
        lm.instance_type_by_env=[{label:'rigid' for label in w.poses}]
        lm.get_scene_object=lambda env_idx,inst_name:SimpleNamespace(_prim_path='/World/envs/env_0/rigid/'+inst_name)
        w.env._atomic_surfaces.resolve=lambda label,env_idx,pose:{'vertices':(v@_rotation(pose[3:]).T+pose[:3]).tolist(),
            'triangles':t.tolist(),'prim_path':'/World/envs/env_0/rigid/'+label,'selected_mesh_paths':None}
        w.env._atomic_surfaces.center_pose=lambda label,env_idx,pose:pose.copy()
        original=runtime.stage('rigid_material_transfer');c=deepcopy(original.recognition)
        c['source_exit']=deepcopy(C);c['source_exit']['aperture_profile'].pop('holes');c['source_exit']['finite_material_bound']=True
        s=AtomicSession(w.env,AtomicStage.from_dict({'id':'pour','family':'pour','instruction':'Pour',
            'success_checks':list(original.success_checks),'recognition':c}),0)
        initial=deepcopy(s.summary()['material_bounds']['other']);self.assertAlmostEqual(validate_material_bound(initial),.006)
        w.hold();w.tick(s,2);w.poses['object'][3:]=[math.cos(.25),0,math.sin(.25),0];w.tick(s)
        r=_rotation(w.poses['object'][3:]);w.poses['target'][:3]=r@[0,0,.3]
        w.poses['other'][:3]=r@[0,0,.15];w.tick(s,2)
        w.poses['other'][:3]=r@[0,0,.21];w.tick(s)
        source=s._physical_recognizer.material['other']['source_mouth_crossing']
        self.assertTrue(source['result']['passed']);self.assertEqual(source['after']['material_bound'],initial)
        w.poses['other'][:3]=w.poses['target'][:3];w.tick(s,2)
        self.assertTrue(s.summary()['action_success']);self.assertEqual(s.summary()['material_bounds']['other'],initial)

    def test_wrong_material_or_changed_capture_excludes_numerically_reproduced_flow(self):
        c,_,row=evidence();c['kind']='rigid_material_transfer'
        c['flow']={'opening':{'kind':'object_pose','label':'target'},'aperture_profile':{'outer':[[-.02,-.02],[.02,-.02],[.02,.02],[-.02,.02]]},
            'target_xy_m':[0,0],'position_tolerance_m':.005,'angle_tolerance_rad':.2,'finite_material_bound':True}
        p=row['source_exit_provenance'];p.update(initial_in_source=True,initial_in_target=False)
        p['exit_contact']['environment_index']=0
        row['after']['material_bound']=bound();row['result']=score_crossing(c['flow'],row['before'],row['after'])
        self.assertEqual(validate_flow_witness('other',row,c,material_bounds={'other':bound()})['status'],'consistent_source_evidence')
        self.assertIn('target_finite_material_identity',validate_flow_witness('wrong',row,c,material_bounds={'wrong':bound()})['failed_checks'])
        row['after']['material_bound']=bound(.005);row['result']=score_crossing(c['flow'],row['before'],row['after'])
        atomic={'recognition':c,'material_bounds':{'other':bound()},
            'material_flow':{'condition':c['flow'],'crossings':{'other':row},'failures':[]}}
        output={'material_flow':audit_flow(atomic['material_flow'])};apply_flow_validation(atomic,output)
        self.assertEqual(output['material_flow']['crossings']['other']['status'],'invalid_source_witness')


if __name__=='__main__':unittest.main()
