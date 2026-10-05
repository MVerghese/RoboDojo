"""Counterexamples for layout repeats, live link frames and control cycles."""
from copy import deepcopy
from dataclasses import replace
import io
import json
import math
from pathlib import Path
import tarfile
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

import numpy as np
from test_atomic_physical_runtime import World, stage
from task.atomic.spec import AtomicProgram, AtomicStage, AtomicGate
from task.atomic.session import AtomicSession
from task.atomic.sequence import AtomicSequence
from task.atomic.landmarks import live_link_pose, matrix_quaternion
from task.atomic.geometry import _rotation
from scripts.atomic.run_suite import freeze_case, read_frozen_case, submit_frozen_case, overlay_runtime_hash


def button_stage():
    return AtomicStage.from_dict({'id':'press', 'family':'actuate', 'instruction':'press and release',
        'success_checks':[{'name':'is_atomic_interaction', 'args':{}}], 'recognition':{
            'kind':'button_press_cycle', 'label':'object', 'arm':'any', 'min_contact_steps':2,
            'joint_tag':'press', 'initial_ratio':.95, 'pressed_ratio':.5, 'released_ratio':.9}})


def button_world():
    w=World()
    lm=w.env.scene_manager.layout_manager
    lm.get_instance_metadata=lambda **kwargs: {'passive':{'functional':{'press':{'parent_joint':['spring']}}}}
    w.env._atomic_joint_state=lambda *args: ({'position':w.joint, 'lower':0., 'upper':1.}, '/env/object/moving')
    return w


class DynamicTests(unittest.TestCase):
    def test_press_requires_contacted_travel_and_complete_release(self):
        w=button_world(); s=AtomicSession(w.env,button_stage(),0)
        w.joint=1.; w.tick(s); w.joint=.1; self.assertFalse(w.tick(s,3))
        w.hold(fingers=1); self.assertFalse(w.tick(s,3)) # Already pressed can't be borrowed.
        w.joint=1.; w.tick(s); w.joint=.2; self.assertFalse(w.tick(s,2))
        self.assertIn('press',s._physical_recognizer.events)
        self.assertFalse(w.tick(s,5)) # Keeping it held down cannot complete a cycle.
        w.joint=1.; self.assertFalse(w.tick(s,2)) # Full travel with finger still present.
        w.release(); self.assertTrue(w.tick(s))
        self.assertEqual(set(s.summary()['physical_events']),{'press','release','cycle'})

    def test_contact_on_fixed_body_and_contact_gap_cannot_press(self):
        w=button_world(); s=AtomicSession(w.env,button_stage(),0)
        w.hold(fingers=1); w.joint=1.; w.tick(s)
        w.contacts.contact_body='/env/object/fixed'; w.joint=.1; self.assertFalse(w.tick(s,3))
        w.contacts.contact_body='/env/object/moving'; self.assertFalse(w.tick(s,2))
        w.release(); w.joint=1.; self.assertFalse(w.tick(s))

    def test_lowercase_layout_categories_match_live_contract(self):
        for kind, category in [('supported_release','rigid'),('contact_joint_motion','articulation')]:
            w=World(); lm=w.env.scene_manager.layout_manager
            lm.instance_type_by_env=[{'obj':category}]; lm.get_instance_name=lambda **kw:'obj'
            AtomicSession(w.env,stage(kind),0)
            lm.instance_type_by_env=[{'obj':'garment'}]
            with self.assertRaises(RuntimeError): AtomicSession(w.env,stage(kind),0)

    def test_model_ids_expand_counts_and_rewrite_dependencies(self):
        a,b=replace(button_stage(),id='red'),replace(button_stage(),id='confirm')
        program=AtomicProgram('press_by_number',(a,b),repeat_counts={'red':{'label':'num0','min':1,'max':9}})
        w=button_world(); w.env.scene_manager.layout_manager.get_instance_metadata=lambda **kw:{'model_id':'3'}
        bound=program.bind(w.env,0)
        self.assertEqual([s.id for s in bound.stages],['red__1','red__2','red__3','confirm'])
        self.assertEqual(bound.dependencies()['confirm'],['red__3'])
        self.assertEqual(bound.binding_evidence['red']['count'],3)
        w.env.scene_manager.layout_manager.get_instance_metadata=lambda **kw:{'model_id':10}
        with self.assertRaises(ValueError): program.bind(w.env,0)
        w.env.scene_manager.layout_manager.get_instance_metadata=lambda **kw:{'model_id':True}
        with self.assertRaises(ValueError): program.bind(w.env,0)

    def test_expanded_ids_cannot_collide(self):
        a,b=replace(button_stage(),id='red'),replace(button_stage(),id='red__1')
        program=AtomicProgram('t',(a,b),repeat_counts={'red':{'label':'num0','min':1,'max':9}})
        w=button_world(); w.env.scene_manager.layout_manager.get_instance_metadata=lambda **kw:{'model_id':1}
        with self.assertRaises(ValueError): program.bind(w.env,0)

    def test_scene_gates_are_not_reported_as_robot_actions(self):
        w=World(); w.goal=False
        gate=AtomicGate.from_dict({'id':'ready','checks':[{'name':'is_test_goal','args':{}}]})
        action=stage('held_tool_push')
        program=AtomicProgram('t',(action,),stage_dependencies={'action':['ready'],'ready':[]},gates=(gate,))
        seq=AtomicSequence(w.env,program,0)
        seq.observe_events(); self.assertFalse(seq.sessions)
        w.goal=True; w.contacts.steps+=1; seq.observe_events()
        self.assertIn('action',seq.sessions)
        summary=seq.summary(); self.assertEqual(len(summary['stages']),1)
        self.assertTrue(summary['gates'][0]['observed'])
        self.assertFalse(summary['stage_boundaries']['action']['prefix_replay_supported'])
        with self.assertRaises(ValueError):
            AtomicGate.from_dict({'id':'g','checks':[{'name':'is_joint_position_change','args':{}}]})

    def test_rise_gate_uses_its_activation_baseline_not_native_history(self):
        w=World(); w.poses['object'][2]=.2
        gate=AtomicGate.from_dict({'id':'raised','checks':[{'name':'is_atomic_rise_since_activation',
            'args':{'label':'object','threshold_m':.025}}]})
        action=stage('held_tool_push')
        seq=AtomicSequence(w.env,AtomicProgram('t',(action,),
            stage_dependencies={'action':['raised'],'raised':[]},gates=(gate,)),0)
        seq.observe_events(); self.assertFalse(seq.sessions)
        w.poses['object'][2]=.226; w.contacts.steps+=1; seq.observe_events()
        self.assertIn('action',seq.sessions)

    def test_physx_link_pose_uses_xyzw_and_environment_origin(self):
        physics=NS(get_link_transforms=lambda:np.array([[[11.,22.,33.,0.,0.,math.sqrt(.5),math.sqrt(.5)]]]))
        obj=NS(_articulation_view=NS(_physics_view=physics,body_names=['cap']))
        lm=NS(get_instance_name=lambda **kw:'obj',get_scene_object=lambda **kw:obj)
        env=NS(scene_manager=NS(layout_manager=lm),sim=NS(scene=NS(env_origins=np.array([[10.,20.,30.]]))))
        pose,source=live_link_pose(env,'button','cap',0)
        np.testing.assert_allclose(pose[:3],[1,2,3])
        np.testing.assert_allclose(_rotation(pose[3:])@[1,0,0],[0,1,0],atol=1e-8)
        self.assertIn('PhysX',source['backend'])
        obj._articulation_view._physics_view=None
        with self.assertRaises(RuntimeError):live_link_pose(env,'button','cap',0)

    def test_quaternion_matrix_conversion_at_pi(self):
        for q in ([1,0,0,0],[0,1,0,0],[0,0,1,0],[.5,.5,.5,.5]):
            rotation=_rotation(q)
            np.testing.assert_allclose(_rotation(matrix_quaternion(rotation)),rotation,atol=1e-8)

    def test_articulated_functional_and_support_frames_move_with_live_link(self):
        w=World(); lm=w.env.scene_manager.layout_manager
        lm.get_instance_name=lambda **kw:'obj'
        lm.get_instance_metadata=lambda **kw:{'passive':{'functional':{'press':{'base_link':'cap','frame':[[.1,0,0,1,0,0,0]]}},
                                                        'support':{'top':{'base_link':'cap','center':[[.1,0,0,1,0,0,0]]}}}}
        s=AtomicSession(w.env,stage('contact_joint_motion'),0)
        link=np.array([1,2,3,math.sqrt(.5),0,0,math.sqrt(.5)])
        with patch('task.atomic.landmarks.live_link_pose',return_value=(link,{'backend':'live PhysX'})):
            for kind,tag in [('functional_point','press'),('support_point','top')]:
                pose,source=s._resolve_with_source({'kind':kind,'label':'object','type':'passive','tag':tag})
                np.testing.assert_allclose(pose[:3],[1,2.1,3],atol=1e-8)
                self.assertEqual(source['live_link']['backend'],'live PhysX')

    def test_landmark_contact_rejects_wrong_part_and_accepts_tip_contact(self):
        w=World(); w.poses['target'][:3]=[0,0,0]
        original=stage('held_tool_contact'); c=dict(original.recognition)
        c.pop('tool_contact_suffix'); c.pop('target_contact_suffix')
        c.update(kind='held_tool_landmark_contact',tool_point={'kind':'object_pose','label':'object'},
                 target_point={'kind':'object_pose','label':'target'},tool_radius_m=.02,target_radius_m=.02)
        s=AtomicSession(w.env,replace(original,recognition=c),0)
        w.hold(); w.tick(s,2)
        old=w.contacts.resolve_object_pair
        def pair(sel,idx):
            _,source=old(sel,idx)
            return {'points':[point]},source
        point=[.1,0,0]; w.contacts.resolve_object_pair=pair; w.contacts.pairs=True
        self.assertFalse(w.tick(s)) # Handle/neighbor key contact outside landmarks.
        w.contacts.pairs=False; w.tick(s); point=[.01,0,0]; w.contacts.pairs=True
        self.assertTrue(w.tick(s))
        self.assertEqual(s.summary()['interaction_evidence']['contact_points'],[[.01,0,0]])

    def test_frozen_case_cannot_rebuild_from_changed_workspace_or_inputs(self):
        with tempfile.TemporaryDirectory() as temp:
            run=Path(temp); program=run/'input.json'; program.write_text('{}')
            (run/'run_plan.json').write_text(json.dumps({'jobs':['j']}))
            (run/'j.atomic-job-spec.json').write_text(json.dumps({'spec':{'queue_config':{
                'priority_class':'high-8000', 'can_preempt':False},
                'affinity':{'allowed_nodes_in_node_group':['bad','good'], 'reservation':'reserved'}}}))
            (run/'code.tar.gz').write_bytes(b'fixed source bundle')
            def archive(runtime, inp):
                with tarfile.open(run/'robodojo-overlay.tar.gz','w:gz') as tar:
                    for name,data in [('task/atomic/session.py',runtime),('task/atomic/inputs/program.json',inp)]:
                        item=tarfile.TarInfo(name); item.size=len(data); tar.addfile(item,io.BytesIO(data))
            archive(b'fixed runtime',b'{}')
            frozen=freeze_case(run,program,'t')
            self.assertEqual(read_frozen_case(run,program,'t'),frozen)
            (run/'run_plan.json').write_text(json.dumps({'jobs':['j'], 'checkpoint':'changed'}))
            with self.assertRaisesRegex(ValueError, 'controls changed'):read_frozen_case(run,program,'t')
            (run/'run_plan.json').write_text(json.dumps({'jobs':['j']}))
            with patch('scripts.atomic.submit_trace.submit_prepared',return_value='job') as submit:
                self.assertEqual(submit_frozen_case(run,program,'t',Path('credentials')),'job')
                self.assertEqual(submit.call_args.args[3],frozen['overlay_sha256'])
                self.assertEqual(submit_frozen_case(run,program,'t',Path('credentials'),priority_class='high-9000',excluded_nodes=['bad']),'job')
                amended=submit.call_args.args[1]
                self.assertEqual(amended['spec']['queue_config'],{'priority_class':'high-9000','can_preempt':False})
                self.assertEqual(amended['spec']['affinity'],{'allowed_nodes_in_node_group':['good'], 'reservation':'reserved'})
                self.assertEqual(read_frozen_case(run,program,'t'),frozen)
                self.assertEqual(json.loads((run/'j.atomic-job-spec.json').read_text())['spec']['queue_config']['priority_class'],'high-8000')
                self.assertEqual(json.loads((run/'run_plan.json').read_text())['scheduling']['priority_class'],'high-9000')
                self.assertEqual(json.loads((run/'run_plan.json').read_text())['scheduling']['excluded_nodes'],['bad'])
                self.assertEqual(json.loads((run/'j.atomic-job-spec.json').read_text())['spec']['affinity']['allowed_nodes_in_node_group'],['bad','good'])
                submit.reset_mock()
                with self.assertRaisesRegex(ValueError,'every prepared eligible node'):
                    submit_frozen_case(run,program,'t',Path('credentials'),excluded_nodes=['bad','good'])
                submit.assert_not_called()
            archive(b'fixed runtime',b'{"different":1}')
            self.assertEqual(overlay_runtime_hash(run/'robodojo-overlay.tar.gz'),frozen['runtime_sha256'])
            with self.assertRaises(ValueError):read_frozen_case(run,program,'t')
