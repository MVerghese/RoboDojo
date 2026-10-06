"""Vertex-inside and outer-bounds shortcuts cannot certify a nonconvex cavity."""
import unittest
import numpy as np
from task.atomic.regions import region_containment


def cube(low=-.5, high=.5):
    vertices = np.array([[low,low,low],[high,low,low],[high,high,low],[low,high,low],
                         [low,low,high],[high,low,high],[high,high,high],[low,high,high]])
    faces = np.array([[0,2,1],[0,3,2],[4,5,6],[4,6,7],[0,1,5],[0,5,4],
                      [1,2,6],[1,6,5],[2,3,7],[2,7,6],[3,0,4],[3,4,7]])
    return vertices, faces


class RegionTests(unittest.TestCase):
    def test_single_box_matches_exact_solid_volume_and_partial_overlap(self):
        vertices, faces = cube()
        r = region_containment(vertices, faces, [{'center':[0,0,0],'half_extents':[.5,.5,.5]}])
        self.assertTrue(r['passed']); self.assertAlmostEqual(r['object_volume_m3'], 1.)
        r = region_containment(vertices, faces, [{'center':[.25,0,0],'half_extents':[.25,.5,.5]}])
        self.assertFalse(r['passed']); self.assertAlmostEqual(r['outside_volume_m3'], .5)

    def test_overlapping_boxes_do_not_double_count(self):
        vertices, faces = cube()
        r = region_containment(vertices, faces, [{'center':[x,0,0],'half_extents':[.375,.5,.5]} for x in (-.125,.125)])
        self.assertTrue(r['passed']); self.assertAlmostEqual(r['outside_volume_m3'], 0.)

    def test_all_vertices_inside_still_rejects_a_hole_engulfed_by_object(self):
        vertices, faces = cube()
        # Six slabs cover every outer vertex and surface, but omit the central solid.
        boxes=[]
        for axis in range(3):
            for sign in (-1,1):
                center=[0.,0.,0.];half=[.5,.5,.5]
                center[axis]=sign*.375;half[axis]=.125
                boxes.append({'center':center,'half_extents':half})
        r=region_containment(vertices, faces, boxes)
        self.assertEqual(r['vertex_containment_error_m'],0.)
        self.assertFalse(r['passed']);self.assertAlmostEqual(r['outside_volume_m3'],.125)

    def test_open_mesh_and_inconsistent_winding_are_unavailable_not_passes(self):
        vertices, faces=cube()
        with self.assertRaisesRegex(ValueError,'closed'):region_containment(vertices,faces[:-1],[{'center':[0,0,0],'half_extents':[1,1,1]}])
        faces[0]=faces[0][::-1]
        with self.assertRaisesRegex(ValueError,'oriented'):region_containment(vertices,faces,[{'center':[0,0,0],'half_extents':[1,1,1]}])


if __name__=='__main__':unittest.main()
