"""Native diagnostics must neither invent material IDs nor lose finger evidence."""
from types import ModuleType, SimpleNamespace as NS
from unittest.mock import patch
import unittest
import numpy as np
from task.atomic.contacts import PhysXContacts
from test_atomic_persistent_support import world


def probe():
    b,_=world()
    b.cloth_probe_enabled=True;b.cloth_probe_paths=['/env/cloth/mesh'];b.cloth_probe_samples=[]
    b.cloth_probe_counts={'headers':0,'points':0,'force_points':0,'finger_force_points':0}
    b.fingers={'/robot/finger':(0,'left_arm')}
    b._support_cache={};b.material_states={};b.pair_diagnostics={};b.report_pair_diagnostics={};b.event_types={}
    return b


class ClothContactProbeTests(unittest.TestCase):
    def test_native_face_ids_are_retained_without_solver_correspondence(self):
        b=probe()
        h=NS(actor0='/env/cloth',actor1='/robot/finger',collider0='/env/cloth/mesh',
             collider1='/robot/finger/shape',type=1,num_contact_data=1,contact_data_offset=0,
             proto_index0=4294967295,proto_index1=4)
        c=NS(impulse=[0,0,.001],position=[.1,.2,.3],normal=[0,0,1],
             face_index0=7,face_index1=11,separation=-.0001)
        b._report([h],[c])
        s=b.summary()['cloth_contact_probe']
        self.assertEqual(s['counts']['finger_force_points'],1)
        sample=s['native_samples'][0]
        self.assertEqual(sample['face_indices'],[7,11])
        self.assertEqual(sample['proto_indices'],[4294967295,4])
        self.assertEqual(sample['material_vertex_correspondence'],'unverified')
        # A normal rigid contact never becomes a cloth diagnostic.
        h.collider0='/env/object/shape';h.actor0='/env/object'
        b._report([h],[c])
        self.assertEqual(b.cloth_probe_counts['points'],1)

    def test_zero_impulse_table_samples_cannot_exhaust_later_finger_sample_budget(self):
        b=probe();h=NS();c=NS()
        for _ in range(400):
            b._probe_cloth_point(('/env/cloth','/table'),('/env/cloth/mesh','/table/shape'),
                                 h,c,np.zeros(3),np.array([0,0,1]),np.zeros(3))
        b._probe_cloth_point(('/env/cloth','/robot/finger'),('/env/cloth/mesh','/robot/finger/shape'),
                             h,c,np.zeros(3),np.array([0,0,1]),np.array([0,0,.001]))
        self.assertEqual(len(b.cloth_probe_samples),33)
        self.assertEqual(b.cloth_probe_samples[-1]['sample_bucket'],'finger_force')
        self.assertEqual(b.cloth_probe_counts['points'],401)
        b.material_states={};b.enable_errors=[]
        b.reset_scene_evidence()
        self.assertFalse(b.cloth_probe_paths)
        self.assertFalse(b.cloth_probe_samples)
        self.assertEqual(b.cloth_probe_counts['points'],0)

    def test_particle_mesh_report_api_does_not_author_a_rigid_body(self):
        b=probe();b.enable_errors=[];b.skipped_nested_body_paths=[];b.cloth_probe_paths=[]
        rigid=type('RigidAPI',(),{});cloth=type('ClothAPI',(),{})
        apis={cloth};applied=[]
        prim=NS(HasAPI=lambda api:api in apis,GetPath=lambda:'/env/cloth/mesh')
        class Report:
            @staticmethod
            def Apply(p):
                apis.add(Report);applied.append(p.GetPath())
                return NS(CreateThresholdAttr=lambda value:self.assertEqual(value,0.))
        pxr=ModuleType('pxr');pxr.UsdPhysics=NS(RigidBodyAPI=rigid)
        pxr.UsdGeom=NS();pxr.Usd=NS(PrimRange=lambda *args:[prim],TraverseInstanceProxies=lambda:None)
        pxr.PhysxSchema=NS(PhysxContactReportAPI=Report,PhysxParticleClothAPI=cloth)
        with patch.dict('sys.modules',{'pxr':pxr}):
            self.assertEqual(b._enable_contact_subtree(prim),[])
            self.assertEqual(b._enable_contact_subtree(prim),[])
        self.assertEqual(applied,['/env/cloth/mesh'])
        self.assertNotIn(rigid,apis)
        self.assertEqual(b.cloth_probe_paths,['/env/cloth/mesh'])
