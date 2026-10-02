"""Articulated child motion must change geometry even when root pose is fixed."""
from copy import deepcopy
from types import SimpleNamespace as NS
import math
import unittest

import numpy as np
from test_atomic_physical_runtime import World
from task.atomic.session import AtomicSession
from task.atomic.contacts import PhysXContacts
from task.atomic.geometry import evaluate_geometry
from task.atomic.spec import AtomicStage,_validate_condition
from task.atomic.surfaces import ObjectSurfaces,_reject_shear


def scene():
    w=World(); data=np.array([[[0.,0.,0.,0.,0.,0.,1.],[0.,0.,.04,0.,0.,0.,1.]]])
    physics=NS(get_link_transforms=lambda:data.copy())
    obj=NS(_articulation_view=NS(_physics_view=physics,body_names=['base','cap']))
    lm=w.env.scene_manager.layout_manager
    lm.instance_type_by_env=[{'object':'articulation','target':'rigid'}]
    lm.get_instance_name=lambda env_idx,label:label
    lm.get_scene_object=lambda env_idx,inst_name:obj
    w.env.sim=NS(scene=NS(env_origins=np.zeros((1,3))))
    surfaces=ObjectSurfaces(w.env);w.env._atomic_surfaces=surfaces
    points=np.array([[-.01,-.01,0],[.01,-.01,0],[0,.01,0]])
    surfaces.cache[(0,'object')]={'prim_path':'/env/button','parts':[
        {'link':'base','prim_path':'/env/button/base','points':points.copy(),'triangles':[[0,1,2]]},
        {'link':'cap','prim_path':'/env/button/cap','points':points.copy(),'triangles':[[0,1,2]]}]}
    surfaces.cache[(0,'target')]=(points.copy(),[[0,1,2]],'/env/target')
    return w,data,surfaces


class ArticulatedSurfaceTests(unittest.TestCase):
    def test_child_pose_moves_mesh_and_center_while_root_remains_fixed(self):
        w,data,surfaces=scene();root=w.poses['object']
        first=surfaces.resolve('object',0,root)
        self.assertAlmostEqual(first['position'][2],.02)
        data[0,1,2]=.2
        second=surfaces.resolve('object',0,root)
        self.assertAlmostEqual(second['position'][2],.1)
        self.assertAlmostEqual(second['vertices'][3][2],.2)
        self.assertEqual(second['vertices'][0][2],0.)
        self.assertIn('PhysX',second['geometry_representation'])
        np.testing.assert_allclose(surfaces.center_pose('object',0,root)[:3],second['position'])

    def test_link_scope_excludes_other_links_and_follows_rotation(self):
        w,data,surfaces=scene()
        data[0,1,3:]=[0,0,math.sqrt(.5),math.sqrt(.5)]
        result=surfaces.resolve_link('object','cap',0)
        self.assertEqual(len(result['vertices']),3)
        self.assertEqual(result['prim_path'],'/env/button/cap')
        np.testing.assert_allclose(result['vertices'][0],[.01,-.01,.04],atol=1e-8)
        with self.assertRaises(ValueError):surfaces.resolve_link('object','absent',0)

    def test_historical_footprint_keeps_old_child_geometry_not_only_old_root(self):
        w,data,surfaces=scene();w.poses['target'][2]=.5
        c={'id':'above','slot':'goal','kind':'spatial_relation','relation_scope':'objects',
           'measurement':{'kind':'object_pose','label':'target'},
           'reference':{'kind':'object_center_pose','label':'object','time':'stage_start'},
           'expected':'above','tolerance':.001}
        stage=AtomicStage.from_dict({'id':'move','family':'place','instruction':'move',
              'success_checks':[{'name':'is_test_goal','args':{}}],'geometry':[c]})
        s=AtomicSession(w.env,stage,0)
        data[0,1,2]=.3
        _,_,historical,_=s._resolve_condition(c)
        self.assertAlmostEqual(max(p[2] for p in historical['vertices']),.04)
        live=deepcopy(c);live['reference']['time']='live'
        _,_,current,_=s._resolve_condition(live)
        self.assertAlmostEqual(max(p[2] for p in current['vertices']),.3)
        historical['vertices'][0][2]=42
        self.assertNotEqual(s._resolve_condition(c)[2]['vertices'][0][2],42)

    def test_deformables_cannot_reuse_rigid_cache(self):
        w,_,surfaces=scene()
        w.env.scene_manager.layout_manager.instance_type_by_env[0]['target']='garment'
        with self.assertRaisesRegex(RuntimeError,'deforming material'):surfaces.resolve('target',0,w.poses['target'])
        with self.assertRaisesRegex(RuntimeError,'deforming material'):surfaces.center_pose('target',0,w.poses['target'])

    def test_link_support_requires_named_link_contact_in_both_actor_orders(self):
        w,_,_=scene();w.poses['target'][2]=.04
        lm=w.env.scene_manager.layout_manager
        articulation=lm.get_scene_object(0,'object');articulation.usd_prim_path='/env/button'
        lm.get_scene_object=lambda env_idx,inst_name:articulation if inst_name=='object' else NS(usd_prim_path='/env/target')
        backend=PhysXContacts.__new__(PhysXContacts)
        backend.env=w.env;backend.errors=[];backend.steps=2;w.env._atomic_contacts=backend
        c={'id':'top','slot':'goal','kind':'spatial_relation','relation_scope':'objects',
           'measurement':{'kind':'object_pose','label':'target'},
           'reference':{'kind':'articulated_link_pose','label':'object','link':'cap'},
           'expected':'on_top','tolerance':.001}
        stage=AtomicStage.from_dict({'id':'put','family':'place','instruction':'put',
              'success_checks':[{'name':'is_test_goal','args':{}}],'geometry':[c]})
        s=AtomicSession(w.env,stage,0)
        for reverse in (False,True):
            for link in ('cap','base'):
                a,b=('/env/target','/env/button/'+link)
                sign=1
                if reverse:a,b=b,a;sign=-1
                backend.rows=[{'actor0':a,'actor1':b,'collider0':a+'/shape','collider1':b+'/shape',
                    'position_world':[0,0,.04],'normal_world':[0,0,sign],'impulse':[0,0,sign]}]
                measured,_,reference,_=s._resolve_condition(c)
                self.assertEqual(measured['support_contact'],link=='cap')
                self.assertEqual(evaluate_geometry(c,measured,reference).passed,link=='cap')
                self.assertEqual(measured['support_contact_evidence']['support_contact_scopes'],{'object':'/env/button/cap'})
                # Scope both sides: contact at the cap cannot stand in for base support.
                self.assertFalse(backend.has_support_contact('target','object',0,
                    object_body_path='/env/target/unrelated',support_body_paths={'object':'/env/button/cap'}))
        with self.assertRaisesRegex(ValueError,'belong'):
            backend.support_evidence('target',['object'],0,support_body_paths={'object':'/env/other/cap'})

    def test_rotation_plus_scale_template_rejects_shear(self):
        matrix=np.eye(4);matrix[:3,:3]=np.diag([2.,3.,4.])@np.array([[0.,-1.,0.],[1.,0.,0.],[0.,0.,1.]])
        _reject_shear(matrix)
        matrix[0,0]=.2
        with self.assertRaisesRegex(RuntimeError,'sheared'):_reject_shear(matrix)
