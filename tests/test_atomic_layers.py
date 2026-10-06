"""Patch coverage and hidden penetration use actual material triangles."""
import unittest
import numpy as np
from task.atomic.layers import patch_layers
from task.atomic.materials import resolve_patch_surface
from task.atomic.spec import AtomicStage,_validate_selector
from task.atomic.session import AtomicSession
from test_atomic_physical_runtime import World
from test_atomic_materials import attach_material


class LayerTests(unittest.TestCase):
    def patch(self,z):
        return np.array([[0,0,z],[.04,0,z],[0,.04,z]]),np.array([[0,1,2]])

    def test_actual_positive_gap_and_overhang(self):
        b,bt=self.patch(0);a,at=self.patch(.005)
        r=patch_layers(a,at,b,bt,.001,.01,.9)
        self.assertTrue(r['passed']);self.assertAlmostEqual(r['minimum_layer_gap_m'],.005)
        a[1,0]=.08
        r=patch_layers(a,at,b,bt,.001,.01,.9)
        self.assertFalse(r['passed']);self.assertLess(r['footprint_overlap_fraction'],.9)

    def test_landmark_positive_but_triangle_penetrates(self):
        b,bt=self.patch(0);a,at=self.patch(.005);a[1,2]=-.005
        r=patch_layers(a,at,b,bt,.001,.01,.9)
        self.assertFalse(r['passed']);self.assertAlmostEqual(r['minimum_layer_gap_m'],-.005)
        self.assertAlmostEqual(r['layer_gap_shortfall_m'],.006)

    def test_disjoint_patches_fail_overlap_without_invented_gap(self):
        b,bt=self.patch(0);a,at=self.patch(.005);a[:,0]+=.1
        r=patch_layers(a,at,b,bt,.001,.01)
        self.assertFalse(r['passed']);self.assertFalse(r['gap_observed'])
        self.assertNotIn('minimum_layer_gap_m',r)

    def test_persistent_face_identity_follows_solver_vertices_and_row_reordering(self):
        w=World();label,data=attach_material(w,'cloth',[5,8,11,20,21,22],
            [[0,0,0],[.04,0,0],[0,.04,0],[0,0,.005],[.04,0,.005],[0,.04,.005]])
        data['triangles']=[[5,8,11],[20,21,22]]
        def patch(face,ids):return {'kind':'cloth_patch_surface','label':label,'face_ids':[face],
                                   'origin_id':ids[0],'x_id':ids[1],'y_id':ids[2]}
        moving=patch(1,[20,21,22]);target=patch(0,[5,8,11]);_validate_selector(moving,'patch')
        condition={'id':'layer','slot':'target region','kind':'spatial_relation','expected':'layered_over',
            'measurement':moving,'reference':target,'relation_scope':'objects','min_layer_gap_m':.001,
            'max_layer_gap_m':.01,'min_overlap_fraction':.9,'tolerance':.0001,'event':{'kind':'attempt_end'}}
        stage=AtomicStage.from_dict({'id':'fold','family':'fold','instruction':'Fold',
            'success_checks':[{'name':'is_atomic_interaction','args':{}}],'geometry':[condition]})
        s=AtomicSession(w.env,stage,0);states=s._resolve_condition(condition)
        from task.atomic.geometry import evaluate_geometry
        self.assertTrue(evaluate_geometry(condition,states[0],states[2]).passed)
        order=[5,3,1,4,2,0];data['ids']=data['ids'][order];data['positions_world']=data['positions_world'][order]
        surface=resolve_patch_surface(w.env,moving,0)
        self.assertEqual(surface['material_vertex_ids'],[20,21,22])
        data['positions_world'][list(data['ids']).index(21),2]=-.005
        states=s._resolve_condition(condition);self.assertFalse(evaluate_geometry(condition,states[0],states[2]).passed)
        moving['face_ids']=[99]
        with self.assertRaisesRegex(RuntimeError,'topology'):resolve_patch_surface(w.env,moving,0)


if __name__=='__main__':unittest.main()
