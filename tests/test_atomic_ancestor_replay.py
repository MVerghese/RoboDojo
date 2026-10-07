"""Single ancestry in a concrete DAG can replay without inventing peer states."""
from dataclasses import replace
import unittest
from task.atomic.replay import prefix_program, validate_start_boundary
import test_atomic_timed_replay as timed
from test_atomic_prefix_recognition import method


def with_peer(program):
    peer=replace(program.stages[0],id='independent_peer')
    return replace(program,stages=(peer,*program.stages),stage_dependencies={
        'independent_peer':[],'a':[],'b':['a'],'c':['b']})


class AncestorReplayTests(unittest.TestCase):
    def test_route_preserves_original_stage_definitions_and_does_not_rewrite_trace(self):
        p,t=timed.fixture();p=with_peer(p);before=t.__dict__.copy()
        route=prefix_program(p,p.stage('c'))
        self.assertEqual([s.id for s in route.stages],['a','b','c'])
        self.assertEqual(route.stages,p.stages[1:]);self.assertEqual(t.__dict__,before)
        boundary=validate_start_boundary(p,p.stage('c'),t)
        self.assertEqual(boundary['prefix_stage_ids'],['a','b','c'])
        self.assertEqual(boundary['physics_substeps'],6)

    def test_actual_evaluator_replays_every_control_and_checks_only_required_ancestry(self):
        w,phases,resets=timed.TimedReplayTests().world();w.env.atomic_program=with_peer(w.env.atomic_program)
        method('_start_atomic_stage')(w.env)
        self.assertEqual(phases,['a','a','b','b','b',None])
        self.assertEqual(w.env.take_action_cnt,[0]);self.assertEqual(w.contacts.steps,6)
        self.assertEqual([s['stage_id'] for s in w.env._atomic_start_evidence['prefix_stage_validation']],['a','b'])
        self.assertTrue(w.env._atomic_start_evidence['physics_boundary_verified'])

    def test_merged_dependency_is_not_reduced_to_one_convenient_parent(self):
        p,t=timed.fixture();p=with_peer(p);deps=p.dependencies();deps['c']=['a','b'];p=replace(p,stage_dependencies=deps)
        with self.assertRaisesRegex(ValueError,'merged graph starts'):
            validate_start_boundary(p,p.stage('c'),t)

    def test_lost_hold_on_required_route_still_blocks_replay(self):
        w,_,resets=timed.TimedReplayTests().world(lose_hold=True);w.env.atomic_program=with_peer(w.env.atomic_program)
        with self.assertRaisesRegex(ValueError,'replay diverged'):method('_start_atomic_stage')(w.env)
        self.assertEqual(resets,[])

    def test_route_root_must_have_an_initial_scene_start(self):
        p,t=timed.fixture();p=with_peer(p);t=replace(t,stage_starts={'a':1})
        with self.assertRaisesRegex(ValueError,'first atomic stage at action 0'):
            validate_start_boundary(p,p.stage('c'),t)

if __name__=='__main__':unittest.main()
