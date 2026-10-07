"""Button cycles retain an actual unpressed start, cap contact and release."""
from copy import deepcopy
import unittest
from test_atomic_dynamic_runtime import button_world,button_stage
from task.atomic.session import AtomicSession
from task.atomic.recognition_validation import validate_recognition_window


def completed_cycle(idle=True):
    w=button_world();s=AtomicSession(w.env,button_stage(),0)
    w.joint=1.
    if idle:w.tick(s);w.hold(fingers=1);w.joint=.8;w.tick(s)
    else:w.hold(fingers=1);w.tick(s,2)
    w.joint=.2;w.tick(s,2);w.release();w.joint=1.;assert w.tick(s)
    return s.summary()


class ButtonValidationTests(unittest.TestCase):
    def test_idle_and_contact_unpressed_starts_both_reproduce_boundary_evidence(self):
        for idle in (True,False):
            self.assertEqual(validate_recognition_window(completed_cycle(idle))['status'],
                             'consistent_boundary_evidence')

    def test_changed_start_time_ratio_contact_interval_or_release_is_invalid(self):
        s=completed_cycle()
        mutations=[lambda s:s['physical_events']['press']['initial_unpressed_sample'].update(physics_step=0),
            lambda s:s['physical_events']['press']['initial_unpressed_sample']['joint_state'].update(position=.1),
            lambda s:s['physical_events']['press']['arming_contact'].update(contact_interval_start_step=99),
            lambda s:s['physical_events']['release'].update(robot_touching=True)]
        for mutate in mutations:
            altered=deepcopy(s);mutate(altered)
            result=validate_recognition_window(altered)
            self.assertEqual(result['status'],'inconsistent_evidence',result)
            self.assertTrue(result['invalid_event_names'])

    def test_legacy_missing_raw_start_stays_partial_and_incomplete_cycle_unobserved(self):
        s=completed_cycle()
        for e in s['physical_events'].values():
            for key in ('initial_unpressed_sample','arming_contact','joint_state','robot_touching'):e.pop(key,None)
        self.assertEqual(validate_recognition_window(s)['status'],'partial_evidence')
        del s['physical_events']['cycle']
        self.assertEqual(validate_recognition_window(s)['status'],'unobserved')


if __name__=='__main__':unittest.main()
