"""Nominal axes need actual successful force grasps and attainable geometry."""
from copy import deepcopy
import unittest
from scripts.atomic.generate_calibrated_contact_frames import calibrate
from test_atomic_contact_pose import runtime,selector,condition


def fixture():
    session,_=runtime();measured,source=session._resolve_with_source(selector())
    pose=condition();pose.update(id='contact_frame_pose',tolerance=.03,reference={'kind':'object_center_pose','label':'object'},
        event={'kind':'first_lift','label':'object','threshold':.025})
    direction={**deepcopy(pose),'id':'contact_frame_z','kind':'relative_orientation','expected':[1,0,0,0],'orientation_axes':[2]}
    direction.pop('angle_tolerance_rad')
    program={'stages':[{'id':'pick','family':'pick','geometry':[pose,direction]}]}
    detail={'layout_id':0,'atomic_sequence':{'stages':[{'stage_id':'pick','action_success':True,
        'geometry':{'contact_frame_pose':{'condition':deepcopy(pose),'measured_state':measured,
            'measurement_source':source,'reference_state':[0,0,0,1,0,0,0]}}}]}}
    return program,detail


class ContactFrameCalibrationTests(unittest.TestCase):
    def test_nominal_contact_pose_is_feasible_in_verified_physical_grasp(self):
        program,detail=fixture();before=deepcopy(program)
        output,text,rows=calibrate(program,detail)
        self.assertEqual(program,before)
        self.assertEqual(rows[0]['resolved_link'],'palm')
        self.assertAlmostEqual(rows[0]['nominal']['contact_frame_pose']['components']['position_m'],.01)
        self.assertAlmostEqual(rows[0]['nominal']['contact_frame_pose']['components']['orientation_rad'],0.)
        self.assertTrue(rows[0]['nominal']['contact_frame_pose']['passed'])
        self.assertIn('15 degrees full rotation error',text)

    def test_failed_grasp_corrupt_force_and_changed_frame_binding_cannot_calibrate(self):
        for change in ('action','force','binding','layout'):
            program,detail=fixture();stage=detail['atomic_sequence']['stages'][0];raw=stage['geometry']['contact_frame_pose']
            if change=='action':stage['action_success']=False
            elif change=='force':raw['measurement_source']['contact_source']['contacts'][0]['impulse']=[0,0,0]
            elif change=='binding':program['stages'][0]['geometry'][0]['measurement']['label']='different'
            else:detail['layout_id']=1
            with self.subTest(change=change),self.assertRaises(ValueError):calibrate(program,detail)

    def test_successful_pick_does_not_make_an_unattainable_translation_target_valid(self):
        program,detail=fixture();program['stages'][0]['geometry'][0]['expected']['position']=[.5,0,0]
        with self.assertRaisesRegex(ValueError,'cannot satisfy'):calibrate(program,detail)


if __name__=='__main__':unittest.main()
