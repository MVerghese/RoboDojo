"""Moving landmarks and aligned mouth points must preserve the declared factor semantics."""
from copy import deepcopy
import unittest
from scripts.atomic.generate_spout_factor_suite import conditions
from task.atomic.geometry import evaluate_geometry


def stage():
    def frame(label):return {'kind':'model_calibrated_frame','label':label,'models':{'vessel/00000':{
        'local_pose':[0,0,.1,1,0,0,0],'calibration_id':'reviewed mouth','asset_sha256':'a'*64,
        'scaled_bounds_m':[[-.05,-.05,0],[.05,.05,.1]]}}}
    return {'recognition':{'source_exit':{'opening':frame('bottle')},'flow':{'opening':frame('cup')}}}


class SpoutFactorTests(unittest.TestCase):
    def test_fixed_initial_point_and_live_offset_diverge_when_the_cup_moves(self):
        point,_=conditions(stage(),'point');offset,_=conditions(stage(),'displacement')
        self.assertEqual(point[0]['reference']['time'],'stage_start');self.assertNotIn('time',offset[0]['reference'])
        mouth=[.04,0,.08];initial=[0,0,0,1,0,0,0];moved=[.04,0,0,1,0,0,0]
        self.assertFalse(evaluate_geometry(point[0],mouth,initial).passed)
        self.assertTrue(evaluate_geometry(offset[0],mouth,moved).passed)

    def test_above_relation_also_requires_mouth_projection_in_the_declared_column(self):
        rows,text=conditions(stage(),'spatial_relation');opening=[0,0,0,1,0,0,0];corridor=[0,0,.08,1,0,0,0]
        self.assertTrue(all(evaluate_geometry(c,[0,0,.08],ref).passed for c,ref in zip(rows,[opening,corridor])))
        point=[.03,0,.08]
        self.assertTrue(evaluate_geometry(rows[0],point,opening).passed)
        self.assertFalse(evaluate_geometry(rows[1],point,corridor).passed)
        self.assertFalse(evaluate_geometry(rows[0],[0,0,.03],opening).passed)
        self.assertEqual(rows[0]['measurement']['kind'],'model_calibrated_position')
        self.assertIn('not whole-bottle footprint',text)
