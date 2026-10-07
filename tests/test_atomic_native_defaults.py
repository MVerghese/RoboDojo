"""Atomic predicates preserve the actual native constructor's default contract."""
import ast
from dataclasses import replace
from pathlib import Path
from types import MethodType
import unittest
from task.atomic.session import AtomicSession, _native_check
from task.atomic.spec import AtomicStage
from test_atomic_physical_runtime import World, stage


def attach_native(manager, name):
    source = Path('env/reward_manager/reward_manager.py').read_text()
    klass = next(n for n in ast.parse(source).body if isinstance(n, ast.ClassDef) and n.name == 'RewardManager')
    function = next(n for n in klass.body if isinstance(n, ast.FunctionDef) and n.name == name)
    namespace = {}
    exec(compile(ast.Module(body=[function], type_ignores=[]), '<native predicate>', 'exec'), namespace)
    setattr(manager, name, MethodType(namespace[name], manager))


class NativeDefaultsTests(unittest.TestCase):
    def test_stacked_omitted_defaults_reach_parser_and_summary(self):
        w = World();manager = w.env.reward_manager;attach_native(manager, 'is_stacked');seen=[]
        manager.call_func_parser=lambda definition, env_idx: seen.append(definition) or 1.
        check={'name':'is_stacked','args':{'label_list':['other','object']}}
        session=AtomicSession(w.env, replace(stage('supported_release'), success_checks=(check,)), 0)
        self.assertTrue(session._check_success())
        args=seen[0][1]
        self.assertIsNone(args['z_threshold']);self.assertEqual(args['xy_threshold'],.04)
        self.assertIs(args['in_order'],False)
        self.assertEqual(session.summary()['resolved_success_checks'][0]['args'],args)
        self.assertNotIn('z_threshold',check['args'])

    def test_explicit_native_limits_are_not_overwritten(self):
        w=World();attach_native(w.env.reward_manager,'is_stacked')
        check={'name':'is_stacked','args':{'label_list':['other','object'], 'xy_threshold':.0175,
                                        'z_threshold':.04,'in_order':True}}
        self.assertEqual(_native_check(w.env.reward_manager,check),check)

    def test_native_lift_defaults_resolve_but_pick_schema_requires_explicit_threshold(self):
        w=World();attach_native(w.env.reward_manager,'is_lift')
        check={'name':'is_lift','args':{'label':'object'}}
        self.assertEqual(_native_check(w.env.reward_manager,check)['args']['z_threshold'],.05)
        with self.assertRaisesRegex(ValueError,'pick lift threshold'):
            AtomicStage.from_dict({'id':'pick','family':'pick','instruction':'Pick object',
                'success_checks':[check], 'recognition':{'kind':'finger_contact_motion','label':'object',
                'arm':'any','motion_threshold_m':.025,'min_contact_steps':2}})

    def test_missing_required_arguments_fail_before_physics(self):
        w=World();attach_native(w.env.reward_manager,'is_stacked')
        with self.assertRaises(TypeError):
            _native_check(w.env.reward_manager,{'name':'is_stacked','args':{}})

    def test_default_that_updates_native_state_is_rejected(self):
        w=World();w.env.reward_manager.is_custom=lambda **args: ('is_custom',{'update':True})
        with self.assertRaisesRegex(ValueError,'must not update'):
            _native_check(w.env.reward_manager,{'name':'is_custom','args':{}})

if __name__=='__main__':unittest.main()
