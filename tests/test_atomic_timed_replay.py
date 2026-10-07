"""Multiple stage boundaries inside one command preserve physical history."""
from dataclasses import replace
from types import SimpleNamespace as NS
import unittest
from task.atomic.spec import AtomicProgram, AtomicTrace
from task.atomic.replay import validate_start_boundary
from test_atomic_physical_runtime import World, stage
from test_atomic_prefix_recognition import method


def fixture(whole=False):
    a = replace(stage('contact_joint_motion','a'), success_checks=({'name':'is_atomic_interaction','args':{}},))
    b = replace(a, id='b', recognition={**a.recognition,'direction':1},
                success_checks=({'name':'is_test_goal' if whole else 'is_atomic_interaction','args':{}},))
    c = replace(stage('held_tool_contact','c'), success_checks=({'name':'is_atomic_interaction','args':{}},))
    p = AtomicProgram('test',(a,b,c))
    trace = AtomicTrace('test',0,({'joint':[0]},), {'a':0,**({'c':1} if whole else {})},
        {'b':{'action_index':1,'physics_step':103,'at_action_boundary':False},
         'c':{'action_index':1,'physics_step':108 if whole else 106,'at_action_boundary':whole}},
        ({'start':100,'end':108},), {'physics_dt':.01,'control_substeps':8})
    return p,trace


class TimedReplayTests(unittest.TestCase):
    def world(self, whole=False, lose_hold=False):
        p,t = fixture(whole);w = World();env = w.env;w.hold();w.goal = not whole
        env.num_envs=1;env.dt=.01;env.obs_manager=NS(collect_interval=8)
        env.atomic_program=p;env.atomic_trace=t;env.atomic_stage=p.stage('c');env.env_seeds=[0]
        env.get_action_type=lambda _: 'joint';resets=[];phases=[]
        env.reward_manager.func_parser=NS(init_state=lambda:resets.append('parser'))
        env.robot_manager=NS(set_origin_endpose=lambda:resets.append('robot'))
        observe=method('_observe_atomic_physics')
        def take_action(action):
            env.take_action_cnt[0]+=1
            for i in range(1,9):
                w.contacts.steps=i
                w.joint={1:0,2:-.002,3:-.006,4:-.006,5:-.003}.get(i,0)
                if lose_hold and i==5:w.release()
                observe(env)
                current=env._atomic_replay_observer.current
                phases.append(current.stage.id if current else None)
                stop=getattr(env,'_atomic_replay_stop',None)
                if stop is not None and stop.reached:break
            if whole:w.goal=True # Native endpoint update after the complete command.
        env.take_action=take_action
        return w,phases,resets

    def test_two_substep_boundaries_in_one_command_activate_at_exact_samples(self):
        w,phases,resets=self.world();method('_start_atomic_stage')(w.env)
        self.assertEqual(phases,['a','a','b','b','b',None])
        self.assertEqual(w.contacts.steps,6);self.assertEqual(resets,['parser','robot'])
        evidence=w.env._atomic_start_evidence['prefix_stage_validation']
        self.assertEqual([s['stage_id'] for s in evidence],['a','b'])
        self.assertTrue(all(s['prefix_boundary_verified'] for s in evidence))
        self.assertTrue(w.env._atomic_start_evidence['physics_boundary_verified'])

    def test_whole_boundary_after_partial_stage_waits_for_native_endpoint_update(self):
        w,phases,resets=self.world(whole=True);method('_start_atomic_stage')(w.env)
        self.assertEqual(w.contacts.steps,8)
        self.assertEqual(w.env._atomic_start_evidence['mode'],'linear_timed_prefix')
        self.assertTrue(w.env._atomic_start_evidence['physics_boundary_verified'])
        self.assertEqual(phases[-1],'b')
        self.assertEqual([s['stage_id'] for s in w.env._atomic_start_evidence['prefix_stage_validation']],['a','b'])

    def test_lost_contact_cannot_be_certified_at_later_substep(self):
        w,_,resets=self.world(lose_hold=True)
        with self.assertRaisesRegex(ValueError,'replay diverged'):
            method('_start_atomic_stage')(w.env)
        self.assertEqual(resets,[]);self.assertFalse(w.env._atomic_replaying)
        self.assertFalse(w.env._atomic_start_evidence['prefix_stage_validation'][-1]['prefix_boundary_verified'])

    def test_missing_or_same_sample_boundaries_are_rejected_before_replay(self):
        p,t=fixture()
        for boundaries in ({'c':t.stage_boundaries['c']},
            {'b':t.stage_boundaries['b'],'c':{**t.stage_boundaries['c'],'physics_step':103}},
            {**t.stage_boundaries,'a':{'action_index':0,'physics_step':100,'at_action_boundary':False}}):
            with self.subTest(boundaries=boundaries),self.assertRaises(ValueError):
                validate_start_boundary(p,p.stage('c'),replace(t,stage_boundaries=boundaries))


if __name__=='__main__':unittest.main()
