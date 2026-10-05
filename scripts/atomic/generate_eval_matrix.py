#!/usr/bin/env python3
"""Generate reviewed partial-task A/B observers across the RoboDojo eval set."""
import argparse
import ast
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.atomic.run_suite import H200_TASKS, validate_suite
from task.atomic.spec import AtomicProgram

PICK_TEXT = ('For every object you pick up, at its first 25 mm lift from its initial position, '
             'keep every force-bearing finger contact within 10 mm vertically of its mesh-bounds '
             'center, measured along the object\u2019s local z axis. Other contact coordinates are unrestricted.')
PLACE_TEXT = ('For every object you place after transporting it while held, at its first complete '
              'finger release keep its local z direction within 30 degrees of that direction at '
              'the beginning of the episode. Rotation about that direction is unrestricted.')
TRANSFER_TEXT = ('During a handover, when only the receiving hand remains in contact, keep the '
                 'object\u2019s local z direction within 30 degrees of its direction at the beginning '
                 'of the episode. Rotation about that direction is unrestricted.')
TOOL_TEXT = ('For each supported sweep stroke after the broom and contacted block have both moved '
             'at least 10 mm horizontally, keep every force-bearing broom/block contact within '
             '10 mm vertically of that block\u2019s mesh-bounds center along the block\u2019s local z axis.')
PREFIX_BOUNDS = {'arrange_largest_number': (4, 5), 'classify_objects': (1, 3),
                 'classify_objects_by_language': (2, 3), 'sweep_blocks': (3, 5),
                 'sweep_blocks_random': (1, 2), 'solve_equation': (10, 10)}


def action_bindings(node):
    if node.get('type') == 'action':
        return [(node['family'], node['binding'])]
    result = []
    for value in node.values():
        if isinstance(value, dict):
            result += action_bindings(value)
        elif isinstance(value, list):
            for child in value:
                if isinstance(child, dict):
                    result += action_bindings(child)
    return list(dict.fromkeys(result))


def grasp_condition(label):
    return {'id': 'grasp_height', 'slot': 'grasp_region', 'kind': 'relative_displacement',
            'measurement': {'kind': 'contact_points', 'label': label, 'arm': 'any', 'min_finger_bodies': 2},
            'reference': {'kind': 'object_center_pose', 'label': label},
            'event': {'kind': 'first_lift', 'label': label, 'threshold': .025},
            'expected': [0, 0, 0], 'axes': [2], 'tolerance': .01, 'track_closest': False}


def direction_condition(label, event, slot):
    return {'id': 'preserved_z_direction', 'slot': slot, 'kind': 'relative_orientation',
            'measurement': {'kind': 'object_pose', 'label': label},
            'reference': {'kind': 'object_pose', 'label': label, 'time': 'stage_start'},
            'event': {'kind': 'recognition_event', 'name': event},
            'expected': [1, 0, 0, 0], 'orientation_axes': [2],
            'tolerance': math.pi / 6, 'track_closest': False}


def pickup(ident, label):
    return {'id': ident, 'family': 'pick', 'required': False, 'instruction': 'Observe a candidate object pickup.',
            'recognition': {'kind': 'finger_contact_motion', 'label': label, 'arm': 'any',
                            'min_contact_steps': 2, 'motion_threshold_m': .025},
            'success_checks': [{'name': 'is_lift', 'args': {'label': label, 'z_threshold': .025}}],
            'geometry': [grasp_condition(label)]}


def placement(ident, label, supports):
    return {'id': ident, 'family': 'place', 'required': False,
            'instruction': 'Observe first held transport, release and settling on a reviewed support.',
            'recognition': {'kind': 'supported_release', 'label': label, 'arm': 'any',
                'min_contact_steps': 2, 'transport_threshold_m': .02,
                'support_labels': [s for s in supports if s != label], 'settle_steps': 24,
                'max_position_step_m': .002, 'max_angle_step_rad': .05,
                'max_settle_displacement_m': .005, 'max_settle_angle_rad': .1},
            'success_checks': [{'name': 'is_atomic_interaction', 'args': {}}],
            'geometry': [direction_condition(label, 'release', 'release_pose')]}


def profile(plan):
    """Compile reviewed candidate roles, without claiming complete task segmentation."""
    task = plan['task']
    if task in H200_TASKS:
        return None, 'H200 workflow required'
    if task == 'fold_clothes':
        return None, 'cloth contact and fold recognizer missing'
    existing = REPO / f'task/atomic/programs/{task}.json'
    # Retain stronger reviewed bindings for these tasks. Endpoint-only original
    # insertion/pour stages are deliberately not included as physical actions.
    if task in ('align_blocks', 'stack_blocks_by_language', 'press_by_number', 'play_Xylophone', 'push_T', 'push_T_random', 'general_pickup'):
        base = json.loads(existing.read_text())
        base.pop('geometric_instruction', None)
        texts = []
        for stage in base['stages']:
            if stage['family'] == 'pick':
                stage['geometry'] = [grasp_condition(stage['recognition']['label'])]
        if any(s['family'] == 'pick' for s in base['stages']):
            texts.append(PICK_TEXT)
        appends = {
            'align_blocks': 'At each completed set-square push, keep every set-square/block contact within 10 mm vertically of the contacted block center along its local z axis. Keep blocks supported on the table.',
            'stack_blocks_by_language': 'For both upper blocks, place their centers 5 mm in positive local x from the block below, with zero local y offset and at most 4 mm planar error. Release and settle with at least 50 percent projected footprint overlap on that block.',
            'press_by_number': 'At each button press, keep every finger contact within 5 mm planar distance of the annotated press point in the moving cap frame. Fully press and release between repetitions.',
            'play_Xylophone': 'At each new mallet/key contact, keep every eligible contact within 8 mm planar distance of the key hit point in its local frame. Raise the mallet at least 25 mm between keys.',
            'push_T': 'At the first 10 mm T-block motion, contact its negative local x edge at -40 mm from its mesh center, within 20 mm along x. At the goal keep the T center 7.5 mm above the pad center within 7 mm positional error and 7 degrees orientation error.',
            'push_T_random': 'At the first 10 mm T-block motion, contact its negative local x edge at -40 mm from its mesh center, within 20 mm along x. At the goal keep the T center 7.5 mm above the pad center within 7 mm positional error and 7 degrees orientation error.',
        }
        if task in appends:
            texts.append(appends[task])
        return (base, ' '.join(texts)), None

    stages, templates, texts = [], {}, []
    bindings = plan['bindings']
    supports = ['@table'] + list(dict.fromkeys(label for b in bindings.values()
        if b['section'] in ('Rigid', 'Geometry', 'Articulation') for label in b.get('labels', [])))
    pairs = action_bindings(plan['flow'])
    for family, role in pairs:
        binding = bindings[role]
        if family not in ('pick', 'place') or binding['section'] != 'Rigid':
            continue
        for label in binding.get('labels', []):
            ident = f'{family}_{label}'
            if any(s['id'] == ident for s in stages):
                continue
            stages.append(pickup(ident, label) if family == 'pick' else placement(ident, label, supports))
        for index, prefix in enumerate(binding.get('prefixes', [])):
            lo, hi = PREFIX_BOUNDS[task]
            ident = f'{family}_{role}_{index}'
            stages.append(pickup(ident, '$object') if family == 'pick' else placement(ident, '$object', supports))
            templates[ident] = {'prefix': prefix, 'placeholder': '$object', 'min': lo, 'max': hi, 'category': 'rigid'}
        if binding.get('labels') or binding.get('prefixes'):
            texts.append(PICK_TEXT if family == 'pick' else PLACE_TEXT)

    for family, role in pairs:
        if family != 'handover' or bindings[role]['section'] != 'Rigid':
            continue
        for label in bindings[role].get('labels', []):
            for giver, receiver in [('left_arm', 'right_arm'), ('right_arm', 'left_arm')]:
                stages.append({'id': f'handover_{label}_{giver}', 'family': 'handover', 'required': False,
                    'instruction': 'Observe a handover in the declared direction.',
                    'recognition': {'kind': 'grip_transfer', 'label': label, 'giver_arm': giver,
                        'receiver_arm': receiver, 'min_contact_steps': 2, 'overlap_steps': 2,
                        'receiver_steps': 2, 'max_position_step_m': .05},
                    'success_checks': [{'name': 'is_atomic_interaction', 'args': {}}],
                    'geometry': [direction_condition(label, 'receiver_only', 'transfer_pose')]})
            texts.append(TRANSFER_TEXT)

    if task in ('sweep_blocks', 'sweep_blocks_random'):
        for index, prefix in enumerate(bindings['objects']['prefixes']):
            ident = f'sweep_{index}'
            stages.append({'id': ident, 'family': 'push_with_tool', 'required': False,
                'instruction': 'Observe a contact-coupled broom/block stroke.',
                'recognition': {'kind': 'held_tool_push', 'label': 'broom', 'target_label': '$object',
                    'arm': 'any', 'min_contact_steps': 2, 'support_labels': ['@table', 'broom_shovel'],
                    'motion_threshold_m': .01, 'tool_motion_threshold_m': .01, 'max_vertical_motion_m': .01},
                'success_checks': [{'name': 'is_atomic_interaction', 'args': {}}],
                'geometry': [{'id': 'sweep_contact_height', 'slot': 'contact', 'kind': 'relative_displacement',
                    'measurement': {'kind': 'object_contact_points', 'label': 'broom', 'other_label': '$object'},
                    'reference': {'kind': 'object_center_pose', 'label': '$object'},
                    'event': {'kind': 'recognition_event', 'name': 'stroke'},
                    'expected': [0, 0, 0], 'axes': [2], 'tolerance': .01, 'track_closest': False}]})
            lo, hi = PREFIX_BOUNDS[task]
            templates[ident] = {'prefix': prefix, 'placeholder': '$object', 'min': lo, 'max': hi, 'category': 'rigid'}
        texts.append(TOOL_TEXT)
    if not stages:
        return None, 'no reviewed executable partial-task observer'
    base = {'task_name': task, 'stages': stages, 'stage_dependencies': {s['id']: [] for s in stages}}
    if templates:
        base['label_templates'] = templates
    return (base, ' '.join(dict.fromkeys(texts))), None


def generate(output, checkpoints, tasks=None):
    if output.exists() and any(output.iterdir()):
        raise ValueError('use an empty output directory; packaged inputs are immutable')
    if not checkpoints:
        raise ValueError('supply at least one checkpoint/base-run mapping')
    for ident, control in checkpoints.items():
        if not ident.replace('_', '').replace('-', '').isalnum() or set(control) != {'checkpoint', 'base_run'}:
            raise ValueError('checkpoint entries require a safe ID, checkpoint and base_run')
    output.mkdir(parents=True, exist_ok=True)
    plans = json.loads((REPO / 'task/atomic/segmentation_plans.json').read_text())['tasks']
    if tasks and set(tasks) - {p['task'] for p in plans}:
        raise ValueError('unknown RoboDojo eval task')
    manifest = {'schema_version': 3, 'task': 'robodojo_eval_set',
        'mode': 'paired_native_and_geometrically_conditioned', 'checkpoints': deepcopy(checkpoints),
        'layout_id': 0, 'cases': [], 'coverage': [],
        'scope': 'first-instance physical observers; partial task coverage, not complete task segmentation',
        'limitations': ['one seed/layout/episode per arm', 'prototype targets require live calibration',
                        'candidate observers do not imply all candidates must be manipulated',
                        'insertion, twist, material pour and fold bindings remain excluded where uncalibrated']}
    priority = {'general_pickup': 0, 'push_T': 1, 'stack_blocks_by_language': 2,
                'align_blocks': 3, 'play_Xylophone': 4, 'insert_key': 5,
                'sweep_blocks': 6, 'classify_objects': 7, 'press_by_number': 8}
    for plan in sorted(plans, key=lambda p: (priority.get(p['task'], 100), p['task'])):
        pair, blocker = profile(plan)
        families = sorted({s['family'] for s in pair[0]['stages']}) if pair else []
        planned = sorted({f for f, _ in action_bindings(plan['flow'])})
        selected = not tasks or plan['task'] in tasks
        manifest['coverage'].append({'task': plan['task'], 'included': bool(pair and selected),
            'families': families if selected else [], 'unbound_families': sorted(set(planned) - set(families)),
            'blocker': blocker or (None if selected else 'not selected for this launch'),
            'source_sha256': plan['evidence']['source']['sha256'],
            'config_sha256': plan['evidence']['config']['sha256']})
        if not pair or not selected:
            continue
        base, append = pair
        source = ast.parse((REPO / plan['evidence']['source']['path']).read_text())
        step_limits = [node.value.value for node in ast.walk(source) if isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Constant) and type(node.value.value) is int
            and any(isinstance(t, ast.Attribute) and t.attr == 'step_lim' for t in node.targets)]
        task_timeout_s = min(36000, max(3600, max(step_limits, default=800) * 12))
        for checkpoint_id in checkpoints:
            root = output / 'pairs' / checkpoint_id / plan['task']
            root.mkdir(parents=True)
            for mode in ('baseline', 'conditioned'):
                program = deepcopy(base)
                if mode == 'conditioned':
                    program['geometric_instruction'] = append
                path = root / f'{mode}.program.json'
                path.write_text(json.dumps(program, indent=2) + '\n')
                AtomicProgram.load(path)
                manifest['cases'].append({'id': f'{checkpoint_id}_{plan["task"]}_{mode}',
                    'task': plan['task'], 'checkpoint_id': checkpoint_id, 'prompt_mode': mode,
                    'task_timeout_s': task_timeout_s,
                    'stage': 'multiple', 'kind': 'multiple', 'layout_id': 0,
                    'program': str(path.resolve()), 'program_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                    'geometric_prompt_append': append if mode == 'conditioned' else None})
    validate_suite(manifest)
    (output / 'suite.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--checkpoints', type=Path, required=True,
                        help='JSON mapping ID to checkpoint and compatible base_run')
    parser.add_argument('--tasks', nargs='+')
    args = parser.parse_args()
    data = generate(args.output_dir, json.loads(args.checkpoints.read_text()), args.tasks)
    print(f"Generated {len(data['cases'])} cases for {sum(c['included'] for c in data['coverage'])} eval tasks")
