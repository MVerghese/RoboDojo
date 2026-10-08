#!/usr/bin/env python3
"""Review/check all-task atomic plans without importing Isaac Sim.

Plans describe candidate actions and control flow. They deliberately cannot be
passed to AtomicProgram: selection rules and physical recognizers remain open.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import sys

import yaml

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from task.atomic.spec import FAMILIES
from scripts.atomic.storage import atomic_write_json, atomic_write_text

PLANS = REPO / 'task/atomic/segmentation_plans.json'
REPORT = REPO / 'task/atomic/SEGMENTATION.md'
DEPENDENCIES = (
    'env/reward_manager/func_parser.py',
    'env/reward_manager/reward_manager.py',
    'task/RoboDojo/config/_task.yml',
    'task/atomic/sequence.py',
    'task/atomic/session.py',
    'task/atomic/spec.py',
    'task/atomic/recognizers.py',
    'task/atomic/twist_validation.py',
    'task/atomic/diagnostics.py',
    'task/atomic/bindings.py',
    'task/atomic/landmarks.py',
    'task/atomic/materials.py',
    'task/atomic/selection.py',
    'task/atomic/trajectory.py',
    'task/atomic/regions.py',
    'task/atomic/fit.py',
    'task/atomic/flow.py',
    'task/atomic/fold.py',
    'task/atomic/cloth_bending.py',
    'task/atomic/layers.py',
    'task/atomic/cloth_calibration.py', 'task/atomic/segments.py', 'task/atomic/surface_distance.py',
    'env/scene_manager/objects/fluid.py',
    'env/scene_manager/objects/garment.py',
    'task/atomic/contacts.py',
    'task/atomic/replay.py', 'task/atomic/recognition_validation.py', 'task/atomic/material_validation.py',
    'task/atomic/support_validation.py', 'task/atomic/settling_validation.py', 'task/atomic/contact_validation.py', 'task/atomic/target_regions.py', 'task/atomic/kinematics.py',
    'src/eval_client/eval_env.py',
)


def strings(value):
    """Config selectors use either a string or a list of strings."""
    return [value] if isinstance(value, str) else value


def config_selectors(config):
    """Keep selection specs (including counts), not guessed instantiated labels."""
    rows = []

    def visit(node, section):
        if isinstance(node, dict):
            if 'select_mode' in node:
                rows.append({'section': section, 'selection': node['select_mode']})
            for value in node.values():
                visit(value, section)
        elif isinstance(node, list):
            for value in node:
                visit(value, section)

    for section, value in config.items():
        visit(value, section)
    return rows


def fingerprint(path):
    return {'path': path.relative_to(REPO).as_posix(),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def evidence(task):
    source = REPO / 'task/RoboDojo/tasks' / f'{task}.py'
    config_path = REPO / 'task/RoboDojo/config' / f'{task}.yml'
    tree = ast.parse(source.read_text())
    source_ev = fingerprint(source)
    source_ev['methods'] = {node.name: node.lineno for node in ast.walk(tree)
                            if isinstance(node, ast.FunctionDef)}
    config_ev = fingerprint(config_path)
    config_ev['selectors'] = config_selectors(yaml.safe_load(config_path.read_text()))
    return {'source': source_ev, 'config': config_ev}


def walk_flow(node):
    yield node
    for child in node.get('children', []):
        yield from walk_flow(child)
    if 'body' in node:
        yield from walk_flow(node['body'])


def validate_flow(node, bindings, ids):
    kind = node.get('type')
    schemas = {
        'action': {'type', 'id', 'family', 'binding', 'goal', 'basis', 'recognition'},
        'event': {'type', 'name', 'goal'},
        'unsupported': {'type', 'behavior', 'binding', 'goal'},
        'sequence': {'type', 'children'},
        'independent': {'type', 'children'},
        'choice': {'type', 'children', 'rule'},
        'repeat': {'type', 'binding', 'body', 'order', 'selection', 'rule'},
        'maintain': {'type', 'binding', 'body', 'condition'},
    }
    if kind not in schemas or set(node) != schemas[kind]:
        raise ValueError(f'invalid flow node: {node}')
    if 'binding' in node and node['binding'] not in bindings:
        raise ValueError(f"unresolved binding {node['binding']}")
    for key in ('id', 'goal', 'rule', 'condition', 'selection', 'name', 'behavior'):
        if key in node and (not isinstance(node[key], str) or not node[key].strip()):
            raise ValueError(f'{key} must be nonempty text')
    if kind == 'action':
        if node['id'] in ids:
            raise ValueError(f"duplicate action id {node['id']}")
        ids.add(node['id'])
        if node['family'] not in FAMILIES or node['recognition'] != node['family']:
            raise ValueError('action requires a taxonomy family and its recognition recipe')
        if node['basis'] not in ('proposed_decomposition', 'explicit_instruction',
                                 'optional_instruction', 'native_requirement'):
            raise ValueError('invalid action evidence basis')
        if node['family'] == 'pick' and bindings[node['binding']]['section'] not in ('Rigid', 'Articulation'):
            raise ValueError('pick must bind a potentially movable object, not fixed Geometry/material')
    if kind in ('sequence', 'independent', 'choice'):
        if not isinstance(node['children'], list) or len(node['children']) < 2:
            raise ValueError(f'{kind} needs at least two branches')
        for child in node['children']:
            validate_flow(child, bindings, ids)
    if kind == 'repeat' and node['order'] not in ('any', 'serial_any', 'source_order'):
        raise ValueError('repeat requires any, serial_any or source_order')
    if 'body' in node:
        validate_flow(node['body'], bindings, ids)
    if kind == 'unsupported' and node['behavior'] != 'throw':
        raise ValueError('unreviewed unsupported behavior')


def validate(data, check_evidence=True):
    paths = {p.stem for p in (REPO / 'task/RoboDojo/tasks').glob('*.py') if p.name != '__init__.py'}
    names = [entry['task'] for entry in data['tasks']]
    if len(names) != len(set(names)) or set(names) != paths:
        raise ValueError(f'task coverage mismatch: missing={paths-set(names)}, extra={set(names)-paths}')
    if data['schema_version'] != 1 or set(data['recognition_recipes']) != FAMILIES:
        raise ValueError('invalid schema version/recognition recipe coverage')
    for recipe in data['recognition_recipes'].values():
        if not recipe['boundary_events'] or not recipe['current_support'] or recipe['requires_independent_of_geometry'] is not True:
            raise ValueError('recognition must have physical boundaries, support status and geometry independence')
    families = set()
    for entry in data['tasks']:
        ev = evidence(entry['task'])
        if entry['status'] != 'source_plan' or not entry['canonical_action_count']:
            raise ValueError('plans must retain source-only status and count semantics')
        for name, binding in entry['bindings'].items():
            selectors = [row['selection'] for row in ev['config']['selectors'] if row['section'] == binding['section']]
            labels = {label for sel in selectors for label in strings(sel.get('label', []))}
            prefixes = {label for sel in selectors for label in strings(sel.get('label_prefix', []))}
            if not binding['resolve'] or not (binding.get('labels') or binding.get('prefixes')):
                raise ValueError(f"{entry['task']}.{name} needs resolution rules and config labels/prefixes")
            missing_labels = set(binding.get('labels', [])) - labels
            missing_prefixes = set(binding.get('prefixes', [])) - prefixes
            if missing_labels or missing_prefixes:
                raise ValueError(f"{entry['task']}.{name}: missing config labels={missing_labels}, prefixes={missing_prefixes}")
        validate_flow(entry['flow'], entry['bindings'], set())
        families.update(n['family'] for n in walk_flow(entry['flow']) if n['type'] == 'action')
        if check_evidence and entry.get('evidence') != ev:
            raise ValueError(f"stale plan source/config evidence for {entry['task']}; review before --refresh")
    if families != FAMILIES:
        raise ValueError(f'missing action families: {FAMILIES-families}')
    deps = [fingerprint(REPO / path) for path in DEPENDENCIES]
    if check_evidence and data.get('dependencies') != deps:
        raise ValueError('native/runtime dependencies changed; re-audit segmentation semantics before --refresh')


def expression(node):
    kind = node['type']
    if kind == 'action':
        return f"{node['family']}[{node['binding']}]"
    if kind == 'event':
        return f"event({node['name']})"
    if kind == 'unsupported':
        return f"UNSUPPORTED {node['behavior']}[{node['binding']}]"
    if kind in ('sequence', 'independent', 'choice'):
        separator = {'sequence': ' → ', 'independent': ' ∥ ', 'choice': ' OR '}[kind]
        return '(' + separator.join(expression(child) for child in node['children']) + ')'
    if kind == 'repeat':
        return f"repeat[{node['binding']}; {node['selection']}; {node['order']}]{{{expression(node['body'])}}}"
    return f"hold[{node['binding']}]{{{expression(node['body'])}}}"


def describe_flow(node, indent=0):
    pad = '  ' * indent
    kind = node['type']
    if kind == 'action':
        return [f"{pad}- **`{node['id']}` / {node['family']}[{node['binding']}]** ({node['basis']}): {node['goal']}"]
    if kind in ('event', 'unsupported'):
        title = node.get('name', 'UNSUPPORTED ' + node.get('behavior', ''))
        return [f"{pad}- **{title}**: {node['goal']}"]
    if kind == 'repeat':
        title = f"Repeat `{node['binding']}` / `{node['selection']}` / `{node['order']}`: {node['rule']}"
    elif kind == 'maintain':
        title = f"Maintain `{node['binding']}`: {node['condition']}"
    else:
        title = {'sequence': 'Sequence', 'independent': 'Independent branches (may overlap)',
                 'choice': 'Alternative route'}[kind]
        if kind == 'choice':
            title += ': ' + node['rule']
    lines = [f'{pad}- **{title}**']
    for child in node.get('children', [node.get('body')]):
        lines.extend(describe_flow(child, indent + 1))
    return lines


def render(data):
    catalog = json.loads((REPO / 'task/atomic/task_catalog.json').read_text())
    gaps = {e['task']: e['audit_gaps'] for e in catalog['tasks']}
    lines = ['# Segmenting all RoboDojo eval tasks', '',
             f"Reviewed **{len(data['tasks'])} modules**, including random variants separately. "
             'Every module has a candidate atomic plan, config-backed object bindings, ordering/selection rules, '
             'physical boundary requirements and restart state requirements. '
             'The [machine-readable plans](segmentation_plans.json) preserve these distinctions.', '',
             '**These are source-backed plans, not observed rollout segments or executable `AtomicProgram` files.** '
             f"There are {len(list((REPO / 'task/atomic/programs').glob('*.json')))} schema-loadable programs; four tasks were exercised in the historical pilot. "
             'No new GPU evaluations were run for this investigation.', '',
             '## Control-flow semantics', '',
             '- **sequence / →:** required order within this proposed route. Some orders are native/instruction requirements; '
             'others follow physical support dependencies and are identified as proposed.',
             '- **independent / ∥:** goals need not be executed in listed order; branches may overlap if robot resources permit.',
             '- **repeat / any:** one independent branch per selected item, each retaining its own pick→terminal dependency. '
             '**serial_any** permits any item order with completed, nonoverlapping cycles. '
             '**source_order** follows the documented role/phase order.',
             '- **choice:** alternative routes or selected subsets. Resolve roles, count and asset identity from the loaded layout, '
             'scene/game state and observed contacts. Labels alone do not determine which slice, hook, outlet or support role was used.',
             '- **maintain / hold:** verify a condition continuously while the body executes. '
             'Scene/opponent/observation events are not robot atomic actions.',
             '- **unsupported:** explicitly preserve requested behavior outside the taxonomy; throwing remains unsupported. '
             'Canonical counts describe a proposed route, never a count of actions observed in a trace.', '',
             'Selection names and goal text are reviewed resolution contracts, **not executable expressions**. '
             'The checker verifies coverage, labels, physical categories and evidence freshness; it does not resolve a layout, '
             'schedule arms, create numeric geometry or prove a proposed route feasible.', '',
             '## Changes needed to recognize and restart every task', '',
             '1. Bind labels/roles and live functional landmarks from each loaded layout. Preserve free choices and optional stages. '
             'Calibrate geometry against actual meshes and feasible trajectories.',
             '2. Add geometry-independent physical recognizers below. Emit contact/event intervals at physics-substep resolution '
             'with arm/object identities, provenance, confidence and missing-data status. '
             'An endpoint predicate alone does not establish the action that achieved it.',
             '3. Bind these plans to the new concurrent dependency runtime. `AtomicSequence` now samples all enabled '
             'stages each physics substep and permits overlapping independent branches; finite repetitions can be explicitly '
             'unrolled. Bounded numeric asset repeats and read-only scene gates are implemented; explicit branch/subset choices are implemented; automatic role/route compilation and task-specific game/conveyor bindings remain missing. '
             'See [RUNTIME.md](RUNTIME.md); the prose plans are still not executable programs.',
             '4. Capture verified start states at observed action boundaries. Save the common and task-specific state below. '
             '`replay_prefix` currently replays actions and checks preceding predicates; it is not a full simulator snapshot. '
             'Any concrete independent root may start in the initial scene, including a trace boundary at action zero, without resetting native baselines. '
             '`_start_atomic_stage` resets parser baselines and robot origin after nonzero prefix replay, so memory/game/count/trigger tasks need '
             'explicit state restoration rather than treating that reset as equivalent to the original boundary.',
             '5. Validate replay/snapshot fidelity against original poses, joints, velocities, material/particle state and native '
             'phase; reject already-completed or unsupported starts. Then generate with/without-condition pairs using identical '
             'recognition/success checks and calibrated slot targets. Report recognition, task success, geometry error and coverage separately.', '',
             'A single rigid-object pilot is insufficient to establish later-stage restarts for all tasks. '
             'Successful instrumented traces are still needed for those boundaries. Existing demonstration datasets without '
             'layout/object state cannot supply verified starts by themselves.', '',
             '## Physical recognition recipes', '',
             '| Family | Required physical evidence/boundaries | Current support |',
             '| --- | --- | --- |']
    for family, recipe in data['recognition_recipes'].items():
        lines.append(f"| `{family}` | {recipe['definition']} Boundaries: {', '.join(recipe['boundary_events'])}. | {recipe['current_support']} |")
    lines += ['', 'See [the complete slot/factor audit](CONDITIONING_AUDIT.md) before assigning geometry to any action. '
              'All recipes require recognition independent of the requested geometric target.', '',
              '## Common restart state', '']
    lines += ['- ' + state for state in data['common_restart_state']]
    lines += ['', '## Every task at a glance', '', '| Task | Candidate action plan | Canonical count |', '| --- | --- | --- |']
    for entry in data['tasks']:
        lines.append(f"| [{entry['task']}](#task-{entry['task'].lower().replace('_', '-')}) | {expression(entry['flow'])} | {entry['canonical_action_count']} |")
    lines += ['', '## Per-task plans and blockers', '']
    for entry in data['tasks']:
        ev = entry['evidence']
        src = '../RoboDojo/tasks/' + entry['task'] + '.py'
        cfg = '../RoboDojo/config/' + entry['task'] + '.yml'
        lines += [f"<a id=\"task-{entry['task'].lower().replace('_', '-')}\"></a>", '',
                  f"### {entry['task']}", '',
                  f"[Instruction]({src}#L{ev['source']['methods']['gen_instruction']}) · "
                  f"[Native reward]({src}#L{ev['source']['methods']['run_reward']}) · [Asset/config bindings]({cfg})", '',
                  '**Bindings:**', '']
        for name, b in entry['bindings'].items():
            selectors = ', '.join(b.get('labels', []) + [p + '*' for p in b.get('prefixes', [])])
            lines.append(f"- `{name}` = {b['section']} `{selectors}`. {b['resolve']}")
        lines += ['', '**Candidate control flow:**', ''] + describe_flow(entry['flow'])
        lines += ['', '**Ordering, recognition and restart gaps:**', '']
        lines += ['- ' + note for note in entry['constraints'] + gaps[entry['task']] + entry['additional_blockers']]
        lines += ['- Additional restart state: ' + (' '.join(entry['restart_state']) or 'Common state plus resolved bindings and action/support history.')]
        lines += ['- Canonical count: ' + entry['canonical_action_count'] + '.', '']
    lines += ['## Check and inspect', '', '```bash',
              'python scripts/atomic/segmentation_plans.py --check',
              'python scripts/atomic/segmentation_plans.py --task press_by_number',
              '# After source/config review and curated plan edits:',
              'python scripts/atomic/segmentation_plans.py --refresh', '```', '',
              'No Isaac Sim imports are needed. The host environment needs PyYAML. '
              'Refresh extracts source/config fingerprints and selection specs; it does not infer or approve a decomposition.', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--check', action='store_true')
    group.add_argument('--refresh', action='store_true')
    group.add_argument('--task', help='Print one reviewed plan as JSON')
    args = parser.parse_args()
    data = json.loads(PLANS.read_text())
    validate(data, check_evidence=not args.refresh)
    if args.refresh:
        for entry in data['tasks']:
            entry['evidence'] = evidence(entry['task'])
        data['dependencies'] = [fingerprint(REPO / path) for path in DEPENDENCIES]
        atomic_write_json(PLANS, data)
        atomic_write_text(REPORT, render(data))
    elif args.task:
        entry = next((e for e in data['tasks'] if e['task'] == args.task), None)
        if entry is None:
            parser.error('unknown task')
        print(json.dumps(entry, indent=2))
        return
    elif REPORT.read_text() != render(data):
        raise ValueError('SEGMENTATION.md differs from reviewed plans/catalogue; use --refresh')
    print(f"Verified {len(data['tasks'])} source plans, all {len(FAMILIES)} action families and config/source evidence")


if __name__ == '__main__':
    main()
