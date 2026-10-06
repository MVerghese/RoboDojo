"""A material-free source region must also contain initial live particles."""
from copy import deepcopy
import math
import unittest

from task.atomic.calibration import initial_fluid_core_cohort


def evidence():
    source = {'metadata': {'model_name': 'bottle', 'model_id': 0},
        'initial_root_pose': [1, 2, 3, math.sqrt(.5), 0, 0, math.sqrt(.5)]}
    target = {'metadata': {'model_name': 'cup', 'model_id': 0},
        'initial_root_pose': [10, 0, 0, 1, 0, 0, 0]}
    scene = {'objects': {'bottle': source, 'cup': target, 'wine': {'material': {
        'ids': [8, 3, 19, 11], 'initial_positions': [[1, 2.01, 2.96],
            [10, 0, 0], [200, 0, 0], [1.02, 2.01, 2.96]],
        'source': {'backend': 'retained live physics particle copy'}}}}}
    def selector(label, center):
        return {'kind': 'model_calibrated_frame', 'label': label, 'models': {
            label+'/00000': {'local_pose': center+[1,0,0,0], 'calibration_id': 'reviewed-core'}}}
    recognition = {'fluid_label': 'wine', 'label': 'bottle', 'target_label': 'cup',
        'source_frame': selector('bottle', [.01,0,-.04]),
        'target_frame': selector('cup', [0,0,0]),
        'source_half_extents_m': [.015]*3, 'target_half_extents_m': [.015]*3}
    return scene, recognition


class FluidCalibrationTests(unittest.TestCase):
    def test_physical_rotated_core_uses_all_particles_and_persistent_ids(self):
        scene, config = evidence(); result = initial_fluid_core_cohort(scene, config)
        self.assertEqual(result['total_particle_count'], 4)
        self.assertEqual(result['initial_source_only_ids'], [8])
        self.assertEqual(result['target_particle_count'], 1)
        self.assertEqual(result['outside_both_count'], 2)
        moved = deepcopy(scene)
        for row in moved['objects'].values():
            for point in row.get('material', {}).get('initial_positions', []):
                point[:3] = [x+y for x,y in zip(point[:3], [8, -5, 2])]
            if 'initial_root_pose' in row:
                row['initial_root_pose'][:3] = [x+y for x,y in zip(row['initial_root_pose'][:3], [8,-5,2])]
        self.assertEqual(initial_fluid_core_cohort(moved, config)['initial_source_only_ids'], [8])

    def test_unpopulated_upper_core_and_initial_target_overlap_are_explicit(self):
        scene, config = evidence()
        config['source_frame']['models']['bottle/00000']['local_pose'][2] = .0275
        self.assertEqual(initial_fluid_core_cohort(scene, config)['initial_source_only_count'], 0)
        scene, config = evidence()
        scene['objects']['cup'] = deepcopy(scene['objects']['bottle'])
        scene['objects']['cup']['metadata']['model_name'] = 'cup'
        config['target_frame']['models']['cup/00000']['local_pose'] = [.01,0,-.04,1,0,0,0]
        result = initial_fluid_core_cohort(scene, config)
        self.assertEqual(result['source_target_overlap_count'], 1)
        self.assertEqual(result['initial_source_only_count'], 0)

    def test_invalid_ids_and_nonfinite_positions_cannot_supply_a_cohort(self):
        for bad in ('float_ids', 'duplicate_ids', 'nan_position'):
            with self.subTest(bad=bad):
                scene, config = evidence(); material = scene['objects']['wine']['material']
                if bad == 'float_ids': material['ids'][0] = 8.1
                if bad == 'duplicate_ids': material['ids'][0] = material['ids'][1]
                if bad == 'nan_position': material['initial_positions'][0][0] = float('nan')
                with self.assertRaisesRegex(ValueError, 'finite positions and distinct integer'):
                    initial_fluid_core_cohort(scene, config)


if __name__ == '__main__':
    unittest.main()
