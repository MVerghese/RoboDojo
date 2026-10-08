"""Counterexamples for selecting calibrated mouths/cores on varying assets."""
from copy import deepcopy
import hashlib
from pathlib import Path
from types import SimpleNamespace as NS
import tempfile
import unittest

import numpy as np

from test_atomic_physical_runtime import World
from task.atomic.session import AtomicSession
from task.atomic.spec import AtomicStage, _validate_selector, _validate_condition


class ModelFrameTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)/'asset.usdz'
        self.path.write_bytes(b'test asset identity')
        self.world = World()
        self.metadata = {'model_name': 'mug', 'model_id': 15}
        self.bounds = [[-.05,-.03,-.04],[.05,.03,.04]]
        self.obj = NS(usd_path=str(self.path))
        lm = self.world.env.scene_manager.layout_manager
        lm.get_instance_name = lambda env_idx,label: label
        lm.get_scene_object = lambda env_idx,inst_name: self.obj
        lm.get_instance_metadata = lambda **kw: self.metadata
        lm.instance_type_by_env = [{'object':'rigid'}]
        self.world.env._atomic_surfaces = NS(local_mesh_summary=lambda *args: {'bounds':self.bounds})
        row = {'local_pose':[-.014,0,.0376,1,0,0,0], 'calibration_id':'reviewed mouth',
               'asset_sha256': hashlib.sha256(self.path.read_bytes()).hexdigest(),
               'scaled_bounds_m':deepcopy(self.bounds)}
        self.selector = {'kind':'model_calibrated_frame','label':'object',
                         'models':{'mug/00015':row}}
        stage = AtomicStage.from_dict({'id':'observe','family':'place','instruction':'Observe',
                                      'success_checks':[{'name':'is_test_goal','args':{}}]})
        self.session = AtomicSession(self.world.env,stage,0)

    def test_actual_model_file_scale_and_live_pose_compose_once(self):
        _validate_selector(self.selector,'mouth')
        value,source = self.session._resolve_with_source(self.selector)
        np.testing.assert_allclose(value[:3],[-.014,0,.0376])
        self.assertEqual(source['model_frame_proof']['model'],'mug/00015')
        self.world.poses['object'][:] = [1,2,3,2**-.5,0,0,2**-.5]
        value,_ = self.session._resolve_with_source(self.selector)
        np.testing.assert_allclose(value[:3],[1,2-.014,3+.0376],atol=1e-12)

    def test_wrong_model_changed_asset_and_wrong_scale_fail_closed(self):
        self.metadata['model_id'] = 16
        with self.assertRaisesRegex(RuntimeError,'no reviewed'):
            self.session._resolve(self.selector)
        self.metadata['model_id'] = 15
        self.session._resolve(self.selector)
        self.path.write_bytes(b'different asset bytes')
        with self.assertRaisesRegex(RuntimeError,'asset file'):
            self.session._resolve(self.selector)
        self.path.write_bytes(b'test asset identity')
        self.bounds[1][0] = .1
        with self.assertRaisesRegex(RuntimeError,'scaled material bounds'):
            self.session._resolve(self.selector)

    def test_unknown_rows_zero_quaternion_and_inverted_bounds_are_rejected(self):
        for update in ({'extra':1}, {'local_pose':[0,0,0,0,0,0,0]},
                       {'scaled_bounds_m':[[0,0,0],[-1,1,1]]}):
            selector = deepcopy(self.selector)
            selector['models']['mug/00015'].update(update)
            with self.assertRaises(ValueError):
                _validate_selector(selector,'mouth')

    def test_calibrated_origin_point_has_no_orientation_or_whole_object_extent(self):
        selector=deepcopy(self.selector);selector['kind']='model_calibrated_position'
        _validate_selector(selector,'mouth point')
        value,source=self.session._resolve_with_source(selector)
        np.testing.assert_allclose(value,[-.014,0,.0376]);self.assertEqual(source['kind'],'model_calibrated_position')
        condition={'id':'mouth_region','slot':'spout','kind':'spatial_relation','relation_scope':'points',
            'measurement':selector,'reference':self.selector,'expected':'above','margin':.04,
            'tolerance':.001,'event':{'kind':'attempt_end'}}
        _validate_condition(condition)
        broken=deepcopy(condition);broken['relation_scope']='objects'
        with self.assertRaises(ValueError):_validate_condition(broken)
        broken=deepcopy(condition);broken['measurement']=self.selector
        with self.assertRaises(ValueError):_validate_condition(broken)
        broken={'id':'false_orientation','slot':'spout','kind':'relative_orientation','measurement':selector,
            'reference':self.selector,'expected':[1,0,0,0],'tolerance':.1,'event':{'kind':'attempt_end'}}
        with self.assertRaisesRegex(ValueError,'actual frame'):_validate_condition(broken)


if __name__ == '__main__':
    unittest.main()
