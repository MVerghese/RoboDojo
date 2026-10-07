"""A reproduced on-top score cannot conceal corrupt support force witnesses."""
from copy import deepcopy
import unittest
from task.atomic.support_validation import validate_support_witness
from test_atomic_persistent_support import world


class SupportValidationTests(unittest.TestCase):
    def measured(self, reverse=False, oblique=False):
        backend, _ = world()
        row = backend.rows[0]
        if oblique: row['normal_world'] = [.920, 0, .391]
        if reverse:
            for key in ('actor', 'collider'): row[key+'0'], row[key+'1'] = row[key+'1'], row[key+'0']
            for key in ('normal_world', 'impulse'): row[key] = [-x for x in row[key]]
        return {'support_contact': True, 'support_contact_evidence': backend.support_evidence('object',['support'],0)}

    def test_oblique_and_reversed_actor_order_reproduce_force_signs(self):
        for reverse in (False, True):
            self.assertEqual(validate_support_witness(self.measured(reverse, True))['status'], 'consistent_support_evidence')

    def test_corrupt_body_force_projection_and_flag_are_rejected(self):
        for kind in ('body', 'normal', 'impulse', 'projection', 'flag'):
            m = self.measured(); row = m['support_contact_evidence']['contacts'][0]
            if kind == 'body': row['actor1'] = row['collider1'] = '/env/unrelated'
            elif kind == 'normal': row['normal_world'] = [0,0,-1]
            elif kind == 'impulse': row['impulse'] = [0,0,-.001]
            elif kind == 'projection': row['axial_impulse_ns'] = 1
            else: m['support_contact'] = False
            with self.subTest(kind=kind):
                self.assertEqual(validate_support_witness(m)['status'], 'inconsistent_support_evidence')

    def test_missing_historical_raw_data_and_sleep_history_are_partial(self):
        self.assertEqual(validate_support_witness({'support_contact':True})['status'], 'partial_support_evidence')
        m = self.measured(); m['support_contact_evidence']['support_evidence_kind'] = 'persistent_unchanged_contact'
        self.assertEqual(validate_support_witness(m)['status'], 'partial_support_evidence')

    def test_cached_arithmetic_scores_receive_independent_support_rejection(self):
        from scripts.atomic.audit_scores import validate_cached_recognition
        measured = self.measured()
        measured['support_contact_evidence']['contacts'][0]['impulse'] = [0,0,-.001]
        stage = {'stage_id':'place', 'geometry':{'support':{
            'condition':{'expected':'on_top'}, 'measured_state':measured}}}
        report = {'native_results':[{'details':{'0':{'atomic_sequence':{'stages':[stage]}}}}]}
        row = {'episode':'0','stage_id':'place','conditions':{'support':{'status':'reproduced'}}}
        validate_cached_recognition(report, [row])
        condition = row['conditions']['support']
        self.assertEqual(condition['status'], 'invalid_support_witness')
        self.assertEqual(condition['numerical_reproduction_status'], 'reproduced')


if __name__ == '__main__': unittest.main()
