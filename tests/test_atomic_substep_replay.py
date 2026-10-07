"""Interrupted joint prefixes retain applied controls and prove physical onset."""
from dataclasses import replace
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest

from task.atomic.replay import (replay_prefix, validate_start_boundary,
                                validate_substep_runtime, SubstepReplayStop)
from task.atomic.spec import AtomicProgram, AtomicTrace
from test_atomic_physical_runtime import World, stage
from test_atomic_prefix_recognition import method
from env.robot_manager.control_manager import ControlManager


def fixture():
    a = replace(stage('contact_joint_motion', 'a'), success_checks=({'name':'is_atomic_interaction','args':{}},))
    b = replace(stage('held_tool_contact', 'b'), success_checks=({'name':'is_atomic_interaction','args':{}},))
    program = AtomicProgram('test', (a, b))
    trace = AtomicTrace('test', 0, ({'joint': [1]}, {'joint': [2]}), {'a': 0},
                        {'b': {'action_index': 2, 'physics_step': 106, 'at_action_boundary': False}},
                        ({'start': 100, 'end': 104}, {'start': 104, 'end': 108}),
                        {'physics_dt': .01, 'control_substeps': 4})
    return program, trace


class SubstepReplayTests(unittest.TestCase):
    def test_loader_retains_physical_boundary_and_timing(self):
        p, t = fixture()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'trace.json'
            path.write_text(json.dumps(t.__dict__))
            loaded = AtomicTrace.load(path)
            self.assertEqual(loaded, t)
            self.assertEqual(validate_start_boundary(p, p.stage('b'), loaded)['physics_substeps'], 2)

    def test_prefix_replays_complete_commands_then_only_selected_substeps(self):
        p, t = fixture(); calls = []
        replay_prefix(p, p.stage('b'), t, lambda a: calls.append(('whole', a)),
                      lambda s: calls.append(('verify', s.id)) or True,
                      lambda a, n: calls.append(('partial', a, n)))
        self.assertEqual(calls, [('whole', t.actions[0]), ('partial', t.actions[1], 2), ('verify', 'a')])
        with self.assertRaisesRegex(ValueError, 'physics-boundary action callback'):
            replay_prefix(p, p.stage('b'), t, lambda _: None, lambda _: True)

    def test_invalid_timing_spans_predecessors_and_boundaries_are_rejected(self):
        p, t = fixture()
        variants = [replace(t, control_timing={}), replace(t, action_physics_spans=()),
                    replace(t, action_physics_spans=({'start': 100, 'end': 104}, {'start': 105, 'end': 109})),
                    replace(t, action_physics_spans=({}, {})),
                    replace(t, control_timing={'physics_dt': float('nan'), 'control_substeps': 4}),
                    replace(t, stage_boundaries={'b': {'action_index': 2, 'physics_step': 110, 'at_action_boundary': False}})]
        for bad in variants:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                validate_start_boundary(p, p.stage('b'), bad)

    def test_runtime_rejects_ik_scripted_controls_multi_env_and_cadence_changes(self):
        _, t = fixture()
        env = NS(num_envs=1, dt=.01, obs_manager=NS(collect_interval=4),
                 _atomic_contacts=NS(steps=0), get_action_type=lambda _: 'joint')
        validate_substep_runtime(env, t)
        for attr, value in [('num_envs', 2), ('dt', .02), ('interact', True),
                            ('support_arm_action', [[{}]]), ('get_action_type', lambda _: 'ee')]:
            old = getattr(env, attr, None); setattr(env, attr, value)
            with self.subTest(attr=attr), self.assertRaises(ValueError): validate_substep_runtime(env, t)
            setattr(env, attr, old)

    def test_sampling_gap_stops_with_deferred_error(self):
        contacts = NS(steps=50); stop = SubstepReplayStop(contacts, 2)
        contacts.steps = 51; stop.observe(contacts); self.assertFalse(stop.reached)
        contacts.steps = 53; stop.observe(contacts)
        self.assertTrue(stop.reached); self.assertIn('sampling diverged', stop.error)

    def test_discard_keeps_applied_controls_and_other_environments(self):
        manager = ControlManager(2, None)
        manager.prev_control[0] = {'applied': 7}
        manager.push([0, 1], [[{}, {}], [{}]])
        self.assertEqual(manager.discard_pending(0), 2)
        self.assertEqual(manager.prev_control[0], {'applied': 7})
        self.assertFalse(manager.control_queue[1].is_empty())

    def test_actual_command_loop_stops_before_native_endpoint_bookkeeping(self):
        w = World(); env = w.env
        manager = ControlManager(1, None); manager.prev_control[0] = {'applied': 7}
        env.robot_manager = NS(robot_list=[], control_manager=manager)
        env.physx_monitor_enabled = False; env.step_lim = 10; env.end_flag = [False]
        env._atomic_record_dir = None; env._atomic_replaying = True
        env._atomic_start_evidence = {}; env._atomic_replay_observer = None
        env._atomic_replay_stop = SubstepReplayStop(w.contacts, 2)
        env.validate_action_dict = lambda _: None; env.get_action_type = lambda _: 'joint'
        env.process_control_info = lambda *_: [{}, {}, {}, {}]
        env.have_empty = lambda ids: bool(manager.get_empty(ids))
        observe = method('_observe_atomic_physics')
        def step(env_idx_list):
            manager.control_queue[0].pop(); w.contacts.steps += 1; observe(env)
        env.step = step
        def forbidden(*args, **kwargs): raise AssertionError('interrupted command must not score native endpoint')
        env.reward_manager.step = forbidden; env.is_episode_end = forbidden
        method('take_action_batch')(env, [{}], [0])
        self.assertEqual(env.take_action_cnt, [1])
        self.assertEqual(env._atomic_start_evidence['discarded_control_substeps'], 2)
        self.assertEqual(manager.prev_control[0], {'applied': 7})
        self.assertTrue(manager.control_queue[0].is_empty())

    def test_actual_stage_start_uses_persistent_physical_witness_at_partial_boundary(self):
        p, t = fixture(); w = World(); env = w.env; w.hold()
        env.atomic_program = p; env.atomic_stage = p.stage('b'); env.atomic_trace = t; env.env_seeds = [0]
        env.num_envs = 1; env.dt = .01; env.obs_manager = NS(collect_interval=4)
        env.get_action_type = lambda _: 'joint'; resets = []
        env.reward_manager.func_parser = NS(init_state=lambda: resets.append('parser'))
        env.robot_manager = NS(set_origin_endpose=lambda: resets.append('robot'))
        observe = method('_observe_atomic_physics')
        def take_action(action):
            env.take_action_cnt[0] += 1
            for _ in range(4):
                w.contacts.steps += 1
                if w.contacts.steps == 6: w.joint = -.01
                observe(env)
                stop = getattr(env, '_atomic_replay_stop', None)
                if stop is not None and stop.reached: break
        env.take_action = take_action
        method('_start_atomic_stage')(env)
        self.assertEqual(w.contacts.steps, 6)
        self.assertEqual(resets, ['parser', 'robot'])
        self.assertTrue(env._atomic_start_evidence['physics_boundary_verified'])
        self.assertTrue(env._atomic_start_evidence['prefix_stage_validation'][0]['prefix_boundary_verified'])
        self.assertIsNone(env._atomic_replay_stop)
        self.assertEqual(env.take_action_cnt, [0])


if __name__ == '__main__': unittest.main()
