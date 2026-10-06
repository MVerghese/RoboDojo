"""A quiet contact is support only with contact lifecycle and unchanged poses."""
from types import SimpleNamespace as NS
from types import ModuleType
from unittest.mock import patch
import ast
from pathlib import Path
import unittest
import numpy as np
from task.atomic.contacts import PhysXContacts


def world():
    b=PhysXContacts.__new__(PhysXContacts)
    poses={label:np.array([0.,0.,0.,1.,0.,0.,0.]) for label in ['object','support']}
    lm=NS(get_instance_name=lambda env_idx,label:label,
          get_scene_object=lambda env_idx,name:NS(usd_prim_path='/env/'+name),
          get_instance_pose=lambda env_idx,label:(poses[label][:3],poses[label][3:]))
    b.env=NS(scene_manager=NS(layout_manager=lm));b.errors=[];b.steps=1;b.reports=0;b._lost_pairs=set()
    b._decode=lambda x:x;b._contact_event_lost=2
    b.rows=[{'actor0':'/env/object','collider0':'/env/object/shape','actor1':'/env/support',
             'collider1':'/env/support/shape','position_world':[0,0,0],
             'normal_world':[0,0,1],'impulse':[0,0,.001],'lifecycle_supported':True}]
    return b,poses


class PersistentSupportTests(unittest.TestCase):
    def test_reloaded_same_body_paths_cannot_inherit_support(self):
        b,_=world();b.support_evidence('object',['support'],0)
        b.material_states={'old':'vertices'};b.pair_diagnostics={};b.report_pair_diagnostics={}
        b.event_types={};b.enable_errors=[]
        b.reset_scene_evidence()
        self.assertFalse(b.support_evidence('object',['support'],0)['contacts'])
        self.assertFalse(b.material_states)
        self.assertEqual(b.reports,0)

    def test_report_enablement_includes_bodies_loaded_after_simulator_setup(self):
        b,_=world();b.enable_errors=[];b.enabled_body_paths=[]
        prims=[NS(HasAPI=lambda _:True,GetPath=lambda:'/robot/finger')];thresholds=[]
        stage=NS(GetPseudoRoot=lambda:prims)
        omni=ModuleType('omni');omni.usd=NS(get_context=lambda:NS(get_stage=lambda:stage))
        pxr=ModuleType('pxr');pxr.UsdPhysics=NS(RigidBodyAPI=object())
        pxr.Usd=NS(PrimRange=lambda root,_:iter(root),TraverseInstanceProxies=lambda:None)
        pxr.PhysxSchema=NS(PhysxContactReportAPI=NS(Apply=lambda prim:NS(CreateThresholdAttr=lambda value:thresholds.append((prim.GetPath(),value)))))
        with patch.dict('sys.modules',{'omni':omni,'omni.usd':omni.usd,'pxr':pxr}):
            b.enable_scene_contacts()
            prims.append(NS(HasAPI=lambda _:True,GetPath=lambda:'/task/block'))
            b.enable_scene_contacts()
        self.assertIn('/task/block',b.enabled_body_paths)
        self.assertIn(('/task/block',0.0),thresholds)
        tree=ast.parse((Path(__file__).resolve().parents[1]/'src/eval_client/eval_env.py').read_text())
        reset=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='reset')
        calls=[n for n in ast.walk(reset) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)]
        load=next(n.lineno for n in calls if n.func.attr=='setup_scene')
        enable=next(n.lineno for n in calls if n.func.attr=='enable_scene_contacts')
        self.assertGreater(enable,load)

    def test_quiet_rest_preserves_support_but_never_current_force_claim(self):
        b,_=world();self.assertTrue(b.support_evidence('object',['support'],0)['contacts'])
        b.begin_step();r=b.support_evidence('object',['support'],0)
        self.assertTrue(r['contacts']);self.assertEqual(r['support_evidence_kind'],'persistent_unchanged_contact')
        self.assertEqual(r['contacts'][0]['last_force_report_physics_step'],1)

    def test_object_motion_support_motion_and_lost_event_invalidate_history(self):
        for cause in ['object','support','lost']:
            b,poses=world();b.support_evidence('object',['support'],0);b.begin_step()
            if cause=='lost':
                b._report([NS(type=2,actor0='/env/object',actor1='/env/support',collider0='/env/object/shape',collider1='/env/support/shape')],[])
            else:poses[cause][0]+=.001
            self.assertFalse(b.support_evidence('object',['support'],0)['contacts'])

    def test_no_lifecycle_no_history_and_downward_contact_cannot_reuse_upward_force(self):
        b,_=world();b.rows[0]['lifecycle_supported']=False
        b.support_evidence('object',['support'],0);b.begin_step()
        self.assertFalse(b.support_evidence('object',['support'],0)['contacts'])
        b,_=world();b.support_evidence('object',['support'],0)
        b.rows[0]['normal_world']=[0,0,-1];b.rows[0]['impulse']=[0,0,-.001]
        self.assertFalse(b.support_evidence('object',['support'],0)['contacts'])
        b.begin_step();self.assertFalse(b.support_evidence('object',['support'],0)['contacts'])


if __name__=='__main__':unittest.main()
