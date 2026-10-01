import json
import ast
from copy import deepcopy
import math
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
import numpy as np
from task.atomic.geometry import evaluate_geometry
from task.atomic.contacts import PhysXContacts, ContactUnavailable
from task.atomic.spec import AtomicProgram, AtomicStage
from scripts.atomic.generate_paired_suite import generate


def plate(x=0, y=0, z=0):
    # Explicit triangles, not an axis-aligned bounding-box overlap test.
    return {'position': [x, y, z], 'orientation': [1, 0, 0, 0],
            'vertices': [[x - .1, y - .1, z], [x + .1, y - .1, z],
                         [x + .1, y + .1, z], [x - .1, y + .1, z]],
            'triangles': [[0, 1, 2], [0, 2, 3]]}


class AuditRegressionTests(unittest.TestCase):
    def test_above_fails_for_correct_height_with_disjoint_footprints(self):
        condition = {'kind': 'spatial_relation', 'relation_scope': 'objects', 'expected': 'above',
                     'margin': .1, 'tolerance': .01, 'min_overlap_fraction': .1}
        result = evaluate_geometry(condition, plate(x=1, z=.2), plate())
        self.assertFalse(result.passed)
        self.assertEqual(result.components['relation_error_m'], 0)
        self.assertEqual(result.components['footprint_overlap_fraction'], 0)
        self.assertTrue(evaluate_geometry(condition, plate(z=.2), plate()).passed)
        self.assertFalse(evaluate_geometry(condition, plate(z=-.2), plate()).passed)

    def test_mesh_hole_does_not_count_as_footprint(self):
        # Two separated strips: their bounding box covers the central square,
        # but the actual projected triangles leave it empty.
        left, right = plate(x=-.4), plate(x=.4)
        source = {**left, 'position': [0, 0, .2],
                  'vertices': [[*v[:2], .2] for v in left['vertices'] + right['vertices']],
                  'triangles': left['triangles'] + [[i + 4 for i in t] for t in right['triangles']]}
        result = evaluate_geometry({'kind': 'spatial_relation', 'relation_scope': 'objects',
                                    'expected': 'above', 'margin': .1, 'tolerance': .01}, source, plate())
        self.assertFalse(result.passed)
        self.assertEqual(result.components['footprint_overlap_m2'], 0)

    def test_contact_centroid_cannot_hide_wrong_surface_contacts(self):
        contacts = {'position': [0, 0, 0], 'points': [[-.08, 0, 0], [.08, 0, 0]]}
        condition = {'kind': 'relative_displacement', 'expected': [0, 0, 0], 'tolerance': .01}
        result = evaluate_geometry(condition, contacts)
        self.assertFalse(result.passed)
        self.assertAlmostEqual(result.error, .08)
        band = {**condition, 'axes': [2]}
        self.assertTrue(evaluate_geometry(band, contacts).passed)
        with self.assertRaisesRegex(ValueError, 'nonempty'):
            evaluate_geometry(condition, {'position': [0, 0, 0], 'points': []})

    def test_contact_points_do_not_invent_an_orientation(self):
        with self.assertRaisesRegex(ValueError, 'orientation'):
            evaluate_geometry({'kind': 'relative_orientation', 'expected': [1, 0, 0, 0], 'tolerance': .1},
                              {'position': [0, 0, 0], 'points': [[0, 0, 0]]})

    def test_axis_orientation_ignores_rotation_about_symmetric_axis(self):
        condition = {'kind': 'relative_orientation', 'orientation_axes': [2],
                     'expected': [1, 0, 0, 0], 'tolerance': .01}
        self.assertTrue(evaluate_geometry(condition, [0, 0, 0, 0, 0, 0, 1]).passed)
        self.assertFalse(evaluate_geometry(condition, [0, 0, 0, math.sqrt(.5), math.sqrt(.5), 0, 0]).passed)

    def test_negative_pose_angle_tolerance_rejected(self):
        with self.assertRaisesRegex(ValueError, 'angle_tolerance'):
            evaluate_geometry({'kind': 'pose', 'expected': {'position': [0, 0, 0], 'orientation': [1, 0, 0, 0]},
                               'tolerance': .01, 'angle_tolerance_rad': -.1}, [0, 0, 0, 1, 0, 0, 0])

    def test_pairs_have_identical_scoring_and_only_prompt_append_differs(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = json.loads(generate(Path(directory)).read_text())
            self.assertEqual(len(manifest['cases']), 8)
            self.assertEqual(len({c['task'] for c in manifest['cases']}), 4)
            for baseline, conditioned in zip(manifest['cases'][::2], manifest['cases'][1::2]):
                a = json.loads(Path(baseline['program']).read_text())
                b = json.loads(Path(conditioned['program']).read_text())
                append = b.pop('geometric_instruction')
                self.assertTrue(append)
                self.assertEqual(a, b)
                self.assertNotIn('instruction', a)  # preserve native object-resolved task prompt
                self.assertEqual(baseline['layout_id'], conditioned['layout_id'])

    def test_real_observation_method_delivers_native_plus_append_throughout_episode(self):
        repo = Path(__file__).resolve().parents[1]
        tree = ast.parse((repo / 'src/eval_client/eval_env.py').read_text())
        method = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == 'get_obs_batch')
        module = ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[]))
        namespace = {'deepcopy': deepcopy, '_jsonable': lambda x: x}
        exec(compile(module, str(repo / 'src/eval_client/eval_env.py'), 'exec'), namespace)
        obs = SimpleNamespace(render_for_capture=lambda: None,
                              get_obs=lambda **kwargs: {0: {'instruction': 'Pick up the scissors by 10 cm.'}})
        env = SimpleNamespace(physx_monitor_enabled=False, num_envs=1, obs_manager=obs,
                              end_flag=[False], _stream_vision=lambda *args: None, atomic_stage=None,
                              _atomic_record_program=SimpleNamespace(instruction=None, geometric_instruction='Use the positive z grasp region.'),
                              _policy_prompt_history=[], take_action_cnt=[0])
        first = namespace['get_obs_batch'](env)[0]['instruction']
        self.assertEqual(first, 'Pick up the scissors by 10 cm. Use the positive z grasp region.')
        env.take_action_cnt = [50]
        self.assertEqual(namespace['get_obs_batch'](env)[0]['instruction'], first)
        self.assertEqual(len(env._policy_prompt_history), 1)
        self.assertEqual(env._policy_prompt_history[0]['instruction'], first)
        env._atomic_record_program.geometric_instruction = None
        self.assertEqual(namespace['get_obs_batch'](env)[0]['instruction'], 'Pick up the scissors by 10 cm.')

    def test_contacts_are_scoped_to_fingers_object_and_environment(self):
        backend = PhysXContacts.__new__(PhysXContacts)
        lm = SimpleNamespace(get_instance_name=lambda i, l: 'cup',
                             get_scene_object=lambda i, n: SimpleNamespace(usd_prim_path='/env0/cup'))
        backend.env = SimpleNamespace(scene_manager=SimpleNamespace(layout_manager=lm),
                                      sim=SimpleNamespace(scene=SimpleNamespace(env_origins=np.array([[1, 2, 3]]))))
        backend.fingers = {'/finger0': (0, 'right_arm'), '/finger1': (0, 'right_arm'), '/env1/finger': (1, 'right_arm')}
        backend.steps, backend.reports, backend.errors = 10, 4, []
        def row(body, obj, point):
            return {'actor0': body, 'actor1': obj, 'collider0': body, 'collider1': obj,
                    'position_world': point, 'normal_world': [1, 0, 0], 'impulse': [1, 0, 0]}
        backend.rows = [row('/finger0', '/env0/cup', [1.01, 2, 3]),
                        row('/finger1', '/env0/cup', [.99, 2, 3]),
                        row('/forearm', '/env0/cup', [9, 9, 9]),
                        row('/env1/finger', '/env0/cup', [9, 9, 9]),
                        row('/finger0', '/env0/other', [9, 9, 9])]
        measured, source = backend.resolve({'kind': 'contact_points', 'label': 'cup', 'min_finger_bodies': 2}, 0)
        self.assertEqual(len(measured['points']), 2)
        self.assertAlmostEqual(measured['points'][0][0], .01)
        self.assertEqual(source['resolved_arm'], 'right_arm')
        backend.rows = backend.rows[:1]
        with self.assertRaises(ContactUnavailable):
            backend.resolve({'kind': 'contact_points', 'label': 'cup', 'min_finger_bodies': 2}, 0)


if __name__ == '__main__':
    unittest.main()
