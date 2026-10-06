import unittest
import numpy as np
from task.atomic.fit import section_fit, seating_metrics, trace_section_fit, oriented_trace_section
from task.atomic.geometry import GeometryUnavailable
from test_atomic_regions import cube


class FitTests(unittest.TestCase):
    def test_open_ends_do_not_invalidate_a_closed_local_shaft_section(self):
        vertices,faces = cube(-.01,.01)
        walls = faces[4:]  # Actual open tube: no invented caps/whole-solid claim.
        profile = {'outer':[[-.02,-.02],[.02,-.02],[.02,.02],[-.02,.02]]}
        with self.assertRaisesRegex(ValueError,'closed'):section_fit(vertices,walls,profile)
        r = trace_section_fit(vertices,walls,profile,.005)
        self.assertTrue(r['passed']);self.assertAlmostEqual(r['section_area_m2'],.0004)
        self.assertEqual(r['plane_trace_segments'],8)
        self.assertFalse(trace_section_fit(vertices,walls,profile,.015)['passed'])
        self.assertIn('not whole-solid',r['certification'])

    def test_missing_reversed_duplicate_and_coplanar_traces_are_unavailable(self):
        vertices,faces = cube(-.01,.01);walls = faces[4:]
        bad = walls.copy();bad[0] = bad[0][::-1]
        for malformed in (walls[:-1],bad,np.concatenate([walls,walls[:1]])):
            with self.assertRaises(GeometryUnavailable):oriented_trace_section(vertices,malformed)
        vertices[:,2] += .01  # Plane lies on an entire bottom edge.
        with self.assertRaisesRegex(GeometryUnavailable,'coincides'):oriented_trace_section(vertices,walls)
        # Closed degree counts alone cannot admit a crossing bow-tie trace.
        vertices,faces = cube(-.01,.01)
        vertices[[0,4],:2] = [-.01,-.01];vertices[[1,5],:2] = [.01,.01]
        vertices[[2,6],:2] = [-.01,.01];vertices[[3,7],:2] = [.01,-.01]
        vertices[:,2] -= .002  # The crossing lies inside trace edges, not at their endpoints.
        with self.assertRaisesRegex(GeometryUnavailable,'cross|overlap'):
            oriented_trace_section(vertices,faces[4:])

    def test_oriented_traces_preserve_material_holes_and_aperture_obstacles(self):
        outer,faces = cube(-.01,.01);inner,_ = cube(-.002,.002)
        vertices = np.concatenate([outer,inner])
        walls = np.concatenate([faces[4:],faces[4:,::-1]+8])
        section,proof = oriented_trace_section(vertices,walls)
        self.assertAlmostEqual(section.area,.000384)
        self.assertEqual(len(section.interiors),1)
        profile = {'outer':[[-.02,-.02],[.02,-.02],[.02,.02],[-.02,.02]],
            'holes':[[[-.001,-.001],[-.001,.001],[.001,.001],[.001,-.001]]]}
        self.assertTrue(trace_section_fit(vertices,walls,profile)['passed'])
        self.assertFalse(trace_section_fit(outer,faces[4:],profile)['passed'])
        # A second nested outward shell is ambiguous material, not a cavity.
        with self.assertRaisesRegex(GeometryUnavailable,'winding'):
            oriented_trace_section(vertices,np.concatenate([faces[4:],faces[4:]+8]))

    def test_trace_schema_and_runtime_use_material_mesh_and_opening_frame_evidence(self):
        from copy import deepcopy
        from types import SimpleNamespace as NS
        from task.atomic.spec import AtomicStage
        from task.atomic.session import AtomicSession
        from test_atomic_physical_runtime import World
        from scripts.atomic.audit_scores import audit_atomic
        w = World();w.poses['target'][:3] = 0
        lm = w.env.scene_manager.layout_manager
        lm.get_instance_name = lambda env_idx,label:label
        lm.instance_type_by_env = [{'object':'rigid','target':'geometry'}]
        vertices,faces = cube(-.01,.01)
        def surface(label,idx,pose,**kw):
            self.assertEqual(label,'object')  # Opening's render mesh is irrelevant.
            self.assertEqual(kw['mesh_paths'],['actual/shaft'])
            return {'vertices':vertices.tolist(),'triangles':faces[4:].tolist(),
                    'geometry_representation':'actual selected material mesh'}
        w.env._atomic_surfaces = NS(resolve=surface)
        definition = {'id':'fit','family':'insert','instruction':'Observe local shaft fit',
            'success_checks':[{'name':'is_test_goal','args':{}}],
            'geometry':[{'id':'shaft_fit','slot':'opening','kind':'spatial_relation','relation_scope':'objects',
                'measurement':{'kind':'object_pose','label':'object','mesh_paths':['actual/shaft'],
                               'calibration_id':'reviewed actual shaft'},
                'reference':{'kind':'calibrated_frame','label':'target','local_pose':[0,0,0,1,0,0,0],
                             'calibration_id':'actual opening'},
                'expected':'inside_trace_aperture','aperture_profile':{'outer':[[-.02,-.02],[.02,-.02],[.02,.02],[-.02,.02]]},
                'tolerance':0.,'required_clearance_m':.005,'event':{'kind':'attempt_end'}}]}
        stage = AtomicStage.from_dict(definition);s = AtomicSession(w.env,stage,0);s.finalize()
        self.assertTrue(s.summary()['geometry']['shaft_fit']['result']['passed'])
        self.assertEqual(audit_atomic(s.summary())['conditions']['shaft_fit']['status'],'reproduced')
        for field,value in [('measurement',{'kind':'object_pose','label':'object'}),('min_overlap_fraction',.5),('margin',.01)]:
            bad = deepcopy(definition);bad['geometry'][0][field] = value
            with self.assertRaises(ValueError):AtomicStage.from_dict(bad)

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
