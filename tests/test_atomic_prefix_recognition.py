"""Later starts must verify recorded physical history, not fresh endpoint checks."""
import ast
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
import tempfile
import json
from task.atomic.replay import PrefixReplayObserver,replay_prefix
from task.atomic.session import AtomicSession
from task.atomic.spec import AtomicProgram,AtomicTrace
from test_atomic_physical_runtime import World,stage


def method(name):
    path=Path(__file__).resolve().parents[1]/'src/eval_client/eval_env.py'
    tree=ast.parse(path.read_text());node=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name==name)
    namespace={};exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),str(path),'exec'),namespace)
    return namespace[name]


class PrefixRecognitionTests(unittest.TestCase):
    def program(self):
        a=replace(stage('contact_joint_motion','a'),success_checks=({'name':'is_atomic_interaction','args':{}},))
        b=replace(stage('held_tool_contact','b'),success_checks=({'name':'is_atomic_interaction','args':{}},))
        return AtomicProgram('test',(a,b))

    def test_persistent_substep_observer_certifies_motion_that_a_fresh_recognizer_cannot(self):
        w=World();p=self.program();o=PrefixReplayObserver(w.env,p,p.stage('b'));w.hold()
        for step in range(1,5):
            w.contacts.steps=step
            if step==4:w.joint=-.01
            o.observe_physics()
        self.assertFalse(AtomicSession(w.env,p.stage('a'),0).check_success_only())
        self.assertTrue(o.stage_succeeded(p.stage('a')))
        self.assertEqual(o.evidence[0]['interaction_evidence']['kind'],'contact_joint_motion')
        self.assertIsNone(o.current)

    def test_native_endpoint_cannot_bypass_missing_contact_or_maintained_hold(self):
        for contact,maintained in ((False,False),(True,True)):
            with self.subTest(contact=contact,maintained=maintained):
                w=World();p=self.program()
                a=replace(p.stage('a'),success_checks=({'name':'goal','args':{}},),
                          maintained_holds=({'label':'target','arm':'left','min_finger_bodies':2},) if maintained else ())
                p=AtomicProgram('test',(a,p.stage('b')));o=PrefixReplayObserver(w.env,p,p.stage('b'))
                if contact:w.hold()
                for step in range(1,5):
                    w.contacts.steps=step
                    if step==4:w.joint=-.01
                    o.observe_physics()
                self.assertFalse(o.stage_succeeded(a))

    def test_actual_evaluator_observes_prefix_substeps_and_records_success_before_reset(self):
        w=World();p=self.program();env=w.env;w.hold();env.end_flag=[False]
        env.atomic_program=p;env.atomic_stage=p.stage('b');env.env_seeds=[0]
        env.atomic_trace=AtomicTrace('test',0,({},),{'a':0,'b':1})
        resets=[]
        env.reward_manager.func_parser=NS(init_state=lambda:resets.append('parser'))
        env.robot_manager=NS(set_origin_endpose=lambda:resets.append('robot'))
        observe=method('_observe_atomic_physics')
        def take_action(action):
            env.take_action_cnt[0]+=1
            for i in range(1,5):
                w.contacts.steps=i
                if i==4:w.joint=-.01
                observe(env)
        env.take_action=take_action
        method('_start_atomic_stage')(env)
        self.assertEqual(resets,['parser','robot'])
        self.assertFalse(env._atomic_replaying);self.assertIsNone(env._atomic_replay_observer)
        self.assertEqual(env.take_action_cnt[0],0)
        self.assertTrue(env._atomic_start_evidence['prefix_stage_validation'][0]['action_success'])
        self.assertEqual(env._atomic_sessions[0].stage.id,'b')

    def test_wrong_stage_callback_is_rejected(self):
        w=World();p=self.program();o=PrefixReplayObserver(w.env,p,p.stage('b'))
        with self.assertRaisesRegex(ValueError,'stage order'):
            o.stage_succeeded(p.stage('b'))

    def test_failed_actual_prefix_cleans_up_and_never_resets_baselines_or_starts_policy_stage(self):
        w=World();p=self.program();env=w.env
        env.atomic_program=p;env.atomic_stage=p.stage('b');env.env_seeds=[0]
        env.atomic_trace=AtomicTrace('test',0,({},),{'a':0,'b':1})
        def forbidden():raise AssertionError('diverged replay cannot reset baselines')
        env.reward_manager.func_parser=NS(init_state=forbidden)
        env.robot_manager=NS(set_origin_endpose=forbidden)
        observe=method('_observe_atomic_physics')
        def take_action(action):
            env.take_action_cnt[0]+=1
            for i in range(1,5):
                w.contacts.steps=i;w.joint=-.01*i
                observe(env)
        env.take_action=take_action
        with self.assertRaisesRegex(ValueError,'replay diverged'):
            method('_start_atomic_stage')(env)
        self.assertFalse(env._atomic_replaying);self.assertIsNone(env._atomic_replay_observer)
        self.assertFalse(env._atomic_start_evidence['prefix_stage_validation'][0]['action_success'])
        self.assertFalse(getattr(env,'_atomic_sessions',{}))

    def test_late_maintained_hold_loss_rejects_a_previously_latched_action(self):
        w=World();p=self.program()
        a=replace(p.stage('a'),maintained_holds=({'label':'target','arm':'left','min_finger_bodies':2},))
        p=AtomicProgram('test',(a,p.stage('b')));o=PrefixReplayObserver(w.env,p,p.stage('b'))
        w.hold();w.hold(label='target')
        for i in range(1,5):
            w.contacts.steps=i
            if i==4:w.joint=-.01
            o.observe_physics()
        self.assertTrue(o.current.success)
        w.contacts.holds.pop(('target','left'));w.contacts.steps=5;o.observe_physics()
        self.assertFalse(o.stage_succeeded(a))
        self.assertTrue(o.evidence[0]['action_success'])
        self.assertFalse(o.evidence[0]['prefix_boundary_verified'])

    def test_stage_only_proof_requires_boundary_evidence_and_ignores_full_task_success(self):
        from scripts.atomic.run_prefix_validation import collect_proof
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);run=root/'runs/case';run.mkdir(parents=True)
            detail={'atomic_start':{'mode':'linear_prefix','prefix_stage_validation':[
                {'action_success':True,'prefix_boundary_verified':False}]},'atomic':{'action_success':True}}
            report={'native_results':[{'success':True,'details':{'0':detail}}]}
            path=run/'eval_report.json';path.write_text(json.dumps(report))
            collect_proof(root,{'id':'case'})
            self.assertEqual(json.loads((root/'prefix-validation.json').read_text())['status'],'prefix_validation_unavailable')
            detail['atomic_start']['prefix_stage_validation'][0]['prefix_boundary_verified']=True
            detail['atomic']['action_success']=False;path.write_text(json.dumps(report))
            collect_proof(root,{'id':'case'})
            proof=json.loads((root/'prefix-validation.json').read_text())
            self.assertEqual(proof['status'],'observed_verified_prefix')
            self.assertFalse(proof['episodes'][0]['selected_stage_success'])
