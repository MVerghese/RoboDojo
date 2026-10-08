"""Valid interrupted impacts remain measurable without becoming completed strike scores."""
from copy import deepcopy
import unittest
import test_atomic_strike_validation as retained
from scripts.atomic.aborted_strike_diagnostics import audit_aborted_strikes
from scripts.atomic.validate_strike_evidence import validate_strike
from task.atomic.geometry import evaluate_geometry


def fixture():
    stage=retained.retained_strike();event=stage['physical_events']['impact'];event['attempt_index']=0
    condition={'id':'contact','slot':'contact','kind':'relative_displacement',
        'measurement':{'kind':'object_contact_points','label':'mallet','other_label':'keys'},
        'reference':{'kind':'functional_point','label':'keys','tag':'hit_0','type':'passive'},
        'expected':[.003,0,0],'tolerance':.008,'event':{'kind':'recognition_event','name':'impact'}}
    measured={'points':[[0,0,0]],'position':[0,0,0]};reference=[0,0,0,1,0,0,0]
    geometry={'contact':{'condition':condition,'event':condition['event'],'event_evidence':deepcopy(event),
        'measurement_physics_step':101,'measured_state':measured,'reference_state':reference,
        'measurement_source':None,'result':evaluate_geometry(condition,measured,reference).as_dict()}}
    stage.update(stage_id='strike',family='touch_with_tool',geometry_coverage=0,action_success=False,
        conditions=[condition],physical_events={},geometry={},trajectories={})
    stage['aborted_recognition_attempts']=[{'attempt_index':0,'reason':'physical_interval_invalidated',
        'aborted_physics_step':106,'physical_events':{'impact':event},'geometry':geometry}]
    return stage


class AbortedStrikeTests(unittest.TestCase):
    def test_interruptions_retain_partial_geometry_without_completing_or_mutating_the_stage(self):
        stage=fixture();before=deepcopy(stage);rows=audit_aborted_strikes(stage)
        self.assertEqual(stage,before);self.assertFalse(stage['action_success'])
        self.assertEqual(validate_strike(stage)['status'],'unobserved')
        self.assertEqual(rows[0]['impact_validation']['status'],'consistent_evidence')
        self.assertEqual(rows[0]['conditions']['contact']['status'],'partial_evidence')
        self.assertAlmostEqual(rows[0]['conditions']['contact']['components']['displacement_m'],.003)

    def test_stale_force_mismatched_attempt_and_wrong_measurement_clock_exclude_diagnostics(self):
        for change in ('force','attempt','measurement'):
            stage=fixture();a=stage['aborted_recognition_attempts'][0]
            if change=='force':a['physical_events']['impact']['tool_target_contacts'][0]['force_report_physics_step']=100
            elif change=='attempt':a['attempt_index']=1
            else:a['geometry']['contact']['measurement_physics_step']=102
            row=audit_aborted_strikes(stage)[0]
            self.assertEqual(row['conditions']['contact']['components'],{})
            self.assertFalse(stage['action_success'])
