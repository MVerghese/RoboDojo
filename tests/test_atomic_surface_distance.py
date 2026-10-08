import unittest
import numpy as np
from task.atomic.surface_distance import mesh_surface_gap,triangle_gap,point_surface_distances
from task.atomic.geometry import evaluate_geometry


class SurfaceDistanceTests(unittest.TestCase):
    def test_point_distance_uses_face_interior_edges_and_vertices_with_rigid_invariance(self):
        triangle=np.array([[0,0,0],[2,0,0],[0,2,0.]])
        points=np.array([[.5,.5,.003],[1.5,1.5,0],[3,0,0],[.5,.5,0.]])
        expected=[.003,np.sqrt(.5),1.,0.]
        np.testing.assert_allclose(point_surface_distances(points,triangle,[[0,1,2]]),expected,atol=1e-12)
        rotation=np.array([[0,0,1],[1,0,0],[0,1,0]]);shift=[10,20,30]
        np.testing.assert_allclose(point_surface_distances(points@rotation+shift,triangle@rotation+shift,[[0,1,2]]),expected,atol=1e-12)

    def test_point_distance_handles_sliver_and_ignored_degenerate_faces_without_solid_inference(self):
        v=np.array([[0,0,0],[1,0,0],[1,1e-8,0.]])
        self.assertAlmostEqual(point_surface_distances([[.75,2e-9,.004]],v,[[0,1,2],[0,0,0]])[0],.004)
        with self.assertRaisesRegex(ValueError,'nondegenerate'):point_surface_distances([[0,0,0]],v,[[0,0,0]])
        with self.assertRaisesRegex(ValueError,'finite XYZ'):point_surface_distances([[np.nan,0,0]],v,[[0,1,2]])

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
