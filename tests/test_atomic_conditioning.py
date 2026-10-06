"""Invalid conditioning must fail before scheduling; landmarks stay explicit."""
from types import SimpleNamespace
import unittest
import numpy as np

from task.atomic.geometry import evaluate_geometry, _rotation
from task.atomic.session import AtomicSession
from task.atomic.spec import AtomicStage


def condition(kind):
    value = {'id': 'geometry', 'slot': 'goal', 'kind': kind,
             'measurement': {'kind': 'object_pose', 'label': 'object'},
             'reference': {'kind': 'object_pose', 'label': 'landmark'}, 'tolerance': .01}
    value['expected'] = {'point': [0, 0, 0], 'relative_displacement': [0, 0, 0],
                         'pose': {'position': [0, 0, 0], 'orientation': [1, 0, 0, 0]},
                         'relative_orientation': [1, 0, 0, 0], 'spatial_relation': 'above'}[kind]
    if kind == 'spatial_relation':
        value['relation_scope'] = 'objects'
    if kind == 'pose':
        value['angle_tolerance_rad'] = .1
    return value


def load(value):
    return AtomicStage.from_dict({'id': 'stage', 'family': 'place', 'instruction': 'Place object.',
                                 'success_checks': [{'name': 'is_lift', 'args': {'label': 'object'}}],
                                 'geometry': [value]})


def cube(center=(0, 0, 0), half=.05, q=(1, 0, 0, 0)):
    points = np.array([[x, y, z] for x in (-half, half) for y in (-half, half) for z in (-half, half)])
    triangles = [[0, 1, 3], [0, 3, 2], [4, 6, 7], [4, 7, 5], [0, 4, 5], [0, 5, 1],
                 [2, 3, 7], [2, 7, 6], [0, 2, 6], [0, 6, 4], [1, 5, 7], [1, 7, 3]]
    return {'position': list(center), 'orientation': list(q),
            'vertices': (points @ _rotation(q).T + center).tolist(), 'triangles': triangles,
            'geometry_representation': 'test cube triangles'}


class ConditioningAuditTests(unittest.TestCase):
    def test_all_factor_inputs_reject_nonfinite_values_before_execution(self):
        for kind in ('point', 'pose', 'relative_displacement', 'relative_orientation', 'spatial_relation'):
            load(condition(kind))
            for invalid in (float('nan'), float('inf'), -1, True):
                with self.subTest(kind=kind, tolerance=invalid), self.assertRaises(ValueError):
                    load({**condition(kind), 'tolerance': invalid})
        for kind in ('point', 'relative_displacement'):
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, 'finite 3-vector'):
                load({**condition(kind), 'expected': [0, 0, float('nan')]})
        with self.assertRaisesRegex(ValueError, 'nonzero'):
            load({**condition('relative_orientation'), 'expected': [0, 0, 0, 0]})
        with self.assertRaisesRegex(ValueError, 'event threshold'):
            load({**condition('point'), 'event': {'kind': 'first_motion', 'label': 'object', 'threshold': float('nan')}})

    def test_relative_frames_and_pose_measurements_cannot_be_invented(self):
        for kind in ('relative_displacement', 'relative_orientation', 'spatial_relation'):
            missing = condition(kind)
            del missing['reference']
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, 'reference'):
                load(missing)
        for kind in ('pose', 'relative_orientation'):
            value = condition(kind)
            value['measurement']['kind'] = 'object_position'
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, 'actual frame'):
                load(value)
        value = condition('relative_displacement')
        value['reference']['kind'] = 'contact_points'
        with self.assertRaisesRegex(ValueError, 'oriented landmark'):
            load(value)
        value = condition('spatial_relation')
        value['measurement'] = {'kind': 'functional_point', 'label': 'object', 'tag': 'tip'}
        with self.assertRaisesRegex(ValueError, 'cannot replace functional'):
            load(value)

    def test_unused_or_invalid_condition_fields_are_not_silently_ignored(self):
        for kind in ('pose', 'relative_orientation', 'spatial_relation'):
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, 'axes only'):
                load({**condition(kind), 'axes': [2]})
        for axes in ([], [True], [0, 0], [3]):
            with self.subTest(axes=axes), self.assertRaisesRegex(ValueError, 'subset'):
                load({**condition('relative_orientation'), 'orientation_axes': axes})
        value = condition('spatial_relation')
        value.update(expected='inside_box', half_extents=[.1, .1, .1], min_overlap_fraction=.1)
        with self.assertRaisesRegex(ValueError, 'projected object relations'):
            load(value)
        value = condition('spatial_relation')
        value['expected'] = 'covering'
        with self.assertRaisesRegex(ValueError, 'relation adapter'):
            load(value)
        value = condition('pose')
        del value['angle_tolerance_rad']
        with self.assertRaisesRegex(ValueError, 'separate from position'):
            load(value)

    def test_explicit_point_near_is_not_a_whole_object_surface_distance(self):
        value = condition('spatial_relation')
        value.update(expected='near', relation_scope='points')
        value['measurement']['kind'] = 'object_center_position'
        load(value)
        self.assertTrue(evaluate_geometry(value, [0, 0, .005], [0, 0, 0, 1, 0, 0, 0]).passed)
        value['measurement']['kind'] = 'object_center_pose'
        value['relation_scope'] = 'objects'
        with self.assertRaisesRegex(ValueError, 'material mesh_paths'):
            load(value)

        value['measurement']={'kind':'object_pose','label':'object','mesh_paths':['visual/mesh'],'calibration_id':'reviewed-material'}
        value['reference']={'kind':'object_pose','label':'landmark','mesh_paths':['visual/mesh'],'calibration_id':'reviewed-material'}
        load(value)

    def test_object_scope_preserves_named_root_frame_instead_of_using_bounds_centre(self):
        roots = {'object': [0, 0, .2, 1, 0, 0, 0], 'landmark': [0, 0, 0, 1, 0, 0, 0]}
        def surface(label, env_idx, pose):
            result = cube(pose[:3])
            result['position'] = [9, 9, 9]  # Deliberately different mesh centre.
            return result
        session = AtomicSession.__new__(AtomicSession)
        session.env_idx = 0
        session.env = SimpleNamespace(_atomic_surfaces=SimpleNamespace(resolve=surface))
        session._resolve_with_source = lambda selector: (np.array(roots[selector['label']]), dict(selector))
        session._object_pose = lambda label: np.array(roots[label])
        value = condition('spatial_relation')
        value['margin'] = .15
        measured, source, reference, _ = session._resolve_condition(value)
        self.assertEqual(measured['position'], roots['object'][:3])
        self.assertEqual(reference['position'], roots['landmark'][:3])
        self.assertTrue(evaluate_geometry(value, measured, reference).passed)
        self.assertIn('geometry_representation', source)

    def test_each_direction_uses_the_reference_axis_and_projected_overlap(self):
        q = [np.sqrt(.5), 0, 0, np.sqrt(.5)]
        reference = cube(q=q)
        directions = {'above': (2, 1), 'below': (2, -1), 'left_of': (0, -1),
                      'right_of': (0, 1), 'in_front_of': (1, 1), 'behind': (1, -1)}
        for relation, (axis, sign) in directions.items():
            local = np.zeros(3)
            local[axis] = sign * .2
            value = {'kind': 'spatial_relation', 'relation_scope': 'objects', 'expected': relation,
                     'margin': .15, 'tolerance': .01, 'min_overlap_fraction': .1}
            with self.subTest(relation=relation):
                self.assertTrue(evaluate_geometry(value, cube(_rotation(q) @ local, q=q), reference).passed)
                local[(axis + 1) % 3] = .5
                result = evaluate_geometry(value, cube(_rotation(q) @ local, q=q), reference)
                self.assertEqual(result.components['relation_error_m'], 0)
                self.assertFalse(result.passed)

    def test_whole_object_box_containment_and_supported_on_are_distinct(self):
        reference = cube(half=.1)
        value = {'kind': 'spatial_relation', 'relation_scope': 'objects', 'expected': 'inside_box',
                 'half_extents': [.1, .1, .1], 'tolerance': .001}
        self.assertTrue(evaluate_geometry(value, cube(half=.05), reference).passed)
        self.assertFalse(evaluate_geometry(value, cube(half=.15), reference).passed)
        value = {'kind': 'spatial_relation', 'relation_scope': 'objects', 'expected': 'on_top', 'tolerance': .001}
        measured = cube((0, 0, .2), half=.1)
        self.assertFalse(evaluate_geometry(value, measured, reference).passed)
        measured['support_contact'] = True
        self.assertTrue(evaluate_geometry(value, measured, reference).passed)

    def test_quaternion_scale_does_not_change_orientation_or_invent_identity(self):
        for magnitude in (1e-300, 1, 1e300):
            rotated = [0, 0, 0, 0, magnitude, 0, 0]  # 180 degrees about x.
            value = {'kind': 'relative_orientation', 'expected': [0, 1, 0, 0], 'tolerance': .001}
            with self.subTest(magnitude=magnitude):
                self.assertTrue(evaluate_geometry(value, rotated).passed)
                self.assertFalse(evaluate_geometry({**value, 'expected': [1, 0, 0, 0]}, rotated).passed)


if __name__ == '__main__':
    unittest.main()
