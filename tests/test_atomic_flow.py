import unittest
from task.atomic.flow import FlowObserver, score_crossing

C={'opening':{'kind':'object_pose','label':'vase'},
   'aperture_profile':{'outer':[[-.02,-.02],[.02,-.02],[.02,.02],[-.02,.02]]},
   'target_xy_m':[0,0],'position_tolerance_m':.005,'angle_tolerance_rad':.2}
FRAME=[0,0,0,1,0,0,0]


class FlowTests(unittest.TestCase):
    def test_crossing_outside_aperture_is_measured_as_failure(self):
        a={'position':[.03,0,.01],'opening':FRAME,'dt_s':.01}
        b={'position':[.03,0,-.01],'opening':FRAME,'dt_s':.01}
        r=score_crossing(C,a,b);self.assertFalse(r['passed'])
        self.assertAlmostEqual(r['components']['crossing_position_error_m'],.03)
        self.assertAlmostEqual(r['components']['aperture_overrun_m'],.01)

    def test_moving_target_translation_is_subtracted_from_velocity(self):
        a={'position':[0,0,.01],'opening':FRAME,'dt_s':.01}
        b={'position':[.05,0,-.01],'opening':[.05,0,0,1,0,0,0],'dt_s':.01}
        r=score_crossing(C,a,b);self.assertTrue(r['passed'])
        self.assertEqual(r['components']['velocity_angle_rad'],0.)

    def test_unqualified_material_and_sampling_gap_do_not_create_flow_measurements(self):
        o=FlowObserver(C)
        o.observe({'p':[0,0,.01]},FRAME,{},1,.01)
        o.observe({'p':[0,0,-.01]},FRAME,{},2,.01)
        self.assertFalse(o.crossings)
        o.observe({'p':[0,0,.01]},FRAME,{'p':{'exited_while_held_and_tilted':True}},3,.01)
        o.observe({'p':[0,0,-.01]},FRAME,{'p':{}},5,.01)
        self.assertFalse(o.crossings);self.assertEqual(o.failures[0]['status'],'sampling_gap')

    def test_only_first_crossing_of_each_identity_is_scored(self):
        o=FlowObserver(C);provenance={'p':{'eligible':True,'exited_while_held_and_tilted':True}}
        for step,z in enumerate([.01,-.01,.01,-.01],1):o.observe({'p':[0,0,z]},FRAME,provenance,step,.01)
        self.assertEqual(o.summary()['scored_crossings'],1)


if __name__=='__main__':unittest.main()
