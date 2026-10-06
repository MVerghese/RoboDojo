import unittest
import numpy as np
from task.atomic.calibration import opening_section,interior_core_box
from test_atomic_regions import cube


class OpeningCalibrationTests(unittest.TestCase):
    def tube(self):
        a,at=cube(-.02,.02);b,bt=cube(-.01,.01)
        return np.vstack((a,b)),np.vstack((at,bt[:,::-1]+len(a)))

    def test_interior_core_rejects_wall_and_between_plane_obstacle(self):
        v,t=self.tube();r=interior_core_box(v,t,[0,0,0],[.005,.005,.005],.02)
        self.assertEqual(r['triangle_box_intersections'],0)
        with self.assertRaisesRegex(ValueError,'footprint'):interior_core_box(v,t,[0,0,0],[.015,.005,.005],.02)
        # An obstruction above the midpoint must be caught by triangle/box SAT.
        island,faces=cube(-.002,.002);island[:,2]+=.004
        v=np.vstack((v,island));t=np.vstack((t,faces+16))
        with self.assertRaisesRegex(ValueError,'touch or intersect'):interior_core_box(v,t,[0,0,0],[.005,.005,.008],.02)

    def test_actual_enclosed_void_not_outer_bounds(self):
        v,t=self.tube();r=opening_section(v,t,0)
        self.assertAlmostEqual(r['aperture_area_m2'],.0004)
        self.assertLess(r['maximum_endpoint_weld_displacement_m'],1e-9)
        v,t=cube(-.02,.02)
        with self.assertRaisesRegex(ValueError,'no enclosed'):opening_section(v,t,0)

    def test_open_wall_trace_does_not_certify_an_aperture(self):
        v,t=self.tube()
        with self.assertRaisesRegex(ValueError,'open, duplicate or nonmanifold'):opening_section(v,np.delete(t,4,axis=0),0)

    def test_material_island_is_forbidden_inside_aperture(self):
        v,t=self.tube();c,ct=cube(-.002,.002)
        v=np.vstack((v,c));t=np.vstack((t,ct+16))
        with self.assertRaisesRegex(ValueError,'island'):opening_section(v,t,0)
        r=opening_section(v,t,0,[.005,0]);self.assertEqual(len(r['aperture_profile']['holes']),1)
        self.assertAlmostEqual(r['aperture_area_m2'],.0004-.000016)


if __name__=='__main__':unittest.main()
