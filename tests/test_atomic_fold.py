from copy import deepcopy
import unittest
from task.atomic.fold import ClothFoldObserver

C={'min_relative_lift_m':.02,'min_closure_m':.04,'min_bend_rad':.5,'max_region_distance_m':.03,
   'min_layer_gap_m':.001,'max_layer_gap_m':.025,'min_crease_length_fraction':.8,
   'settle_steps':3,'max_position_step_m':.002,'max_angle_step_rad':.1,
   'max_settle_displacement_m':.003,'max_settle_angle_rad':.15}


def state(x=.1,z=0.,folded=False):
    return {'moving':[x,0,z],'target':[0,0,0],'crease_a':[0,-.05,0],'crease_b':[0,.05,0],
            'moving_frame':[x,0,z,*([0,1,0,0] if folded else [1,0,0,0])],
            'stationary_frame':[0,0,0,1,0,0,0]}


class FoldTests(unittest.TestCase):
    def test_requires_relative_lift_deformation_bend_layer_and_settling(self):
        o=ClothFoldObserver(C,state())
        self.assertFalse(o.observe(state(.005,.003,True)))  # Endpoint alone is insufficient.
        self.assertFalse(o.observe(state(.1,.05)))
        self.assertFalse(o.observe(state(.005,.003,True)))
        self.assertFalse(o.observe(state(.005,.003,True)))
        self.assertTrue(o.observe(state(.005,.003,True)))
        self.assertIn('not measured',o.evidence['evidence_semantics'])

    def test_rigid_translation_or_an_initially_folded_garment_is_not_a_new_fold(self):
        for initial in [state(),state(.005,.003,True)]:
            o=ClothFoldObserver(C,initial)
            for i in range(5):
                current=deepcopy(initial)
                for k in ('moving','target','crease_a','crease_b'):current[k][2]+=.1
                self.assertFalse(o.observe(current))

    def test_slow_cumulative_drift_cannot_complete_settling(self):
        c=C|{'settle_steps':5};o=ClothFoldObserver(c,state());o.observe(state(.1,.05))
        for i in range(5):
            current=state(.005,.003,True)
            for k in ('moving','target','crease_a','crease_b'):current[k][1]+=i*.001
            self.assertFalse(o.observe(current))


if __name__=='__main__':unittest.main()
