"""Stage-success geometry must use the same qualified completion as actions."""
from copy import deepcopy
import unittest
from task.atomic.session import AtomicSession
from task.atomic.spec import AtomicStage
from task.atomic.completion_validation import validate_stage_success
from scripts.atomic.audit_scores import audit_atomic,validate_cached_recognition
from test_atomic_recognition import environment,config
from test_atomic_physical_runtime import World,recognition


def condition():
    return {'id':'completion_pose','slot':'goal','kind':'point',
        'measurement':{'kind':'object_position','label':'object'},'expected':[0,0,.12],
        'tolerance':.002,'event':{'kind':'stage_success'},'track_closest':False}


class CompletionEventTests(unittest.TestCase):
    def complete_pick(self):
        env,pose,contacts=environment();s=AtomicSession(env,AtomicStage.from_dict(config([condition()])),0)
        contacts.present=True;s.observe_events();pose[2]=.12;contacts.steps=1
        self.assertTrue(s.step());return s

    def test_native_goal_ballistic_motion_and_later_touch_do_not_latch_completion_geometry(self):
        env,pose,contacts=environment();s=AtomicSession(env,AtomicStage.from_dict(config([condition()])),0)
        pose[2]=.12;contacts.steps=1
        self.assertFalse(s.step());self.assertTrue(s.goal_success);self.assertEqual(s.results,{})
        contacts.present=True;contacts.steps=2;s.observe_events();contacts.steps=3
        self.assertFalse(s.step());self.assertEqual(s.results,{})
        pose[2]=.23;contacts.steps=4;self.assertTrue(s.step())
        row=s.results['completion_pose'];self.assertEqual(row['measurement_physics_step'],4)
        self.assertEqual(row['measured_state'],[0.,0.,.23]);self.assertFalse(row['result']['passed'])
        self.assertEqual(validate_stage_success(s.summary(),row)['status'],'consistent_evidence')

    def test_supported_push_waits_for_actual_supported_contact_coupled_motion(self):
        env,pose,contacts=environment();env.reward_manager.call_func_parser=lambda check,env_idx:1.
        c=config([condition()],family='push');c['success_checks']=[{'name':'is_test_goal','args':{}}]
        s=AtomicSession(env,AtomicStage.from_dict(c),0);contacts.present=True;contacts.support=False
        for step,x in [(1,.03),(2,.06)]:
            contacts.steps=step;pose[0]=x;self.assertFalse(s.step());self.assertEqual(s.results,{})
        contacts.support=True;contacts.steps=3;s.observe_events();pose[0]=.09;contacts.steps=4
        self.assertTrue(s.step());self.assertEqual(s.results['completion_pose']['measurement_physics_step'],4)

    def test_maintained_hold_failure_blocks_endpoint_geometry_as_well_as_action(self):
        w=World();stage=AtomicStage.from_dict({'id':'place','family':'place','instruction':'Place',
            'success_checks':[{'name':'is_test_goal','args':{}}],'geometry':[condition()],
            'maintained_holds':[{'label':'other','arm':'right','min_finger_bodies':2}]})
        s=AtomicSession(w.env,stage,0);self.assertFalse(w.tick(s));self.assertTrue(s.goal_success)
        self.assertTrue(s.maintained_hold_failures);self.assertEqual(s.results,{})

    def test_native_place_goal_waits_for_transport_release_and_settling(self):
        w=World();stage=AtomicStage.from_dict({'id':'place','family':'place','instruction':'Place',
            'success_checks':[{'name':'is_test_goal','args':{}}],
            'recognition':recognition('supported_release'),'geometry':[condition()]})
        s=AtomicSession(w.env,stage,0);self.assertFalse(w.tick(s));self.assertEqual(s.results,{})
        w.hold();w.tick(s);w.poses['object'][0]=.02;w.tick(s);self.assertEqual(s.results,{})
        w.release();w.tick(s,2);self.assertEqual(s.results,{})
        self.assertTrue(w.tick(s));row=s.results['completion_pose']
        self.assertEqual(row['measurement_physics_step'],s.summary()['physical_events']['settled']['physics_step'])
        self.assertEqual(validate_stage_success(s.summary(),row)['status'],'consistent_evidence')

    def test_corrupted_completion_metadata_excludes_cached_geometry_without_rewriting_policy_outcome(self):
        s=self.complete_pick();raw=s.summary();row=raw['geometry']['completion_pose']
        for change in [lambda e:e.__setitem__('native_endpoint_passed',False),
                lambda e:e.__setitem__('physical_interaction_observed',False),
                lambda e:e.__setitem__('maintained_hold_failure_count',1),
                lambda e:e.__setitem__('physics_step',0),
                lambda e:e.__setitem__('recognition_kind','another_kind'),
                lambda e:e.__setitem__('current_hold_observed',False),
                lambda e:e.__setitem__('contact_coupled_displacement_m',[0,0,.03])]:
            broken=deepcopy(raw);change(broken['geometry']['completion_pose']['event_evidence'])
            output=audit_atomic(broken)
            self.assertEqual(output['conditions']['completion_pose']['status'],'invalid_stage_success_witness')
            self.assertTrue(output['action_success'])
            cached=audit_atomic(raw);cached['episode']='0'
            validate_cached_recognition({'native_results':[{'details':{'0':{'atomic':broken}}}]},[cached])
            self.assertEqual(cached['conditions']['completion_pose']['status'],'invalid_stage_success_witness')

    def test_historical_endpoint_only_event_stays_partial_without_relabeling_it(self):
        s=self.complete_pick();raw=s.summary();raw['geometry']['completion_pose']['event_evidence']=None
        raw['action_success']=False
        output=audit_atomic(raw);row=output['conditions']['completion_pose']
        self.assertEqual(row['status'],'reproduced')
        self.assertEqual(row['stage_success_witness']['status'],'partial_evidence')
        self.assertFalse(output['action_success'])


if __name__=='__main__':unittest.main()
