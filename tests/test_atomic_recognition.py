"""Physical recognition must survive geometry changes and reject delayed touch."""
from copy import deepcopy
from types import SimpleNamespace
import unittest

import numpy as np

from task.atomic.contacts import ContactUnavailable, PhysXContacts
from task.atomic.geometry import evaluate_geometry
from task.atomic.session import AtomicSession
from task.atomic.spec import AtomicStage


def config(geometry=(), family='pick'):
    value = {'id': 'test', 'family': family, 'instruction': 'Move the object.',
            'recognition': {'kind': 'finger_contact_motion', 'label': 'object', 'arm': 'any',
                            'motion_threshold_m': .025, 'min_contact_steps': 2},
            'success_checks': [{'name': 'is_lift', 'args': {'label': 'object', 'z_threshold': .1}}],
            'geometry': list(geometry)}
    if family == 'push':
        value['recognition']['support_labels'] = ['@table']
    return value


class Contacts:
    def __init__(self):
        self.steps = 0
        self.present = False
        self.arm = 'left_arm'
        self.support = True

    def resolve(self, selector, env_idx):
        if not self.present:
            raise ContactUnavailable('no fingers')
        return {'position': [0, 0, .01], 'points': [[0, 0, .01], [0, 0, -.01]]}, {
            'resolved_arm': self.arm, 'physics_step': self.steps,
            'finger_bodies': ['finger0', 'finger1'], 'contacts': []}

    def support_evidence(self, label, supports, env_idx):
        return {'contacts': [{'support_label': '@table'}] if self.support else []}


def environment():
    pose = np.array([0., 0., 0., 1., 0., 0., 0.])
    contacts = Contacts()
    lm = SimpleNamespace(get_instance_pose=lambda env_idx, label: (pose[:3].copy(), pose[3:].copy()))
    env = SimpleNamespace(scene_manager=SimpleNamespace(layout_manager=lm), _atomic_contacts=contacts,
                          take_action_cnt=[0], reward_manager=SimpleNamespace(
                              call_func_parser=lambda check, env_idx: float(pose[2] >= .1)))
    return env, pose, contacts


def contact_condition(expected=(0, 0, .01)):
    return {'id': 'contact', 'slot': 'grasp_region', 'kind': 'relative_displacement',
            'measurement': {'kind': 'contact_points', 'label': 'object', 'min_finger_bodies': 2},
            'reference': {'kind': 'object_pose', 'label': 'object'}, 'expected': list(expected),
            'tolerance': .001, 'event': {'kind': 'first_lift', 'label': 'object', 'threshold': .025},
            'track_closest': False}


class RecognitionTests(unittest.TestCase):
    def test_geometry_removal_targets_and_events_cannot_relax_recognition(self):
        changed = contact_condition((9, 9, 9))
        changed['event']['threshold'] = .15  # Geometric event never fires.
        for geometry in ([], [contact_condition()], [changed]):
            with self.subTest(geometry=geometry):
                env, pose, contacts = environment()
                session = AtomicSession(env, AtomicStage.from_dict(config(geometry)), 0)
                pose[2] = .12
                contacts.steps = 1
                self.assertFalse(session.step())  # Lift without any hold is not pick.
                self.assertTrue(session.summary()['goal_success'])
                contacts.present = True
                contacts.steps = 2
                session.observe_events()
                contacts.steps = 3
                self.assertFalse(session.step())  # Touching an already-raised object cannot borrow its lift.
                pose[2] = .23
                contacts.steps = 4
                session.observe_events()
                self.assertTrue(session.step())
                evidence = session.summary()['interaction_evidence']
                self.assertAlmostEqual(evidence['motion_m'], .11)
                self.assertEqual(evidence['consecutive_contact_steps'], 3)
                self.assertEqual(evidence['arm'], 'left_arm')

    def test_contact_loss_arm_change_and_duplicate_callbacks_reset_or_do_not_count(self):
        env, pose, contacts = environment()
        session = AtomicSession(env, AtomicStage.from_dict(config()), 0)
        contacts.present = True
        session.observe_events()
        pose[2] = .12
        for _ in range(5):
            self.assertFalse(session.step())  # One physics step never becomes a sustained hold.
        self.assertEqual(session._recognition_contact_steps, 1)
        contacts.steps = 1
        contacts.present = False
        session.observe_events()
        contacts.present = True
        contacts.steps = 2
        session.observe_events()
        pose[2] = .15
        contacts.arm = 'right_arm'
        contacts.steps = 3
        self.assertFalse(session.step())  # New arm cannot borrow old arm's displacement.
        pose[2] = .26
        contacts.steps = 4
        self.assertTrue(session.step())

    def test_ballistic_lift_after_short_grasp_does_not_complete_pick(self):
        env, pose, contacts = environment()
        session = AtomicSession(env, AtomicStage.from_dict(config()), 0)
        contacts.present = True
        session.observe_events()
        pose[2] = .03
        contacts.steps = 1
        session.observe_events()
        self.assertTrue(session.interaction_observed)
        contacts.present = False
        pose[2] = .12
        contacts.steps = 2
        self.assertFalse(session.step())
        # A later catch at height also cannot borrow the original short lift.
        contacts.present = True
        contacts.steps = 3
        session.observe_events()
        contacts.steps = 4
        self.assertFalse(session.step())
        pose[2] = .15
        contacts.steps = 5
        self.assertFalse(session.step())  # New held interval is only 3 cm, not requested 10 cm.
        pose[2] = .23
        contacts.steps = 6
        self.assertTrue(session.step())

    def test_push_requires_planar_motion_with_support_not_a_finger_lift(self):
        env, pose, contacts = environment()
        env.reward_manager.call_func_parser = lambda check, idx: 1.
        session = AtomicSession(env, AtomicStage.from_dict(config(family='push')), 0)
        contacts.present = True
        contacts.support = False
        session.observe_events()
        pose[:] = [.1, 0, .1, 1, 0, 0, 0]
        contacts.steps = 1
        self.assertFalse(session.step())
        contacts.support = True
        contacts.steps = 2
        session.observe_events()
        pose[2] += .1
        contacts.steps = 3
        self.assertFalse(session.step())  # Vertical movement alone is not push.
        pose[0] += .03
        contacts.steps = 4
        self.assertTrue(session.step())
        self.assertTrue(session.summary()['interaction_evidence']['support_evidence']['contacts'])

    def test_schema_fails_closed_and_variant_preserves_physical_recognition(self):
        data = config()
        del data['recognition']
        with self.assertRaisesRegex(ValueError, 'requires explicit recognition'):
            AtomicStage.from_dict(data)
        for value in (0, 1, True, 2.0):
            data = config()
            data['recognition']['min_contact_steps'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                AtomicStage.from_dict(data)
        stage = AtomicStage.from_dict(config([contact_condition()]))
        varied = stage.with_variant({'stage_id': 'test', 'conditions': {'contact': {'expected': [9, 9, 9]}}})
        self.assertEqual(stage.recognition, varied.recognition)
        varied.recognition['arm'] = 'other'
        self.assertEqual(stage.recognition['arm'], 'any')
        wrong_object = config()
        wrong_object['success_checks'][0]['args']['label'] = 'unrelated_object'
        with self.assertRaisesRegex(ValueError, 'same object'):
            AtomicStage.from_dict(wrong_object)


class FrozenReferenceTests(unittest.TestCase):
    def test_start_frame_stays_fixed_after_motion_rotation_and_external_result_mutation(self):
        env, pose, _ = environment()
        pose[:] = [1, 2, 3, np.sqrt(.5), 0, 0, np.sqrt(.5)]
        condition = {'id': 'lift', 'slot': 'lift_goal', 'kind': 'relative_displacement',
                     'measurement': {'kind': 'object_position', 'label': 'object'},
                     'reference': {'kind': 'object_pose', 'label': 'object', 'time': 'stage_start'},
                     'expected': [.1, 0, .1], 'tolerance': 1e-6}
        session = AtomicSession(env, AtomicStage.from_dict({**config([condition]), 'family': 'place', 'recognition': None}), 0)
        pose[:] = [1, 2.1, 3.1, 1, 0, 0, 0]
        measured, _, reference, source = session._resolve_condition(condition)
        self.assertTrue(evaluate_geometry(condition, measured, reference).passed)
        self.assertEqual(source['time'], 'stage_start')
        self.assertEqual(source['captured_policy_action_index'], 0)
        reference[0] = 100
        self.assertAlmostEqual(session._resolve_condition(condition)[2][0], 1)
        live = deepcopy(condition)
        live['reference']['time'] = 'live'
        self.assertFalse(evaluate_geometry(live, *session._resolve_condition(live)[::2]).passed)

    def test_historical_object_footprint_is_not_replaced_by_the_live_pose(self):
        env, pose, _ = environment()
        def surface(label, env_idx, root_pose):
            return {'position': root_pose[:3].tolist(), 'orientation': root_pose[3:].tolist(),
                    'vertices': [root_pose[:3].tolist()], 'triangles': [], 'geometry_representation': 'fixture'}
        env._atomic_surfaces = SimpleNamespace(resolve=surface)
        condition = {'id': 'above', 'slot': 'goal', 'kind': 'spatial_relation', 'relation_scope': 'objects',
                     'measurement': {'kind': 'object_pose', 'label': 'object'},
                     'reference': {'kind': 'object_pose', 'label': 'object', 'time': 'stage_start'},
                     'expected': 'above', 'tolerance': .001}
        session = AtomicSession(env, AtomicStage.from_dict({**config([condition]), 'family': 'place', 'recognition': None}), 0)
        pose[2] = .2
        measured, _, reference, _ = session._resolve_condition(condition)
        self.assertEqual(measured['vertices'], [[0, 0, .2]])
        self.assertEqual(reference['vertices'], [[0, 0, 0]])
        condition['expected'] = 'on_top'
        with self.assertRaisesRegex(ValueError, 'live support frame'):
            AtomicStage.from_dict({**config([condition]), 'family': 'place', 'recognition': None})


class ContactBackendTests(unittest.TestCase):
    def backend(self):
        backend = PhysXContacts.__new__(PhysXContacts)
        lm = SimpleNamespace(get_instance_name=lambda i, l: l,
                             get_scene_object=lambda i, n: SimpleNamespace(usd_prim_path='/env0/' + n))
        backend.env = SimpleNamespace(scene_manager=SimpleNamespace(layout_manager=lm), sim=SimpleNamespace(
            scene=SimpleNamespace(env_origins=np.zeros((1, 3)))))
        backend.fingers = {'/left0': (0, 'left'), '/left1': (0, 'left'), '/right0': (0, 'right')}
        backend.steps, backend.reports, backend.errors = 2, 2, []
        def row(body):
            return {'actor0': body, 'actor1': '/env0/object', 'collider0': body, 'collider1': '/env0/object',
                    'position_world': [0, 0, 0], 'normal_world': [0, 0, 1], 'impulse': [1, 0, 0]}
        backend.rows = [row('/right0') for _ in range(20)] + [row('/left0'), row('/left1')]
        return backend

    def test_single_finger_with_many_points_cannot_hide_other_arms_valid_grasp(self):
        _, source = self.backend().resolve({'label': 'object', 'min_finger_bodies': 2}, 0)
        self.assertEqual(source['resolved_arm'], 'left')
        self.assertEqual(source['finger_bodies'], ['/left0', '/left1'])

    def test_support_contact_cannot_hide_backend_failure(self):
        backend = self.backend()
        backend.errors = ['broken callback']
        with self.assertRaisesRegex(RuntimeError, 'reporting failed'):
            backend.has_support_contact('object', 'support', 0)

    def test_support_normal_and_impulse_are_signed_for_the_supported_body(self):
        backend = self.backend()
        def row(reverse=False, downward=False, tangential=False):
            a, b = ('/env0/support', '/env0/object') if reverse else ('/env0/object', '/env0/support')
            sign = (-1 if reverse else 1) * (-1 if downward else 1)
            return {'actor0': a, 'actor1': b, 'collider0': a, 'collider1': b,
                    'position_world': [0, 0, 0], 'normal_world': [0, 0, sign],
                    'impulse': [1, 0, 0] if tangential else [0, 0, sign]}
        for reverse in (False, True):
            with self.subTest(reverse=reverse):
                backend.rows = [row(reverse=reverse)]
                self.assertTrue(backend.has_support_contact('object', 'support', 0))
                backend.rows = [row(reverse=reverse, downward=True)]
                self.assertFalse(backend.has_support_contact('object', 'support', 0))
                backend.rows = [row(reverse=reverse, tangential=True)]
                self.assertFalse(backend.has_support_contact('object', 'support', 0))
        backend.env.scene_manager._tables = [SimpleNamespace(prim_path='/env0/support')]
        backend.rows = [row()]
        evidence = backend.support_evidence('object', ['@table'], 0)
        self.assertEqual(evidence['contacts'][0]['support_label'], '@table')
        self.assertEqual(evidence['contacts'][0]['impulse_on_object_world'], [0, 0, 1])

    def test_tool_pair_uses_actual_actor_or_collider_identity_and_both_pair_directions(self):
        backend = self.backend()
        backend.env.sim.scene.env_origins[0] = [1, 2, 3]
        def row(a, b, p, collider_a=None, collider_b=None):
            return {'actor0': a, 'actor1': b, 'collider0': collider_a or a, 'collider1': collider_b or b,
                    'position_world': p, 'normal_world': [0, 0, 1], 'impulse': [1, 0, 0]}
        backend.rows = [row('/env0/tool/body', '/env0/object', [1, 2, 3]),
                        row('/env0/object', '/World/static', [1.01, 2, 3], collider_b='/env0/tool/tip'),
                        row('/env1/tool', '/env0/object', [9, 9, 9]),
                        row('/env0/toolbox', '/env0/object', [9, 9, 9]),
                        row('/left0', '/env0/tool', [9, 9, 9])]
        measured, source = backend.resolve_object_pair({'kind': 'object_contact_points',
            'label': 'tool', 'other_label': 'object'}, 0)
        self.assertEqual(len(measured['points']), 2)
        np.testing.assert_allclose(measured['points'], [[0, 0, 0], [.01, 0, 0]])
        self.assertEqual(source['object_roots'], ['/env0/tool', '/env0/object'])
        backend.rows = backend.rows[2:]
        with self.assertRaises(ContactUnavailable):
            backend.resolve_object_pair({'label': 'tool', 'other_label': 'object'}, 0)

    def test_first_contact_captures_tool_pose_and_physical_event_evidence(self):
        env, pose, _ = environment()
        backend = self.backend()
        backend.env = SimpleNamespace(scene_manager=backend.env.scene_manager, sim=backend.env.sim)
        env._atomic_contacts = backend
        backend.rows = []
        pair = {'kind': 'object_contact_points', 'label': 'tool', 'other_label': 'object'}
        condition = {'id': 'tool_pose', 'slot': 'tool_tip', 'kind': 'point',
                     'measurement': {'kind': 'object_position', 'label': 'tool'},
                     'event': {'kind': 'first_contact', 'measurement': pair},
                     'expected': [0, 0, .2], 'tolerance': .001, 'track_closest': False}
        stage = AtomicStage.from_dict({**config([condition]), 'family': 'touch_with_tool', 'recognition': None})
        session = AtomicSession(env, stage, 0)
        session.observe_events()
        self.assertEqual(session.summary()['geometry_observed'], 0)
        pose[2] = .2
        backend.rows = [{'actor0': '/env0/tool', 'actor1': '/env0/object',
                         'collider0': '/env0/tool/tip', 'collider1': '/env0/object',
                         'position_world': [0, 0, .2], 'normal_world': [0, 0, 1], 'impulse': [1, 0, 0]}]
        backend.steps += 1
        session.observe_events()
        saved = session.summary()['geometry']['tool_pose']
        self.assertTrue(saved['result']['passed'])
        self.assertEqual(saved['event_evidence']['contact_source']['contacts'][0]['impulse'], [1, 0, 0])
        pose[2] = .9
        session.observe_events()
        self.assertEqual(session.summary()['geometry']['tool_pose']['measured_state'], [0, 0, .2])

    def test_nonfinite_contact_report_is_an_instrumentation_failure(self):
        backend = self.backend()
        backend._decode = lambda value: value
        header = SimpleNamespace(actor0='tool', actor1='object', collider0='tool', collider1='object',
                                 contact_data_offset=0, num_contact_data=1)
        contact = SimpleNamespace(position=[float('nan'), 0, 0], normal=[0, 0, 1], impulse=[1, 0, 0])
        backend._report([header], [contact])
        self.assertIn('finite 3-vectors', backend.errors[0])
        with self.assertRaises(RuntimeError):
            backend.resolve_object_pair({'label': 'tool', 'other_label': 'object'}, 0)


if __name__ == '__main__':
    unittest.main()
