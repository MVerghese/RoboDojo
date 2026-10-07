"""Initial independent roots are valid; later graph starts need state fidelity."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

from scripts.atomic.submit_stage import validate_stage_inputs
from task.atomic.replay import validate_start_boundary, replay_prefix
from task.atomic.spec import AtomicProgram, AtomicTrace
from test_atomic_physical_runtime import World, stage


class StartBoundaryTests(unittest.TestCase):
    def program(self):
        return AtomicProgram('task', (stage('held_tool_contact','a'), stage('held_tool_contact','b')),
                             stage_dependencies={'a':[],'b':[]})

    def test_nonfirst_independent_root_starts_at_initial_scene_with_or_without_zero_trace(self):
        p=self.program(); b=p.stage('b')
        for trace in (None,AtomicTrace('task',0,({},),{'a':0,'b':0})):
            validate_stage_inputs(p,'b',trace,None)
            self.assertEqual(validate_start_boundary(p,b,trace)['mode'],'initial_scene')
            def forbidden(*args):raise AssertionError('initial root cannot replay or check another stage')
            self.assertEqual(replay_prefix(p,b,trace,forbidden,forbidden),0)

    def test_later_graph_boundaries_and_wrong_task_are_not_treated_as_initial_roots(self):
        p=self.program();b=p.stage('b')
        with self.assertRaisesRegex(ValueError,'graph starts'):
            validate_stage_inputs(p,'b',AtomicTrace('task',0,({},{}),{'a':0,'b':1}),None)
        with self.assertRaisesRegex(ValueError,'task_name'):
            validate_stage_inputs(p,'b',AtomicTrace('other',0,({},),{'b':0}),None)

    def test_actual_evaluator_initial_root_keeps_native_parser_and_robot_baselines(self):
        path=Path(__file__).resolve().parents[1]/'src/eval_client/eval_env.py'
        tree=ast.parse(path.read_text())
        method=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='_start_atomic_stage')
        namespace={}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[method],type_ignores=[])),str(path),'exec'),namespace)
        w=World();w.goal=False;p=self.program();env=w.env
        env.atomic_program=p;env.atomic_stage=p.stage('b')
        env.atomic_trace=AtomicTrace('task',0,({},),{'a':0,'b':0});env.env_seeds=[0]
        def forbidden(*args):raise AssertionError('zero replay must preserve initialized baselines')
        env.take_action=forbidden
        env.reward_manager.func_parser=SimpleNamespace(init_state=forbidden)
        env.robot_manager=SimpleNamespace(set_origin_endpose=forbidden)
        namespace['_start_atomic_stage'](env)
        self.assertEqual(env._atomic_start_evidence['mode'],'initial_scene')
        self.assertEqual(env.take_action_cnt[0],0)
        self.assertFalse(env._atomic_replaying)
        self.assertEqual(env._atomic_sessions[0].stage.id,'b')
