"""Mouth and body frames must remain distinct in taxonomy groups and actual pose targets."""
from copy import deepcopy
import unittest
import numpy as np
from task.atomic.slot_semantics import condition_slot
from scripts.atomic.audit_scores import apply_slot_semantics,audit_atomic,apply_point_relation_observations
from scripts.atomic.generate_vessel_pose_suite import vessel_condition
from task.atomic.geometry import _rotation,evaluate_geometry


def stage():
    mouth={'kind':'model_calibrated_frame','label':'bottle','models':{'wuliangye/00000':{
        'asset_sha256':'a'*64,'scaled_bounds_m':[[-.04,-.04,-.06],[.04,.04,.16]],
        'local_pose':[0,0,.158,1,0,0,0],'calibration_id':'reviewed mouth'}}}
    opening={'kind':'object_pose','label':'cup'}
    c={'id':'mouth','slot':'source pour pose','measurement':deepcopy(mouth)}
    return {'family':'pour','recognition':{'source_exit':{'opening':mouth},'flow':{'opening':opening}},'conditions':[c]}


class SlotSemanticsTests(unittest.TestCase):
    def test_point_relation_coordinates_come_from_raw_states_not_saved_observed_metadata(self):
        c={'id':'height','slot':'spout','kind':'spatial_relation','expected':'above','relation_scope':'points',
            'margin':.04,'tolerance':.001,'measurement':{'kind':'object_position','label':'bottle'}}
        measured=[.03,.01,.07];reference=[0,0,0,1,0,0,0]
        result=evaluate_geometry(c,measured,reference).as_dict();result['observed']=[99,99,99]
        raw={'stage_id':'pour','family':'pour','action_success':False,'geometry_coverage':1,
            'conditions':[c],'geometry':{'height':{'condition':c,'measured_state':measured,'reference_state':reference,'result':result}}}
        audited=audit_atomic(raw);row=audited['conditions']['height']
        self.assertEqual(row['status'],'reproduced')
        np.testing.assert_allclose(row['point_relation_observation']['reference_relative_xyz_m'],measured)
        self.assertEqual(row['recorded_result']['components']['relation_error_m'],0)
        row['status']='invalid_recognition_window';apply_point_relation_observations(raw,audited)
        self.assertNotIn('point_relation_observation',row)

    def test_exact_source_opening_relabels_only_derived_group_and_preserves_numbers(self):
        raw=stage();before=deepcopy(raw);c=raw['conditions'][0]
        self.assertEqual(condition_slot(raw,c)[0],'spout')
        scores={'conditions':{'mouth':{'slot':'source pour pose','status':'reproduced','recorded_result':{'components':{'position_m':.03}}}}}
        apply_slot_semantics(raw,scores);self.assertEqual(raw,before)
        self.assertEqual(scores['conditions']['mouth']['slot'],'spout')
        self.assertEqual(scores['conditions']['mouth']['recorded_result']['components']['position_m'],.03)
        body=deepcopy(c);body['measurement']['models']['wuliangye/00000']['local_pose'][2]=.05
        self.assertEqual(condition_slot(raw,body),('source pour pose',None))
        body=deepcopy(c);body['measurement']['label']='other'
        self.assertEqual(condition_slot(raw,body),('source pour pose',None))

    def test_vessel_center_target_places_the_separate_mouth_at_authored_target(self):
        raw=stage();before=deepcopy(raw);c,proof=vessel_condition(raw);self.assertEqual(raw,before)
        self.assertEqual(condition_slot(raw,c),('source pour pose',None))
        model=c['measurement']['models']['wuliangye/00000'];center=np.array(model['local_pose'][:3])
        mouth=np.array(proof['source_mouth_local_pose'][:3]);target=np.array(c['expected']['position'])
        np.testing.assert_allclose(target+_rotation(c['expected']['orientation'])@(mouth-center),[0,0,.08],atol=1e-12)
        self.assertAlmostEqual(target[0],.108);self.assertEqual(c['slot'],'source pour pose')
        bad=stage();bad['recognition']['source_exit']['opening']['models']['wuliangye/00000']['local_pose'][3:]=[0,1,0,0]
        with self.assertRaisesRegex(ValueError,'root axes'):vessel_condition(bad)
