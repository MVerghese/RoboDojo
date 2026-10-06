from copy import deepcopy
import unittest
import numpy as np
from task.atomic.geometry import evaluate_geometry
from task.atomic.segments import segment_metrics
from task.atomic.session import AtomicSession
from task.atomic.spec import AtomicStage
from test_atomic_physical_runtime import World
from test_atomic_materials import attach_material


class SegmentTests(unittest.TestCase):
    def test_finite_segments_reject_infinite_line_and_midpoint_proxies(self):
        a=[[0,0,0],[1,0,0]];b=[[2,-1,0],[2,1,0]]
        self.assertAlmostEqual(segment_metrics(a,b)['segment_gap_m'],1)
        c=[[-.5,0,0],[.5,0,0]];d=[[0,-.5,0],[0,.5,0]]
        self.assertEqual(segment_metrics(c,d)['segment_gap_m'],0)
        self.assertAlmostEqual(segment_metrics(c,d)['segment_hausdorff_m'],.5)
        self.assertAlmostEqual(segment_metrics(c,d)['segment_axis_angle_rad'],np.pi/2)
        self.assertEqual(segment_metrics(c,c[::-1])['segment_hausdorff_m'],0)
        with self.assertRaises(ValueError):segment_metrics([[0,0,0]]*2,d)

    def test_live_deformation_preserves_actual_frozen_endpoint_evidence(self):
        w=World();label,data=attach_material(w,'cloth',[5,8,11],[[0,0,0],[1,0,0],[0,1,0]])
        data['triangles']=[[5,8,11]]
        w.env.scene_manager.layout_manager.get_instance_metadata=lambda **kw:{'passive':{'functional':{'a':{'id':[5]},'b':{'id':[8]}}}}
        c={'kind':'cloth_line_frame','label':label,'tag_a':'a','tag_b':'b','normal_tag':'a'}
        definition={'id':'line','family':'fold','instruction':'Preserve the material endpoint segment',
            'success_checks':[{'name':'is_atomic_interaction','args':{}}],
            'geometry':[{'id':'segment','slot':'crease','kind':'spatial_relation','relation_scope':'segments',
                'measurement':c,'reference':{**c,'time':'stage_start'},'expected':'coincides_with_segment',
                'tolerance':.01,'event':{'kind':'attempt_end'},'track_closest':False}]}
        s=AtomicSession(w.env,AtomicStage.from_dict(definition),0)
        data['positions_world'][1]=[0,1,0];data['positions_world'][2]=[-1,0,0]
        s.finalize();row=s.summary()['geometry']['segment']
        self.assertFalse(row['result']['passed']);self.assertAlmostEqual(row['result']['error'],1)
        self.assertEqual(row['reference_state']['endpoints_m'],[[0,0,0],[1,0,0]])
        result=evaluate_geometry(row['condition'],row['measured_state'],row['reference_state']).as_dict()
        self.assertEqual(result,row['result'])
        bad=deepcopy(definition);bad['geometry'][0]['relation_scope']='points'
        with self.assertRaisesRegex(ValueError,'segment'):AtomicStage.from_dict(bad)


if __name__=='__main__':unittest.main()
