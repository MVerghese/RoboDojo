"""Counterexamples for temporal rigid recognizers and concurrent scheduling."""
from copy import deepcopy
import ast
import math
from pathlib import Path
from types import SimpleNamespace
import tempfile
import json
import unittest

import numpy as np

from task.atomic.contacts import ContactUnavailable
from task.atomic.session import AtomicSession
from task.atomic.sequence import AtomicSequence
from task.atomic.spec import AtomicStage, AtomicProgram, AtomicTrace
from task.atomic.replay import replay_prefix


class Contacts:
    def __init__(self):
        self.steps = 0
        self.errors = []
        self.holds = {}
        self.pairs = False
        self.support = True
        self.impulse = .01
        self.target_suffix = 'key0'
        self.contact_body = '/env/object/moving'

    def resolve(self, selector, env_idx):
        label, requested = selector['label'], selector.get('arm', 'any')
        arms = sorted(a for (l, a), fingers in self.holds.items()
                      if l == label and requested in ('any', a) and fingers >= selector.get('min_finger_bodies', 1))
        if not arms or selector.get('body_path', self.contact_body) != self.contact_body:
            raise ContactUnavailable('missing eligible fingers')
        return {'position': [0, 0, 0]}, {'resolved_arm': arms[0], 'physics_step': self.steps,
                                        'contacts': [], 'finger_bodies': ['f0', 'f1']}

    def resolve_object_pair(self, selector, env_idx):
        if not self.pairs:
            raise ContactUnavailable('no tool/target contact')
        roots = ['/env/' + selector['label'], '/env/' + selector['other_label']]
        return {}, {'object_roots': roots, 'contacts': [
            {'actor0': roots[0], 'actor1': roots[1], 'collider0': roots[0] + '/tip',
             'collider1': roots[1] + '/' + self.target_suffix, 'impulse': [0, 0, self.impulse]}]}

    def support_evidence(self, label, supports, env_idx):
        return {'contacts': [{'support_label': supports[0]}] if self.support else []}


class World:
    def __init__(self):
        self.poses = {l: np.array([0., 0., 0., 1., 0., 0., 0.]) for l in ('object', 'target', 'other')}
        self.contacts = Contacts()
        self.joint = 0.
        self.goal = True
        lm = SimpleNamespace(get_instance_pose=lambda env_idx, label: (
            self.poses[label][:3].copy(), self.poses[label][3:].copy()))
        self.env = SimpleNamespace(scene_manager=SimpleNamespace(layout_manager=lm),
            _atomic_contacts=self.contacts, take_action_cnt=[0],
            reward_manager=SimpleNamespace(call_func_parser=lambda check, env_idx: float(self.goal)),
            _atomic_joint_state=lambda label, joint, env_idx: ({'position': self.joint}, '/env/object/moving'))

    def hold(self, arm='left', fingers=2, label='object'):
        self.contacts.holds[(label, arm)] = fingers

    def release(self, arm='left', label='object'):
        self.contacts.holds.pop((label, arm), None)

    def tick(self, session, n=1):
        for _ in range(n):
            self.contacts.steps += 1
            session.observe_events()
        return session.step()


def recognition(kind):
    c = {'kind': kind, 'label': 'object', 'arm': 'any', 'min_contact_steps': 2}
    if kind == 'supported_release':
        c.update(transport_threshold_m=.01, support_labels=['@table'], settle_steps=3,
                 max_position_step_m=.001, max_angle_step_rad=.02,
                 max_settle_displacement_m=.001, max_settle_angle_rad=.02)
    elif kind == 'held_tool_push':
        c.update(target_label='target', support_labels=['@table'], motion_threshold_m=.02,
                 tool_motion_threshold_m=.01, max_vertical_motion_m=.007)
    elif kind == 'held_tool_contact':
        c.update(target_label='target', min_impulse_ns=.005,
                 tool_contact_suffix='tip', target_contact_suffix='key0')
    elif kind == 'grip_transfer':
        del c['arm']
        c.update(giver_arm='left', receiver_arm='right', overlap_steps=2,
                 receiver_steps=2, max_position_step_m=.01)
    elif kind == 'held_insertion':
        c.update(target_label='target', tip={'kind': 'object_pose', 'label': 'object'},
                 opening={'kind': 'object_pose', 'label': 'target'}, entry_clearance_m=.002,
                 min_depth_m=.005, max_depth_m=.02, lateral_tolerance_m=.003, axis_tolerance_rad=.1)
    elif kind == 'contact_joint_motion':
        c.update(joint_name='button_joint', min_travel=.005, direction=-1)
    elif kind == 'contact_constrained_twist':
        c.update(target_label='target', pivot={'kind': 'object_pose', 'label': 'target'},
                 axis=[0, 0, 1], direction=1, min_angle_rad=2*math.pi,
                 max_off_axis_rad=.05, max_radius_m=.003, min_depth_m=.005, max_depth_m=.02)
    elif kind == 'rigid_material_transfer':
        c.update(target_label='target', source_frame={'kind':'object_pose','label':'object'},
                 target_frame={'kind':'object_pose','label':'target'},
                 source_half_extents_m=[.1,.1,.1], target_half_extents_m=[.1,.1,.1],
                 material_labels=['other'], required_count=1, min_tilt_rad=.3, settle_steps=2)
    return c


def stage(kind, ident='action', label=None):
    family = {'supported_release': 'place', 'held_tool_push': 'push_with_tool',
              'held_tool_contact': 'touch_with_tool', 'grip_transfer': 'handover',
              'held_insertion': 'insert', 'contact_joint_motion': 'actuate',
              'contact_constrained_twist': 'twist', 'rigid_material_transfer': 'pour'}[kind]
    c = recognition(kind)
    if label:
        c['label'] = label
    return AtomicStage.from_dict({'id': ident, 'family': family, 'instruction': ident,
        'recognition': c, 'success_checks': [{'name': 'is_test_goal', 'args': {}}], 'geometry': []})


class PhysicalTests(unittest.TestCase):
    def test_place_needs_transport_then_release_then_supported_stability(self):
        w = World(); s = AtomicSession(w.env, stage('supported_release'), 0)
        self.assertFalse(w.tick(s, 5))  # Object already resting on target isn't placement.
        w.hold(); self.assertFalse(w.tick(s, 2))
        w.poses['object'][0] = .02
        self.assertFalse(w.tick(s))
        w.release(); w.contacts.support = False
        self.assertFalse(w.tick(s, 4))  # Released in midair.
        w.contacts.support = True
        self.assertFalse(w.tick(s))
        w.poses['object'][0] += .02
        self.assertFalse(w.tick(s))  # Drift resets settling window.
        self.assertFalse(w.tick(s))
        self.assertTrue(w.tick(s))
        self.assertEqual(s.summary()['interaction_evidence']['stable_steps'], 3)

    def test_gradual_jaw_release_preserves_verified_transport_but_is_not_yet_release(self):
        w = World(); s = AtomicSession(w.env, stage('supported_release'), 0)
        w.hold(); w.tick(s, 2); w.poses['object'][0] = .03; w.tick(s)
        w.hold(fingers=1)
        self.assertFalse(w.tick(s, 5))
        self.assertNotIn('release', s.summary()['physical_events'])
        w.release(); self.assertTrue(w.tick(s, 3))
        self.assertIn('release', s.summary()['physical_events'])

    def test_one_finger_cannot_establish_transport_and_late_goal_cannot_reuse_release(self):
        w = World(); s = AtomicSession(w.env, stage('supported_release'), 0)
        w.hold(fingers=1); w.tick(s, 2); w.poses['object'][0] = .03; w.tick(s)
        w.release(); self.assertFalse(w.tick(s, 5))
        w.hold(); w.tick(s, 2); w.poses['object'][0] += .03; w.tick(s)
        w.release(); w.goal = False
        self.assertFalse(w.tick(s, 3))
        self.assertTrue(s.interaction_observed)
        w.contacts.support = False; w.goal = True
        self.assertFalse(w.tick(s))  # Historical physical event cannot rescue a later unrelated goal.

    def test_small_per_step_drift_cannot_accumulate_through_a_settling_window(self):
        w = World(); original = stage('supported_release')
        c = {**original.recognition, 'settle_steps': 10}
        s = AtomicSession(w.env, AtomicStage.from_dict({'id':'place','family':'place','instruction':'place',
            'success_checks':list(original.success_checks),'recognition':c}), 0)
        w.hold(); w.tick(s); w.poses['object'][0]=.02; w.tick(s); w.release()
        for _ in range(30):
            w.poses['object'][0] += .0005
            self.assertFalse(w.tick(s))
        self.assertTrue(w.tick(s, 10))

    def test_tool_push_requires_held_tool_pair_support_and_new_coupled_motion(self):
        w = World(); s = AtomicSession(w.env, stage('held_tool_push'), 0)
        w.contacts.pairs = True; w.poses['target'][0] = .1
        self.assertFalse(w.tick(s, 3))  # Tool collision without held tool.
        w.hold(); w.contacts.pairs = False
        self.assertFalse(w.tick(s, 2))
        w.poses['object'][0] = .1; w.poses['target'][0] = .2
        w.contacts.pairs = True
        self.assertFalse(w.tick(s, 2))  # Earlier displacement cannot be borrowed.
        w.poses['object'][0] += .03; w.poses['target'][0] += .03
        w.contacts.support = False
        self.assertFalse(w.tick(s))
        w.contacts.support = True; w.tick(s, 2)
        w.poses['object'][0] += .03; w.poses['target'][0] += .03
        self.assertTrue(w.tick(s))

    def test_tool_touch_needs_a_new_force_bearing_encounter_on_declared_parts(self):
        w = World(); s = AtomicSession(w.env, stage('held_tool_contact'), 0)
        w.hold(); w.tick(s, 2)
        w.contacts.pairs = True; w.contacts.target_suffix = 'key1'
        self.assertFalse(w.tick(s))  # Wrong key cannot satisfy key0 event.
        w.contacts.target_suffix = 'key0'
        self.assertFalse(w.tick(s))  # Resting contact isn't a new encounter.
        w.contacts.pairs = False; w.tick(s)
        w.contacts.pairs = True; w.contacts.impulse = .0001
        self.assertFalse(w.tick(s))
        w.contacts.pairs = False; w.tick(s)
        w.contacts.pairs = True; w.contacts.impulse = .01
        self.assertTrue(w.tick(s))

    def test_handover_needs_giver_only_overlap_release_and_receiver_retention(self):
        w = World(); s = AtomicSession(w.env, stage('grip_transfer'), 0)
        w.hold('left'); w.hold('right')
        self.assertFalse(w.tick(s, 5))  # Simultaneous initial holds do not establish transfer provenance.
        w.release('right'); self.assertFalse(w.tick(s, 2))
        w.hold('right'); self.assertFalse(w.tick(s, 3))
        self.assertFalse(w.tick(s, 2))  # Both arms holding isn't transfer completion.
        w.release('left'); self.assertFalse(w.tick(s)); self.assertTrue(w.tick(s))
        self.assertEqual(s.interaction_evidence['receiver_only_steps'], 2)

    def test_insertion_small_inside_retreat_preserves_verified_outside_entry(self):
        w=World();w.poses['object'][2]=.02;w.hold()
        s=AtomicSession(w.env,stage('held_insertion'),0)
        w.tick(s,2)
        w.poses['object'][2]=-.006;w.contacts.pairs=False;w.tick(s)
        w.poses['object'][2]=-.0055;w.contacts.pairs=True
        self.assertTrue(w.tick(s))
        self.assertTrue(s.summary()['interaction_observed'])

    def test_insertion_rejects_already_inside_and_misaligned_entry(self):
        w = World(); w.poses['object'][2] = -.01
        s = AtomicSession(w.env, stage('held_insertion'), 0)
        w.hold(); w.contacts.pairs = True
        self.assertFalse(w.tick(s, 4))  # Catching an already-inserted object.
        w.poses['object'][2] = .01; w.tick(s)
        w.poses['object'][:3] = [.02, 0, -.01]
        self.assertFalse(w.tick(s))
        w.poses['object'][0] = 0
        self.assertFalse(w.tick(s))  # Alignment after crossing isn't insertion.
        w.poses['object'][2] = .01; w.tick(s)
        w.poses['object'][2] = -.01
        self.assertTrue(w.tick(s))
        self.assertAlmostEqual(s.interaction_evidence['depth_m'], .01)

    def test_actuation_requires_correct_moving_body_contact_and_direction(self):
        w = World(); s = AtomicSession(w.env, stage('contact_joint_motion'), 0)
        w.hold(fingers=1); w.contacts.contact_body = '/env/object/base'
        w.joint = -.02
        self.assertFalse(w.tick(s, 3))  # Root/base contact can't explain moving-joint travel.
        w.contacts.contact_body = '/env/object/moving'; w.tick(s, 2)
        w.joint += .02
        self.assertFalse(w.tick(s))  # Wrong direction.
        w.joint -= .03
        self.assertTrue(w.tick(s))

    def test_two_sample_actuation_and_placement_keep_the_first_contact_anchor(self):
        w = World(); s = AtomicSession(w.env, stage('contact_joint_motion'), 0)
        w.hold(fingers=1); self.assertFalse(w.tick(s))
        w.joint = -.01
        self.assertTrue(w.tick(s))  # Full motion during the two valid contact samples.
        w = World(); s = AtomicSession(w.env, stage('supported_release'), 0)
        w.hold(); self.assertFalse(w.tick(s))
        w.poses['object'][0] = .02; self.assertFalse(w.tick(s))
        w.release(); self.assertTrue(w.tick(s, 3))

    def test_actual_eval_physics_callback_latches_brief_tool_contact(self):
        # Exercise the actual evaluator method without importing Isaac Sim.
        path = Path(__file__).resolve().parents[1]/'src/eval_client/eval_env.py'
        tree = ast.parse(path.read_text())
        callback = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                        and n.name == '_observe_atomic_physics')
        namespace = {}
        exec(compile(ast.Module(body=[callback], type_ignores=[]), str(path), 'exec'), namespace)
        w = World(); s = AtomicSession(w.env, stage('held_tool_contact'), 0)
        w.env._atomic_replaying=False; w.env._atomic_stepping_envs=[0]; w.env.end_flag=[False]
        w.env.atomic_stage=s.stage; w.env._atomic_sessions={0:s}; w.env._atomic_sequences={}
        w.hold()
        for _ in range(2):
            w.contacts.steps += 1; namespace['_observe_atomic_physics'](w.env)
        w.contacts.pairs=True
        w.contacts.steps += 1; namespace['_observe_atomic_physics'](w.env)
        w.contacts.pairs=False
        w.contacts.steps += 1; namespace['_observe_atomic_physics'](w.env)
        self.assertFalse(s._physical_recognizer.ready)
        self.assertTrue(s.step())  # Success survives disappearance before the action boundary.

    def test_twist_unwraps_full_turn_and_cannot_borrow_rotation_before_contact(self):
        w = World(); w.poses['object'][2] = -.01
        s = AtomicSession(w.env, stage('contact_constrained_twist'), 0)
        w.hold(); w.contacts.pairs = False; w.tick(s, 3)
        w.contacts.pairs = True; w.tick(s)
        for angle in np.linspace(.1, 2*math.pi+.1, 65):
            w.poses['object'][3:] = [math.cos(angle/2), 0, 0, math.sin(angle/2)]
            w.tick(s)
        self.assertTrue(s.success)
        self.assertGreaterEqual(s.interaction_evidence['signed_angle_rad'], 2*math.pi)
        # Identical endpoint quaternion without an observed turn is insufficient.
        s2 = AtomicSession(w.env, stage('contact_constrained_twist'), 0)
        self.assertFalse(w.tick(s2, 4))

    def test_duplicate_callbacks_backend_error_and_skipped_step_fail_closed(self):
        w = World(); s = AtomicSession(w.env, stage('contact_joint_motion'), 0)
        w.hold(fingers=1); w.tick(s)
        for _ in range(5):
            self.assertFalse(s.step())
        w.contacts.steps += 5; w.joint = -.03
        s.observe_events(); self.assertFalse(s.step())
        w.contacts.errors = ['broken callback']
        w.contacts.steps += 1
        with self.assertRaisesRegex(RuntimeError, 'reporting failed'):
            s.observe_events()

    def test_schema_rejects_unknown_ignored_fields_bad_limits_and_wrong_landmarks(self):
        for kind in ('supported_release', 'held_tool_push', 'held_tool_contact', 'grip_transfer',
                     'held_insertion', 'contact_joint_motion', 'contact_constrained_twist', 'rigid_material_transfer'):
            original = stage(kind)
            variants = [{'ignored_field': 1}, {'min_contact_steps': True}, {'min_contact_steps': 1}]
            for change in variants:
                data = {'id': 'x', 'family': original.family, 'instruction': 'x',
                        'success_checks': list(original.success_checks), 'recognition': {**original.recognition, **change}}
                with self.subTest(kind=kind, change=change), self.assertRaises(ValueError):
                    AtomicStage.from_dict(data)
            varied = original.with_variant({'stage_id': original.id, 'conditions': {}})
            self.assertEqual(varied.recognition, original.recognition)
        with self.assertRaises(ValueError):
            c = recognition('held_insertion'); c['opening']['label'] = 'other'
            AtomicStage.from_dict({'id': 'x', 'family': 'insert', 'instruction': 'x',
                'success_checks': [{'name': 'is_test', 'args': {}}], 'recognition': c})

    def material_world(self):
        w = World()
        w.poses['target'][0] = 1
        offsets = np.array([[x,y,z] for x in (-.01,.01) for y in (-.01,.01) for z in (-.01,.01)])
        w.env._atomic_surfaces = SimpleNamespace(resolve=lambda label, env_idx, pose:
            {'vertices': (offsets + pose[:3]).tolist()})
        return w

    def test_material_transfer_has_whole_object_containment_exit_provenance_and_raw_counts(self):
        w = self.material_world(); s = AtomicSession(w.env, stage('rigid_material_transfer'), 0)
        w.hold(); w.tick(s, 2)
        w.poses['object'][3:] = [math.cos(.3), math.sin(.3), 0, 0]
        w.poses['other'][0] = .5
        self.assertFalse(w.tick(s))
        self.assertEqual(s.summary()['physical_metrics']['outside_both'], 1)
        w.release()  # Source may be released after material exits it.
        w.poses['other'][0] = 1.095
        self.assertFalse(w.tick(s, 3))  # Centre in box, whole ball protrudes.
        w.poses['other'][0] = 1
        self.assertFalse(w.tick(s)); self.assertTrue(w.tick(s))
        evidence = s.interaction_evidence
        self.assertEqual(evidence['counts']['transferred'], 1)
        self.assertEqual(evidence['counts']['in_source'], 0)
        self.assertTrue(evidence['materials']['other']['exited_while_held_and_tilted'])

    def test_preexisting_target_and_later_source_grasp_cannot_borrow_transfer(self):
        w = self.material_world(); w.poses['other'][0] = 1
        s = AtomicSession(w.env, stage('rigid_material_transfer'), 0)
        w.hold(); self.assertFalse(w.tick(s, 4))
        self.assertEqual(s.summary()['physical_metrics']['initially_eligible'], 0)
        w = self.material_world(); s = AtomicSession(w.env, stage('rigid_material_transfer'), 0)
        w.poses['other'][0] = .5; w.tick(s)
        w.hold(); w.poses['object'][3:] = [math.cos(.3), math.sin(.3), 0, 0]
        w.tick(s, 3); w.poses['other'][0] = 1
        self.assertFalse(w.tick(s, 4))  # Exit occurred before held/tilted evidence.

    def test_release_geometry_is_sampled_before_final_settled_pose(self):
        w = World()
        original = stage('supported_release')
        condition = {'id':'release','slot':'release_point','kind':'point','expected':[.03,0,0],
            'tolerance':.0001,'measurement':{'kind':'object_position','label':'object'},
            'event':{'kind':'recognition_event','name':'release'},'track_closest':False}
        s = AtomicSession(w.env, AtomicStage.from_dict({'id':'place','family':'place','instruction':'place',
            'success_checks':list(original.success_checks),'recognition':original.recognition,'geometry':[condition]}), 0)
        w.hold(); w.tick(s, 2); w.poses['object'][0] = .03; w.tick(s)
        w.release(); w.tick(s)
        w.poses['object'][0] = .031; w.tick(s, 3)
        self.assertEqual(s.results['release']['measured_state'], [.03,0,0])
        self.assertTrue(s.results['release']['result']['passed'])
        self.assertFalse(s.results['release']['ee_contact_proxy'])
        with self.assertRaisesRegex(ValueError, 'transition emitted'):
            s.stage.with_variant({'stage_id': 'place', 'conditions': {
                'release': {'event': {'kind': 'recognition_event', 'name': 'not_a_release'}}}})

    def test_maintained_other_arm_hold_cannot_be_restored_after_violation(self):
        w = World(); original = stage('held_tool_push')
        s = AtomicSession(w.env, AtomicStage.from_dict({'id':'push','family':original.family,'instruction':'push',
            'success_checks':list(original.success_checks),'recognition':original.recognition,
            'maintained_holds':[{'label':'other','arm':'right','min_finger_bodies':2}]}), 0)
        w.hold(); w.hold('right',label='other'); w.contacts.pairs=True; w.tick(s, 3)
        w.release('right',label='other'); w.tick(s)
        w.hold('right',label='other')
        w.poses['object'][0]=.03; w.poses['target'][0]=.03
        self.assertFalse(w.tick(s))
        self.assertTrue(s.interaction_observed)
        self.assertEqual(len(s.summary()['maintained_hold_failures']),1)

    def test_stateful_native_predicates_are_forbidden_without_update_flag(self):
        for name in ('is_joint_position_change','is_joint_position_ratio_change_from_above_to_below',
                     'is_functional_point_moved','is_functional_point_not_moved'):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError,'stateful'):
                AtomicStage.from_dict({'id':'x','family':'actuate','instruction':'x',
                    'success_checks':[{'name':name,'args':{}}]})

    def test_checked_in_programs_load_and_new_programs_preserve_label_bindings(self):
        root = Path(__file__).resolve().parents[1]
        for path in (root/'task/atomic/programs').glob('*.json'):
            with self.subTest(path=path.name):
                AtomicProgram.load(path)
        p = AtomicProgram.load(root/'task/atomic/programs/stack_blocks_by_language.json')
        self.assertEqual(p.dependencies()['place_block_2'], ['pick_block_2','place_block_1'])
        self.assertEqual(p.stage('place_block_1').recognition['support_labels'], ['block_0'])

    def test_rigid_material_cannot_use_cached_cloth_or_fluid_geometry(self):
        for category in ('Garment','Fluid','Articulation'):
            w = self.material_world()
            lm = w.env.scene_manager.layout_manager
            lm.get_instance_name = lambda env_idx, label: label
            lm.instance_type_by_env = [{'object':'Rigid','target':'Geometry','other':category}]
            with self.subTest(category=category), self.assertRaisesRegex(RuntimeError,'cannot use fluid/cloth'):
                AtomicSession(w.env, stage('rigid_material_transfer'), 0)


class GraphTests(unittest.TestCase):
    def test_independent_actions_overlap_and_successors_start_inside_chunk(self):
        w = World()
        first = stage('contact_joint_motion', 'first')
        other = stage('contact_joint_motion', 'other')
        later = stage('contact_joint_motion', 'later')
        p = AtomicProgram('test', (first, other, later), stage_dependencies={
            'first': [], 'other': [], 'later': ['first']})
        seq = AtomicSequence(w.env, p, 0)
        self.assertEqual(set(seq.sessions), {'first', 'other'})
        w.hold(fingers=1)
        w.env.take_action_cnt[0] = 1
        for _ in range(2):
            w.contacts.steps += 1; seq.observe_events()
        w.joint = -.01; w.contacts.steps += 1; seq.observe_events()
        self.assertEqual(set(seq.completed), {'first', 'other'})
        self.assertEqual(set(seq.sessions), {'later'})
        self.assertNotIn('later', seq.stage_starts)
        self.assertFalse(seq.stage_boundaries['later']['prefix_replay_supported'])
        # Next stage cannot borrow the previous stroke in the same action chunk.
        for _ in range(2):
            w.contacts.steps += 1; seq.observe_events()
        self.assertNotIn('later', seq.completed)
        w.joint -= .01; w.contacts.steps += 1; seq.observe_events()
        self.assertEqual(len(seq.completed), 3)
        self.assertEqual(seq.summary()['active_stages'], [])
        self.assertEqual({r['end_action'] for r in seq.summary()['stages']}, {1})

    def test_cycle_missing_stage_and_non_linear_prefix_replay_rejected(self):
        a, b = stage('contact_joint_motion', 'a'), stage('contact_joint_motion', 'b')
        for deps in ({'a': ['b'], 'b': ['a']}, {'a': []}, {'a': [], 'b': ['missing']}):
            with self.subTest(deps=deps), self.assertRaises(ValueError):
                AtomicProgram('test', (a, b), stage_dependencies=deps)
        p = AtomicProgram('test', (a, b), stage_dependencies={'a': [], 'b': []})
        trace = AtomicTrace('test', 0, (), {'a': 0, 'b': 0})
        with self.assertRaisesRegex(ValueError, 'requires a linear program'):
            replay_prefix(p, b, trace, lambda _: None, lambda _: True)


if __name__ == '__main__':
    unittest.main()
