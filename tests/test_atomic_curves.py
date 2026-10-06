"""Edge-interior witnesses and calibrated persistent material paths."""
import math
import unittest
from copy import deepcopy
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
import numpy as np

from task.atomic.curves import curve_metrics, directed_hausdorff


class CurveTests(unittest.TestCase):
    def test_fractional_topology_cannot_be_truncated_into_a_valid_material_path(self):
        from task.atomic.cloth_calibration import material_edge_path
        from task.atomic.materials import material_state
        from test_atomic_physical_runtime import World
        from test_atomic_materials import attach_material
        w = World();label,data = attach_material(w,'cloth',[0,1,2],[[0,0,0],[1,0,0],[0,1,0]])
        for topology in ([[0.,1.5,2.]],[[0,1,3]],[[0,1,1]]):
            data['triangles'] = topology
            with self.assertRaisesRegex(RuntimeError,'topology'):material_state(w.env,label,'cloth',0)
        with self.assertRaises(ValueError):
            material_edge_path(data['positions_world'],[[0.,1.5,2.]],0,2,'a'*64)

    def test_material_curve_binding_follows_interior_deformation_and_preserves_frozen_reference(self):
        from task.atomic.cloth_calibration import material_edge_path
        from task.atomic.spec import AtomicStage, _validate_selector
        from task.atomic.session import AtomicSession
        from test_atomic_physical_runtime import World
        from test_atomic_materials import attach_material
        from scripts.atomic.audit_scores import audit_atomic
        w=World();w.goal=False
        label,data=attach_material(w,'cloth',[0,1,2,3],[[0,0,0],[.01,0,0],[.02,0,0],[.01,.01,0]])
        data['triangles']=[[0,1,3],[1,2,3]]
        lm=w.env.scene_manager.layout_manager;obj=lm.get_scene_object(0,label)
        lm.get_instance_metadata=lambda **kw:{'model_name':'shirt','model_id':1}
        with TemporaryDirectory() as directory:
            path=Path(directory)/'object.usdz';path.write_bytes(b'actual material curve asset');obj.usd_path=str(path)
            row=material_edge_path(data['positions_world'],data['triangles'],0,2,
                                  hashlib.sha256(path.read_bytes()).hexdigest())
            self.assertEqual(row['ids'],[0,1,2])
            selected={'kind':'cloth_model_curve','label':label,'models':{'shirt/00001':row}}
            _validate_selector(selected,'curve')
            condition={'id':'material_curve','slot':'crease','kind':'spatial_relation','relation_scope':'curves',
                'measurement':selected,'reference':{**deepcopy(selected),'time':'stage_start'},
                'expected':'coincides_with_curve','tolerance':.002,'event':{'kind':'attempt_end'}}
            stage=AtomicStage.from_dict({'id':'fold','family':'fold','instruction':'Fold the material',
                'success_checks':[{'name':'is_test_goal','args':{}}],'geometry':[condition]})
            s=AtomicSession(w.env,stage,0)
            data['positions_world'][1,2]=.006  # Endpoints/chord stay exactly unchanged.
            s.finalize()
            score=s.summary()['geometry']['material_curve']['result']
            self.assertFalse(score['passed']);self.assertAlmostEqual(score['components']['curve_hausdorff_m'],.006)
            self.assertEqual(audit_atomic(s.summary())['conditions']['material_curve']['status'],'reproduced')
            from task.atomic.materials import resolve_material
            broken=deepcopy(selected);broken['models']['shirt/00001']['ids']=[0,2]
            with self.assertRaisesRegex(RuntimeError,'connected'):resolve_material(w.env,broken,0)
            broken=deepcopy(selected);broken['models']['shirt/00001']['topology_sha256']='a'*64
            with self.assertRaisesRegex(RuntimeError,'topology'):resolve_material(w.env,broken,0)
            path.write_bytes(b'changed physical asset')
            with self.assertRaisesRegex(RuntimeError,'asset file'):resolve_material(w.env,selected,0)
            invalid=deepcopy(condition);invalid['kind']='relative_orientation';invalid['expected']=[1,0,0,0]
            with self.assertRaises(ValueError):AtomicStage.from_dict({'id':'fold','family':'fold','instruction':'Fold',
                'success_checks':[{'name':'is_test_goal','args':{}}],'geometry':[invalid]})

    def test_material_path_cannot_jump_to_a_nearby_disconnected_layer(self):
        from task.atomic.cloth_calibration import material_edge_path
        v=[[0,0,0],[1,0,0],[0,1,0],[0,0,.001],[1,0,.001],[0,1,.001]]
        with self.assertRaisesRegex(ValueError,'disconnected'):
            material_edge_path(v,[[0,1,2],[3,4,5]],0,3,'a'*64)

    def test_same_vertices_different_route_has_nonzero_continuous_hausdorff(self):
        a=np.array([[0,0,0],[1,1,0],[0,1,0],[1,0,0]],dtype=float)
        b=np.array([[0,0,0],[0,1,0],[1,1,0],[1,0,0]],dtype=float)
        self.assertEqual(set(map(tuple,a)),set(map(tuple,b)))
        result=curve_metrics(a,b)
        self.assertEqual(result['curve_gap_m'],0.)
        self.assertAlmostEqual(result['curve_hausdorff_m'],.5)
        self.assertAlmostEqual(directed_hausdorff(a,b),.5)

    def test_directed_maximum_can_be_inside_an_edge_with_zero_endpoint_distances(self):
        source=[[-1,0,0],[1,0,0]]
        target=[[-1,0,0],[0,1,0],[1,0,0]]
        self.assertAlmostEqual(directed_hausdorff(source,target),math.sqrt(.5))
        self.assertAlmostEqual(directed_hausdorff(target,source),1.)

    def test_translation_rotation_and_reversal_preserve_distance(self):
        a=np.array([[0,0,0],[.03,.02,.01],[.06,0,0]])
        b=np.array([[0,0,.01],[.03,.02,.02],[.06,0,.01]])
        original=curve_metrics(a,b)
        r=np.array([[0,0,1],[1,0,0],[0,1,0]])
        transformed=curve_metrics(a@r+[2,3,4],b[::-1]@r+[2,3,4])
        for key in original:self.assertAlmostEqual(original[key],transformed[key],places=12)
        self.assertEqual(curve_metrics(a,a)['curve_hausdorff_m'],0.)

    def test_degenerate_or_nonfinite_edges_are_not_curves(self):
        for value in ([[0,0,0]],[[0,0,0],[0,0,0]],[[0,0,0],[float('nan'),0,0]]):
            with self.assertRaises(ValueError):directed_hausdorff(value,[[0,0,0],[1,0,0]])

    def test_continuous_maximum_respects_independent_dense_lipschitz_bounds_at_multiple_scales(self):
        # Distance to a set is 1-Lipschitz: dense samples bound the true maximum
        # above and below by half the largest source sampling interval.
        rng = np.random.default_rng(831)
        for scale in (1e-6, 1., 1e6):
            for _ in range(4):
                source = rng.normal(size=(5,3))*scale
                target = rng.normal(size=(4,3))*scale
                sampled = np.concatenate([a+np.linspace(0,1,1001)[:,None]*(b-a)
                                          for a,b in zip(source,source[1:])])
                distances = []
                for a,b in zip(target,target[1:]):
                    edge = b-a
                    projection = np.clip((sampled-a)@edge/(edge@edge),0,1)
                    distances.append(np.linalg.norm(sampled-a-projection[:,None]*edge,axis=1))
                lower = float(np.min(distances,axis=0).max())
                bound = np.linalg.norm(np.diff(source,axis=0),axis=1).max()/2000
                measured = directed_hausdorff(source,target)
                self.assertGreaterEqual(measured+scale*1e-12,lower)
                self.assertLessEqual(measured,lower+bound+scale*1e-12)
