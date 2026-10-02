"""Frame, identity, deforming-patch and liquid provenance counterexamples."""
from copy import deepcopy
from types import SimpleNamespace as NS
import math
import unittest

import numpy as np
from test_atomic_physical_runtime import World
from task.atomic.materials import material_state,resolve_material
from task.atomic.geometry import evaluate_geometry,_rotation
from task.atomic.session import AtomicSession
from task.atomic.spec import AtomicStage,_validate_selector


def attach_material(w,kind,ids,points):
    data={'ids':np.array(ids,dtype=np.int64),'backend':'test live state','identity':'persistent test ids'}
    if kind=='fluid':
        data.update(positions_local=np.asarray(points,dtype=float),local_to_world_row_matrix=np.eye(4),nominal_particle_mass_kg=.0005)
        obj=NS(get_atomic_particle_state=lambda:deepcopy(data)); label='water';category='fluid'
    else:
        data.update(positions_world=np.asarray(points,dtype=float))
        obj=NS(get_atomic_vertex_state=lambda:deepcopy(data));label='cloth';category='garment'
    lm=w.env.scene_manager.layout_manager
    lm.instance_type_by_env=[{'object':'rigid','target':'rigid',label:category}]
    lm.get_instance_name=lambda env_idx,label:label
    lm.get_scene_object=lambda env_idx,inst_name:obj if inst_name==label else None
    lm.get_instance_metadata=lambda **kw:{'passive':{'functional':{'sleeve':{'id':[5,8]}}}}
    w.env.sim=NS(scene=NS(env_origins=np.zeros((1,3))))
    return label,data


def pour_stage():
    return AtomicStage.from_dict({'id':'pour','family':'pour','instruction':'Pour the water',
        'success_checks':[{'name':'is_atomic_interaction','args':{}}],'recognition':{
            'kind':'fluid_material_transfer','label':'object','arm':'any','min_contact_steps':2,'target_label':'target',
            'fluid_label':'water','source_frame':{'kind':'object_pose','label':'object'},
            'target_frame':{'kind':'object_pose','label':'target'},'source_half_extents_m':[.1,.1,.1],
            'target_half_extents_m':[.1,.1,.1],'required_count':1,'min_tilt_rad':.3,'settle_steps':2}})


def pour_world():
    w=World();w.poses['target'][0]=.5
    _,data=attach_material(w,'fluid',[7,9,11],[[0,0,0],[.005,0,0],[.5,0,0]])
    return w,data


class MaterialTests(unittest.TestCase):
    def test_fluid_applies_current_scale_rotation_translation_and_origin_once(self):
        w=World();label,data=attach_material(w,'fluid',[15,3],[[1,0,0],[0,1,0]])
        data['local_to_world_row_matrix']=np.array([[0,2,0,0],[-3,0,0,0],[0,0,4,0],[10,20,30,1.]])
        w.env.sim.scene.env_origins[0]=[10,20,30]
        state=material_state(w.env,label,'fluid',0)
        np.testing.assert_allclose(state['positions'],[[0,2,0],[-3,0,0]])
        points,source=resolve_material(w.env,{'kind':'fluid_points','label':label,'ids':[3]},0)
        np.testing.assert_allclose(points['position'],[-3,0,0])
        self.assertEqual(source['selected_nominal_mass_kg'],.0005)
        self.assertIn('nominal',source['mass_semantics'])

    def test_material_point_scoring_uses_every_vertex_not_the_centroid(self):
        w=World();label,data=attach_material(w,'cloth',[5,8,11],[[-.02,0,0],[.02,0,0],[0,.01,0]])
        measured,_=resolve_material(w.env,{'kind':'cloth_landmark','label':label,'tag':'sleeve'},0)
        result=evaluate_geometry({'kind':'point','expected':[0,0,0],'tolerance':.005},measured)
        self.assertFalse(result.passed);self.assertAlmostEqual(result.error,.02)
        self.assertEqual(result.components['material_points'],2)
        self.assertNotIn('contact_points',result.components)

    def test_cloth_patch_frame_follows_live_material_deformation(self):
        w=World();label,data=attach_material(w,'cloth',[5,8,11],[[1,2,3],[2,2,3],[1,3,3]])
        selector={'kind':'cloth_patch_frame','label':label,'origin_id':5,'x_id':8,'y_id':11}
        _validate_selector(selector,'patch')
        pose,_=resolve_material(w.env,selector,0);np.testing.assert_allclose(_rotation(pose[3:]),np.eye(3))
        data['positions_world'][1]=[1,3,3];data['positions_world'][2]=[0,2,3]
        pose,_=resolve_material(w.env,selector,0)
        np.testing.assert_allclose(_rotation(pose[3:])@[1,0,0],[0,1,0],atol=1e-8)
        data['positions_world'][2]=[1,4,3]
        with self.assertRaisesRegex(RuntimeError,'collinear'):resolve_material(w.env,selector,0)

    def test_bad_ids_missing_vertices_nonfinite_state_and_wrong_category_fail(self):
        w=World();label,data=attach_material(w,'cloth',[5,8,11],[[0,0,0],[1,0,0],[0,1,0]])
        with self.assertRaises(ValueError):resolve_material(w.env,{'kind':'cloth_points','label':label,'ids':[99]},0)
        data['ids']=np.array([5,5,11])
        with self.assertRaises(RuntimeError):material_state(w.env,label,'cloth',0)
        data['ids']=np.array([5,8,11]);data['positions_world'][0,0]=float('nan')
        with self.assertRaises(RuntimeError):material_state(w.env,label,'cloth',0)
        data['positions_world'][0,0]=0;w.env.scene_manager.layout_manager.instance_type_by_env[0][label]='rigid'
        with self.assertRaises(ValueError):material_state(w.env,label,'cloth',0)
        with self.assertRaises(ValueError):_validate_selector({'kind':'cloth_points','label':'cloth','ids':[1,1]},'bad')

    def test_fluid_preexisting_target_and_unheld_exit_cannot_count_as_pour(self):
        w,data=pour_world();s=AtomicSession(w.env,pour_stage(),0)
        w.tick(s);self.assertEqual(s.summary()['physical_metrics']['counts']['transferred'],0)
        data['positions_local'][0]=[.5,0,0];w.tick(s);w.tick(s)
        w.hold();w.poses['object'][3:]=[math.cos(.25),0,math.sin(.25),0]
        w.tick(s);self.assertFalse(w.tick(s))
        self.assertEqual(s.summary()['physical_metrics']['counts']['transferred'],0)

    def test_fluid_provenance_raw_outside_counts_mass_partition_and_persistent_ids(self):
        w,data=pour_world();s=AtomicSession(w.env,pour_stage(),0)
        w.hold();w.tick(s);w.tick(s)
        w.poses['object'][3:]=[math.cos(.25),0,math.sin(.25),0]
        data['positions_local'][0]=[.5,0,0];data['positions_local'][1]=[.3,0,0]
        self.assertFalse(w.tick(s))
        # Backend may reorder rows: identity follows persistent IDs, not row number.
        data['ids']=data['ids'][[2,0,1]];data['positions_local']=data['positions_local'][[2,0,1]]
        self.assertTrue(w.tick(s))
        metrics=s.summary()['physical_metrics']
        self.assertEqual(metrics['counts']['target_only'],2)
        self.assertEqual(metrics['counts']['outside_both'],1)
        self.assertEqual(metrics['counts']['transferred'],1)
        self.assertEqual(metrics['partition_count_error'],0)
        self.assertEqual(metrics['transferred_particle_ids'],[7])
        self.assertAlmostEqual(metrics['outside_both_nominal_mass_kg'],.0005)
        self.assertEqual(set(s.summary()['physical_events']),{'source_exit','first_transfer','transfer_complete'})
        self.assertIn('in-flight',metrics['outside_semantics'])

    def test_fluid_population_changes_are_backend_failure_not_lost_mass_pass(self):
        w,data=pour_world();s=AtomicSession(w.env,pour_stage(),0)
        data['ids']=data['ids'][:-1];data['positions_local']=data['positions_local'][:-1]
        with self.assertRaisesRegex(RuntimeError,'identity/population'):w.tick(s)

    def test_fluid_sampling_gap_cannot_borrow_an_unobserved_exit(self):
        w,data=pour_world();s=AtomicSession(w.env,pour_stage(),0)
        w.hold();w.tick(s);w.tick(s)
        w.contacts.steps+=4;w.poses['object'][3:]=[math.cos(.25),0,math.sin(.25),0]
        data['positions_local'][0]=[.5,0,0]
        w.tick(s);self.assertFalse(w.tick(s))
        self.assertEqual(s.summary()['physical_metrics']['counts']['transferred'],0)
