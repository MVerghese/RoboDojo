import unittest
import numpy as np
from task.atomic.surface_distance import mesh_surface_gap,triangle_gap
from task.atomic.geometry import evaluate_geometry


class SurfaceDistanceTests(unittest.TestCase):
    def test_edge_piercing_and_coplanar_crossing_without_near_vertices(self):
        a=np.array([[-1,-1,0],[1,-1,0],[0,1,0.]])
        b=np.array([[0,0,-1],[0,0,1],[2,0,1.]])
        self.assertEqual(triangle_gap(a,b),0)
        b=np.array([[-1,0,0],[1,0,0],[0,-2,0.]])
        self.assertEqual(triangle_gap(a,b),0)

    def test_boundary_gap_is_not_vertex_or_centre_distance(self):
        a=np.array([[-1,-1,0],[1,-1,0],[0,1,0.]])
        b=np.array([[-.1,-.1,.003],[.1,-.1,.003],[0,.1,.003]])
        r=mesh_surface_gap(a,[[0,1,2]],b,[[0,1,2]])
        self.assertAlmostEqual(r['surface_distance_m'],.003)
        surface=lambda v,p:{'vertices':v.tolist(),'triangles':[[0,1,2]],'position':p,'orientation':[1,0,0,0]}
        result=evaluate_geometry({'kind':'spatial_relation','relation_scope':'objects','expected':'near','tolerance':.005},surface(a,[0,0,0]),surface(b,[100,100,100]))
        self.assertTrue(result.passed);self.assertAlmostEqual(result.error,.003)

    def test_bvh_matches_exhaustive_gap_and_is_rigid_transform_invariant(self):
        rng=np.random.default_rng(4);a=rng.normal(size=(12,3,3));b=rng.normal(size=(15,3,3))+[4,0,0]
        expected=min(triangle_gap(x,y) for x in a for y in b)
        faces=lambda q:np.arange(q.size//3).reshape(-1,3)
        r=mesh_surface_gap(a.reshape(-1,3),faces(a),b.reshape(-1,3),faces(b))
        self.assertAlmostEqual(r['surface_distance_m'],expected)
        rotation=np.array([[0,-1,0],[1,0,0],[0,0,1]]);shift=[10,20,30]
        r=mesh_surface_gap(a.reshape(-1,3)@rotation+shift,faces(a),b.reshape(-1,3)@rotation+shift,faces(b))
        self.assertAlmostEqual(r['surface_distance_m'],expected)
        with self.assertRaisesRegex(ValueError,'nondegenerate'):mesh_surface_gap([[0,0,0]]*3,[[0,1,2]],b.reshape(-1,3),faces(b))


if __name__=='__main__':unittest.main()
