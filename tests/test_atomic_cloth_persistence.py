"""A folded endpoint cannot alone establish settled physical bending."""
from copy import deepcopy
import unittest
import numpy as np

from test_atomic_cloth_bending import IDS, P, T, THRESHOLDS, folded
import test_atomic_cloth_bending as fixtures
from task.atomic.cloth_bending import ClothBendingTopology, ClothEndpointHistory, measure_bending_persistence
from task.atomic.sequence import AtomicSequence
from unittest.mock import patch
from scripts.atomic.analyze_cloth_bending import analyze_report, compact_diagnostics


def witness(positions):
    o=ClothBendingTopology(IDS,P,T)
    endpoint={**o.measure(IDS,positions[-1],**THRESHOLDS),'endpoint_positions':positions[-1].tolist()}
    samples=[]
    for i,p in enumerate(positions):
        step=i*4
        samples.append({'physics_step':step,'dt_s':.01,'garments':{'cloth':{
            'status':'captured','ids':IDS,'positions_world':p.tolist(),'physics_step':step,
            'coordinate_frame':'environment_local_world','length_unit':'metres',
            'topology_sha256':o.topology_sha256}}})
    return o,endpoint,{'sampling_stride_steps':4,'samples':samples}


class ClothPersistenceTests(unittest.TestCase):
    def test_stable_candidate_requires_history_and_reports_actual_duration_and_drift(self):
        o,e,h=witness([folded() for _ in range(8)])
        r=measure_bending_persistence(o,e,h,'cloth')
        self.assertEqual(r['status'],'observed_sampled_stable_bending')
        self.assertEqual(r['stable_candidate_count'],1)
        self.assertAlmostEqual(r['duration_s'],.28)
        self.assertEqual(r['components'][0]['max_vertex_drift_m'],0.)
        self.assertEqual(measure_bending_persistence(o,e,None,'cloth')['status'],'unavailable_temporal_witness')
        short=deepcopy(h);short['samples']=short['samples'][-2:]
        self.assertEqual(measure_bending_persistence(o,e,short,'cloth')['reason'],'mesh_history_duration_below_threshold')

    def test_rigid_drift_or_late_bending_cannot_pass_sampled_stability(self):
        o,e,h=witness([folded()+[i*.001,0,0] for i in range(8)])
        r=measure_bending_persistence(o,e,h,'cloth')
        self.assertEqual(r['status'],'no_sampled_stable_candidates')
        self.assertAlmostEqual(r['components'][0]['max_vertex_drift_m'],.007)
        o,e,h=witness([P.copy() for _ in range(7)]+[folded()])
        r=measure_bending_persistence(o,e,h,'cloth')
        self.assertFalse(r['components'][0]['persistent_new_bending'])
        self.assertFalse(r['components'][0]['within_sampled_stability_bounds'])

    def test_time_topology_identity_and_endpoint_mismatch_fail_explicitly(self):
        o,e,h=witness([folded() for _ in range(8)])
        mutations=[lambda h:h['samples'][2].update(physics_step=99),
                   lambda h:h['samples'][2].update(dt_s=.02),
                   lambda h:h['samples'][2]['garments']['cloth'].update(topology_sha256='wrong'),
                   lambda h:h['samples'][2]['garments']['cloth'].update(ids=[7,9,11,99]),
                   lambda h:h['samples'][-1]['garments']['cloth'].update(positions_world=P.tolist())]
        for mutate in mutations:
            altered=deepcopy(h);mutate(altered)
            self.assertEqual(measure_bending_persistence(o,e,altered,'cloth')['status'],'invalid_temporal_witness')

    def test_live_probe_is_bounded_deduplicated_and_collected_before_reset(self):
        w,data,program=fixtures.ClothBendingTests().world();w.env.dt=.01
        with patch.dict('os.environ',{'ATOMIC_CLOTH_BENDING_PROBE':'1'}):seq=AtomicSequence(w.env,program,0)
        data['positions_world']=folded()
        for step in range(60):
            w.contacts.steps=step;seq.observe_events();seq.observe_events()
        seq.finalize();summary=seq.summary()
        samples=summary['cloth_bending_capture']['temporal_history']['samples']
        self.assertEqual(len(samples),8)
        self.assertEqual(samples[-1]['physics_step'],59)
        report={'native_results':[{'details':{'0':{'atomic_sequence':summary}}}]}
        result=analyze_report(report,THRESHOLDS)
        self.assertEqual(result[0]['temporal_persistence']['status'],'observed_sampled_stable_bending')
        compact=compact_diagnostics(result)[0]
        self.assertNotIn('components',compact['temporal_persistence'])
        self.assertEqual(compact['max_candidate_vertex_drift_m'],0.)
        data['positions_world']=P.copy();seq.finalize()
        self.assertEqual(len(seq.summary()['cloth_bending_capture']['temporal_history']['samples']),8)


if __name__=='__main__':unittest.main()
