"""Choice completion preserves optional attempts and rejects ambiguous merges."""
from dataclasses import replace
import unittest

from test_atomic_physical_runtime import World
from task.atomic.spec import AtomicChoice,AtomicProgram,AtomicStage
from task.atomic.sequence import AtomicSequence
from task.atomic.replay import replay_prefix


def pick(ident,label):
    return AtomicStage.from_dict({'id':ident,'family':'pick','instruction':'Pick '+label,
        'recognition':{'kind':'finger_contact_motion','label':label,'arm':'any','min_contact_steps':2,'motion_threshold_m':.025},
        'success_checks':[{'name':'is_lift','args':{'label':label,'z_threshold':.025}}]})


def program(required=1):
    stages=tuple(pick(ident,label) for ident,label in [('a','object'),('b','other'),('c','target')])
    tail=AtomicStage.from_dict({'id':'finish','family':'place','instruction':'finish',
        'success_checks':[{'name':'is_test_goal','args':{}}]})
    choice=AtomicChoice.from_dict({'id':'choose','branches':[['a'],['b'],['c']],'required':required})
    deps={'a':[],'b':[],'c':[],'choose':['a','b','c'],'finish':['choose']}
    return AtomicProgram('t',stages+(tail,),stage_dependencies=deps,choices=(choice,))


def tick(w,seq):
    w.contacts.steps+=1;seq.observe_events()


class ChoiceTests(unittest.TestCase):
    def test_first_completed_branch_enables_successor_and_preserves_other_attempts(self):
        w=World();seq=AtomicSequence(w.env,program(),0)
        w.hold();tick(w,seq);w.poses['object'][2]=.04;tick(w,seq)
        self.assertEqual(seq.summary()['choices'][0]['status'],'resolved')
        self.assertEqual(seq.summary()['choices'][0]['completed_branches'],[0])
        self.assertEqual(set(seq.sessions),{'finish'})
        rows={r['stage_id']:r for r in seq.summary()['stages']}
        self.assertTrue(rows['a']['action_success'])
        self.assertEqual(rows['b']['choice_status'],'not_selected')
        self.assertFalse(rows['b']['required'])
        self.assertTrue(rows['b']['reached']) # It was an enabled observer, even without contact.
        self.assertFalse(rows['finish']['action_success']) # Same physical sample cannot finish successor.
        tick(w,seq);self.assertTrue(seq.completed['finish']['action_success'])

    def test_choose_two_waits_for_two_complete_physical_branches(self):
        w=World();seq=AtomicSequence(w.env,program(2),0)
        w.hold();tick(w,seq);w.poses['object'][2]=.04;tick(w,seq)
        self.assertNotIn('finish',seq.sessions)
        w.hold(label='other');tick(w,seq);w.poses['other'][2]=.04;tick(w,seq)
        self.assertEqual(seq.summary()['choices'][0]['completed_branches'],[0,1])
        self.assertIn('finish',seq.sessions)
        self.assertFalse(next(r for r in seq.summary()['stages'] if r['stage_id']=='c')['required'])

    def test_simultaneous_excess_branches_are_not_arbitrarily_selected(self):
        w=World();seq=AtomicSequence(w.env,program(1),0)
        w.hold();w.hold(label='other');tick(w,seq)
        w.poses['object'][2]=w.poses['other'][2]=.04;tick(w,seq)
        self.assertEqual(seq.summary()['choices'][0]['status'],'ambiguous_completion')
        self.assertEqual(seq.summary()['choices'][0]['completed_branches'],[0,1])
        self.assertNotIn('finish',seq.sessions)
        self.assertNotIn('choose',seq.completed)

    def test_invalid_count_overlap_cross_branch_dependencies_and_cycles_fail(self):
        with self.assertRaises(ValueError):AtomicChoice.from_dict({'id':'x','branches':[['a'],['a']],'required':1})
        with self.assertRaises(ValueError):AtomicChoice.from_dict({'id':'x','branches':[['a'],['b']],'required':2})
        p=program()
        deps=p.dependencies();deps['finish']=['a']
        with self.assertRaisesRegex(ValueError,'external successors'):replace(p,stage_dependencies=deps)
        deps=p.dependencies();deps['b']=['a']
        with self.assertRaisesRegex(ValueError,'external successors'):replace(p,stage_dependencies=deps)
        deps=p.dependencies();deps['a']=['choose']
        with self.assertRaisesRegex(ValueError,'cycle'):replace(p,stage_dependencies=deps)

    def test_repeat_expansion_rewrites_choice_terminal_and_branch_identity(self):
        p=program();p=replace(p,repeat_counts={'a':{'label':'num0','min':1,'max':9}})
        w=World();w.env.scene_manager.layout_manager.get_instance_metadata=lambda **kw:{'model_id':2}
        bound=p.bind(w.env,0)
        self.assertEqual(bound.choices[0].branches[0],('a__1','a__2'))
        self.assertEqual(bound.dependencies()['choose'],['a__2','b','c'])
        self.assertEqual(bound.dependencies()['a__2'],['a__1'])
        with self.assertRaisesRegex(ValueError,'without scene gates or choices'):
            replay_prefix(bound,bound.stages[-1],None,None,None)
