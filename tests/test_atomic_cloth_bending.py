"""Actual new bending must not be confused with existing shape or rigid motion."""
from copy import deepcopy
import math
import os
from unittest.mock import patch
import unittest
import numpy as np
from task.atomic.cloth_bending import ClothBendingTopology, capture_cloth_endpoint
from task.atomic.geometry import _rotation
from task.atomic.sequence import AtomicSequence
from task.atomic.spec import AtomicProgram, AtomicStage
from scripts.atomic.analyze_cloth_bending import analyze_report,compact_diagnostics
from scripts.atomic.run_suite import execution_controls
from scripts.atomic.continuous_report import bending_display
from test_atomic_physical_runtime import World
from test_atomic_materials import attach_material

IDS=[7,9,11,13]
P=np.asarray([[0,0,0],[1,0,0],[0,1,0],[1,1,0]],dtype=float)
T=[[7,9,11],[11,9,13]]
THRESHOLDS={'min_bend_rad':math.pi/4,'min_increase_rad':math.pi/6,'min_component_length_m':.5}


def folded():
    p=P.copy();axis=(P[2]-P[1])/math.sqrt(2);v=P[3]-P[1]
    p[3]=P[1]+np.cross(axis,v)+axis*(axis@v)
    return p


class ClothBendingTests(unittest.TestCase):
    def test_new_dihedral_bending_uses_actual_interior_edge_with_units(self):
        o=ClothBendingTopology(IDS,P,T)
        result=o.measure(IDS,folded(),**THRESHOLDS)
        self.assertEqual(result['status'],'observed_bending_candidates')
        self.assertEqual(result['selected_hinges'],1)
        c=result['components'][0]
        self.assertEqual(c['edge_ids'],[[9,11]])
        self.assertAlmostEqual(c['current_bend_rad'][0],math.pi/2)
        self.assertAlmostEqual(c['total_edge_length_m'],math.sqrt(2))
        self.assertEqual(c['connectivity'],'open_chain')
        self.assertEqual(result['topology_quality'],{'boundary_edges':4})

    def test_rigid_motion_reordered_ids_and_preexisting_bend_do_not_create_new_bending(self):
        o=ClothBendingTopology(IDS,P,T)
        r=_rotation([math.cos(.4),0,math.sin(.4),0])
        moved=P@r.T+[10,-7,3]
        self.assertEqual(o.measure(IDS,moved,**THRESHOLDS)['selected_hinges'],0)
        p=folded();order=[3,0,2,1]
        result=o.measure(np.asarray(IDS)[order],p[order],**THRESHOLDS)
        self.assertEqual(result['selected_hinges'],1)
        self.assertEqual(ClothBendingTopology(IDS,p,T).measure(IDS,p,**THRESHOLDS)['selected_hinges'],0)

    def test_bad_winding_nonmanifold_faces_degenerate_and_stretched_edges_are_explicit(self):
        result=ClothBendingTopology(IDS,P,[[7,9,11],[9,11,13]]).measure(IDS,folded(),**THRESHOLDS)
        self.assertEqual(result['interior_hinges'],0)
        self.assertEqual(result['topology_quality']['inconsistent_winding_edges'],1)
        p=np.vstack((P,[[0,1,1]]));ids=IDS+[15]
        result=ClothBendingTopology(ids,p,T+[[9,11,15]]).measure(ids,p,**THRESHOLDS)
        self.assertEqual(result['topology_quality']['nonmanifold_edges'],1)
        o=ClothBendingTopology(IDS,P,T);p=folded();p[3]=p[1]
        self.assertEqual(o.measure(IDS,p,**THRESHOLDS)['degenerate_hinges'],1)
        p=folded();p[2]*=3
        self.assertEqual(o.measure(IDS,p,**THRESHOLDS)['excluded_stretched_hinges'],1)
        for ids,t in [([7.,9.1,11.,13.],T),(IDS,[[7,9,9]]),(IDS,[[7,9,99]])]:
            with self.assertRaises(ValueError):ClothBendingTopology(ids,P,t)
        with self.assertRaises(ValueError):o.measure([7,9,11,15],P,**THRESHOLDS)

    def world(self):
        w=World();w.goal=False
        label,data=attach_material(w,'cloth',IDS,P)
        data['triangles']=deepcopy(T);lm=w.env.scene_manager.layout_manager
        lm.get_labels_by_prefix=lambda **kw:[label]
        program=AtomicProgram('cloth-test',(AtomicStage.from_dict({
            'id':'fold','family':'fold','instruction':'Fold','success_checks':[{'name':'is_test_goal','args':{}}]}),))
        return w,data,program

    def test_actual_sequence_captures_endpoint_once_before_reset_with_no_success_gate(self):
        w,data,program=self.world()
        with patch.dict(os.environ,{'ATOMIC_CLOTH_BENDING_PROBE':'1'}):
            seq=AtomicSequence(w.env,program,0)
        data['positions_world']=folded();seq.finalize()
        capture=seq.summary()['cloth_bending_capture']
        self.assertEqual(capture['status'],'captured')
        np.testing.assert_allclose(capture['garments']['cloth']['positions_world'],folded())
        self.assertFalse(seq.summary()['stages'][0]['action_success'])
        report={'native_results':[{'details':{'0':{'layout_id':0,'success':False,'atomic_sequence':seq.summary()}}}]}
        results=analyze_report(report,THRESHOLDS)
        self.assertEqual(results[0]['selected_hinges'],1)
        self.assertAlmostEqual(compact_diagnostics(results)[0]['max_new_bend_rad'],math.pi/2)
        shown=bending_display(compact_diagnostics(results))[0]
        self.assertAlmostEqual(shown['max_new_bend_deg'],90)
        self.assertAlmostEqual(shown['longest_component_mm'],1000*math.sqrt(2))
        self.assertIn('max_new_bend_rad',compact_diagnostics(results)[0])
        data['positions_world']=P.copy();seq.finalize()
        np.testing.assert_allclose(seq.summary()['cloth_bending_capture']['garments']['cloth']['positions_world'],folded())
        self.assertNotIn('cloth_bending_capture',AtomicSequence(w.env,program,0).summary())

    def test_changed_mesh_and_missing_backend_are_capture_failures_and_frozen_controls_differ(self):
        w,data,program=self.world();seq=AtomicSequence(w.env,program,0)
        data['triangles']=[[7,9,13]]
        result=capture_cloth_endpoint(seq.session,seq.calibration)
        self.assertEqual(result['status'],'capture_failed')
        self.assertIn('topology differs',result['garments']['cloth']['reason'])
        a=execution_controls({});b=execution_controls({'atomic_cloth_bending_probe':True})
        self.assertNotIn('cloth_bending_probe',a)
        self.assertTrue(b['cloth_bending_probe'])


if __name__=='__main__':unittest.main()
