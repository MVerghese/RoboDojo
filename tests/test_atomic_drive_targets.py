"""Physical joint equality must not hide different actuator commands."""
from copy import deepcopy
import math
import unittest
from unittest.mock import patch
import numpy as np
from task.atomic.robot_kinematics import capture_robot_joints,compare_robot_joints
from test_atomic_robot_kinematics import robot_session,schema,ROOT


def capture():
    session=robot_session();data=session.env.robot_manager.robot_key[0].data
    data.joint_pos_target=np.array([[.4,.02]]);data.joint_vel_target=np.array([[.1,0.]])
    with patch('task.atomic.robot_kinematics._joint_schema',side_effect=schema):raw=capture_robot_joints(session)
    return session,raw


class DriveTargetsTests(unittest.TestCase):
    def test_command_buffers_are_copied_and_separate_from_actual_state(self):
        session,a=capture();row=a['articulations'][ROOT]
        self.assertEqual(row['joints'][0]['position'],.2)
        self.assertEqual(row['drive_targets']['joints'][0]['position_target'],.4)
        session.env.robot_manager.robot_key[0].data.joint_pos_target[:]=10
        self.assertEqual(row['drive_targets']['joints'][0]['position_target'],.4)
        self.assertEqual(row['joints'][0]['position'],.2)

    def test_equal_physical_state_can_have_nonzero_command_residuals_in_each_unit(self):
        _,a=capture();b=deepcopy(a);commands=b['articulations'][ROOT]['drive_targets']['joints']
        commands[0]['position_target']+=2*math.pi;commands[0]['velocity_target']+=math.pi/6
        commands[1]['position_target']+=.003;commands[1]['velocity_target']+=.004
        result=compare_robot_joints(a,b,25,25)
        self.assertTrue(all(j['position_error']==0 and j['velocity_error']==0 for j in result['joints']))
        targets={j['name']:j for j in result['drive_targets']['joints']}
        self.assertAlmostEqual(targets['elbow']['position_target_error'],360)
        self.assertAlmostEqual(targets['elbow']['velocity_target_error'],30)
        self.assertAlmostEqual(targets['jaw']['position_target_error'],3)
        self.assertAlmostEqual(targets['jaw']['velocity_target_error'],4)

    def test_missing_failed_command_capture_does_not_erase_physical_joint_evidence(self):
        session,a=capture();key=session.env.robot_manager.robot_key[0]
        del key.data.joint_pos_target
        with patch('task.atomic.robot_kinematics._joint_schema',side_effect=schema):b=capture_robot_joints(session)
        self.assertEqual(b['status'],'observed_robot_joints')
        self.assertEqual(b['articulations'][ROOT]['drive_targets']['status'],'unavailable')
        result=compare_robot_joints(a,b,25,25)
        self.assertEqual(result['status'],'observed_joint_comparison')
        self.assertEqual(result['drive_targets']['status'],'unavailable')
        # Older records did not retain command targets.
        b=deepcopy(a);del b['articulations'][ROOT]['drive_targets']
        self.assertEqual(compare_robot_joints(a,b,25,25)['drive_targets']['status'],'unavailable')

    def test_misbound_units_nonfinite_values_and_wrong_source_cannot_certify_commands(self):
        _,a=capture()
        changes=[lambda t:t['source'].__setitem__('position_api','IsaacLab.Articulation.data.joint_pos'),
            lambda t:t['joints'][0].__setitem__('joint_path','/different/elbow'),
            lambda t:t['joints'][0].__setitem__('position_unit','degrees'),
            lambda t:t['joints'][0].__setitem__('position_target',float('nan')),
            lambda t:t['joints'][1].__setitem__('name','elbow'),lambda t:t['joints'].pop()]
        for change in changes:
            b=deepcopy(a);change(b['articulations'][ROOT]['drive_targets'])
            result=compare_robot_joints(a,b,25,25)
            self.assertEqual(result['status'],'observed_joint_comparison')
            self.assertEqual(result['drive_targets']['status'],'unavailable')
            self.assertEqual(result['drive_targets']['joints'],[])

    def test_report_displays_command_units_separately_and_historical_missing_as_na(self):
        from scripts.atomic.continuous_report import drive_validation_rows,DRIVE_HEADERS
        _,a=capture();b=deepcopy(a);b['articulations'][ROOT]['drive_targets']['joints'][1]['velocity_target']+=.004
        compare=compare_robot_joints(a,b,25,25)
        data={'replay_validations':[{'task':'task','episodes':[{'atomic_start':{'stage_id':'s'},
             'boundary_position_comparison':{'robot_kinematics':compare}}]}]}
        row=drive_validation_rows(data)[0]
        self.assertEqual(row,['task','s',2,'0.0000','0.0000','0.0000','4.0000'])
        self.assertEqual(len(row),len(DRIVE_HEADERS))
        data['replay_validations'][0]['episodes'][0]['boundary_position_comparison']={}
        self.assertEqual(drive_validation_rows(data)[0][-4:],['N/A']*4)


if __name__=='__main__':unittest.main()
