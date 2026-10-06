import unittest
from task.atomic.fit import section_fit, seating_metrics
from task.atomic.geometry import GeometryUnavailable
from test_atomic_regions import cube


class FitTests(unittest.TestCase):
    def test_cross_section_clearance_and_blocked_opening(self):
        vertices, faces = cube(-.01,.01)
        profile={'outer':[[-.02,-.02],[.02,-.02],[.02,.02],[-.02,.02]]}
        r=section_fit(vertices,faces,profile,.005)
        self.assertTrue(r['passed']);self.assertAlmostEqual(r['boundary_distance_m'],.01)
        self.assertFalse(section_fit(vertices,faces,profile,.015)['passed'])

    def test_obstacle_engulfed_by_section_is_not_hidden_by_vertex_fit(self):
        vertices,faces=cube(-.01,.01)
        profile={'outer':[[-.02,-.02],[.02,-.02],[.02,.02],[-.02,.02]],
                 'holes':[[[-.002,-.002],[-.002,.002],[.002,.002],[.002,-.002]]]}
        r=section_fit(vertices,faces,profile)
        self.assertFalse(r['passed']);self.assertAlmostEqual(r['outside_aperture_area_m2'],.000016)

    def test_object_not_crossing_plane_is_unobserved(self):
        vertices,faces=cube(-.01,.01);vertices[:,2]+=.1
        with self.assertRaises(GeometryUnavailable):section_fit(vertices,faces,{'outer':[[-1,-1],[1,-1],[1,1],[-1,1]]})

    def test_flush_measurement_uses_named_faces_not_root_alignment(self):
        r=seating_metrics([.003,0,.01,1,0,0,0],[0,0,0,1,0,0,0])
        self.assertAlmostEqual(r['seating_gap_m'],.01)
        self.assertAlmostEqual(r['seating_lateral_error_m'],.003)
        self.assertEqual(r['seating_axis_error_rad'],0.)


if __name__=='__main__':unittest.main()
