#!/usr/bin/env python3
"""Four fixed tasks, each with native and explicitly conditioned policy prompts."""
import argparse
from copy import deepcopy
import json
import math
from pathlib import Path
import sys
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from task.atomic.spec import AtomicProgram


def audited_program(task):
    program = json.loads((REPO / 'task/atomic/programs' / f'{task}.json').read_text())
    program.pop('instruction', None)
    program.pop('geometric_instruction', None)
    for stage in program['stages']:
        for condition in stage['geometry']:
            condition['track_closest'] = False
            if stage['family'] in ('pick', 'push') and condition['slot'] in ('grasp_region', 'contact'):
                label = condition['measurement']['label']
                condition['measurement'] = {'kind': 'contact_points', 'label': label, 'arm': 'any',
                                             'min_finger_bodies': 2 if stage['family'] == 'pick' else 1}
                condition['reference'] = {'kind': 'object_center_pose', 'label': label}
                condition['kind'] = 'relative_displacement'
                condition['axes'] = [2] if stage['family'] == 'pick' else [0]
                condition['expected'] = [0, 0, 0]
                condition['tolerance'] = 0.025
            if condition['kind'] == 'spatial_relation':
                condition['relation_scope'] = 'objects'
                condition['min_overlap_fraction'] = 0.1
                condition['measurement']['kind'] = 'object_center_pose'
                condition['reference']['kind'] = 'object_center_pose'

    if task == 'general_pickup':
        c = program['stages'][0]['geometry'][0]
        c.update(expected=[0, 0, 0.06], tolerance=0.02, axes=[2])
    elif task == 'push_T':
        c = program['stages'][0]['geometry'][0]
        c.update(expected=[-0.04, 0, 0], tolerance=0.02, axes=[0])
        program['stages'][0]['geometry'] = [c, {
            'id': 't_goal_pose', 'slot': 'goal', 'kind': 'pose',
            'measurement': {'kind': 'object_center_pose', 'label': 't'},
            'reference': {'kind': 'object_center_pose', 'label': 'target_t'},
            'event': {'kind': 'stage_success'}, 'track_closest': False,
            # Layout 0: block thickness 15 mm, planar target at table surface.
            'expected': {'position': [0, 0, 0.0075], 'orientation': [1, 0, 0, 0]},
            'tolerance': 0.007, 'angle_tolerance_rad': math.radians(7),
        }]
    elif task == 'pour_balls_into_vase':
        c = program['stages'][0]['geometry'][0]
        c.update(expected=[0, 0, 0.02], axes=[2], tolerance=0.015)
        pour = program['stages'][1]
        # All seven *whole balls* must be within finite vase bounds. Native
        # completion is retained separately; its is_A_in_B has no upper-z bound.
        pour['success_checks'] = [{'name': 'is_A_bbox_in_B_bbox', 'args': {
            'label_A': f'sphere_{i}', 'label_B': 'vase', 'atol': 0.002}} for i in range(7)]
        c = pour['geometry'][0]
        c.update(margin=0.10, tolerance=0.01, min_overlap_fraction=0.1)
        c['event']['checks'] = deepcopy(pour['success_checks'])
        c['event']['mode'] = 'any'
        pour['geometry'] = [c, {
            'id': 'cup_pour_orientation', 'slot': 'source_pour_pose', 'kind': 'relative_orientation',
            'measurement': {'kind': 'object_center_pose', 'label': 'cup'},
            'reference': {'kind': 'object_center_pose', 'label': 'vase'},
            'event': deepcopy(c['event']), 'track_closest': False,
            'expected': [math.sqrt(0.5), 0, -math.sqrt(0.5), 0],
            'orientation_axes': [2], 'tolerance': math.radians(30),
        }]
    elif task == 'plug_in_charger':
        c = program['stages'][0]['geometry'][0]
        c.update(expected=[0, 0.01, 0], axes=[1], tolerance=0.015)
        insert = program['stages'][1]
        insert['success_checks'] = [{'name': 'is_atomic_inserted', 'args': {
            'label_A': 'charger', 'label_B': 'socket', 'tip_tag': 'insert',
            'min_depth': 0.005, 'max_depth': 0.025, 'xy_tolerance': 0.012,
            'angle_tolerance_deg': 30}}]
        insert['geometry'] = [{
            'id': 'charger_entry_pose', 'slot': 'entry_pose', 'kind': 'pose',
            'measurement': {'kind': 'functional_point', 'label': 'charger', 'tag': 'insert', 'type': 'active'},
            'reference': {'kind': 'support_point', 'label': 'socket', 'tag': 'socket/1', 'type': 'passive', 'index': 0},
            'event': {'kind': 'first_predicate', 'mode': 'all', 'checks': [
                {'name': 'is_atomic_entry', 'args': {'label_A': 'charger', 'label_B': 'socket',
                                                   'min_depth': 0.0, 'max_depth': 0.025,
                                                   'xy_tolerance': 0.012, 'angle_tolerance_deg': 30}}]},
            'expected': {'position': [0, 0, -0.005], 'orientation': [1, 0, 0, 0]},
            'tolerance': 0.008, 'angle_tolerance_rad': math.radians(20), 'track_closest': False,
        }]
    elif task == 'deposit_coin':
        # Remove the misleading bank-origin final-position proxy. This task is
        # outside the pilot; entry geometry needs its own verified slot landmark.
        program['stages'][1]['geometry'] = []
    return program


PROMPTS = {
    'general_pickup': 'At the first 2.5 cm lift, grasp the target so every force-bearing finger contact lies between 4 and 8 cm along its positive local z axis from the centre of its mesh bounds. Other contact coordinates are unrestricted.',
    'push_T': 'At the first 1 cm motion of the T block, make finger contact on its negative local x side: every force-bearing finger contact must be 2 to 6 cm to the negative x side of the centre of its mesh bounds. Finish with the block centre within 7 mm of the point 7.5 mm above the pad centre along the pad local z axis and its orientation within 7 degrees of the pad.',
    'pour_balls_into_vase': 'At the first 2.5 cm lift, grasp the cup with every force-bearing finger contact 0.5 to 3.5 cm above the centre of its mesh bounds along its local z axis. When the first whole ball enters the vase, keep the cup centre at least 10 cm above the vase centre along the vase local z axis (1 cm tolerance), with at least 10 percent overlap of the smaller object footprint projected along that axis. At that moment, point the cup local z axis towards the vase negative local x axis, within 30 degrees.',
    'plug_in_charger': 'At the first 2.5 cm lift, grasp the charger body with every force-bearing finger contact between -0.5 and +2.5 cm along its local y axis from the centre of its mesh bounds. Insert into the middle outlet (socket/1). When the connector first crosses an outlet entry plane, put its insert landmark within 8 mm of the point 5 mm below the middle outlet entry landmark and align its insert frame within 20 degrees of the middle outlet frame, using its zero-degree orientation.',
}


def generate(output):
    output.mkdir(parents=True, exist_ok=True)
    manifest = {'schema_version': 2, 'task': 'four_task_contact_audit',
                'mode': 'paired_native_and_geometrically_conditioned', 'cases': [],
                'pair_control': 'same checkpoint, seed 0, layout 0, success definitions and geometric targets; only geometric prompt append differs',
                'limitations': ['one episode per prompt per task; no statistical claim',
                                'native task success reported separately from audited atomic recognition',
                                'mesh bounds centre and projected visible mesh footprint are explicitly named',
                                'PhysX reports contact manifold points, not a continuous contact patch',
                                'contact absence or unreachable events are not geometric passes']}
    for task, prompt in PROMPTS.items():
        base = audited_program(task)
        for mode in ('baseline', 'conditioned'):
            program = deepcopy(base)
            if mode == 'conditioned':
                program['geometric_instruction'] = prompt
            path = output / f'{task}_{mode}.program.json'
            path.write_text(json.dumps(program, indent=2) + '\n')
            AtomicProgram.load(path)
            manifest['cases'].append({'id': f'{task}_{mode}', 'task': task, 'prompt_mode': mode,
                                      'stage': 'multiple', 'kind': 'multiple', 'program': str(path.resolve()),
                                      'layout_id': 0, 'geometric_prompt_append': prompt if mode == 'conditioned' else None})
    path = output / 'suite.json'
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    return path


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    print(generate(args.output_dir))
