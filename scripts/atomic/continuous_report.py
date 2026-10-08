"""Portable Markdown/HTML reports of measured geometric error and conditioning."""
from collections import Counter, defaultdict
import hashlib
import html
import json
import math
from pathlib import Path
import statistics
import tarfile

from scripts.atomic.storage import atomic_write_json, atomic_write_text


def contact_witness_summary(scores):
    rows = []
    for stage in scores:
        conditions = [c['contact_witness'] for c in stage['conditions'].values() if c.get('contact_witness')]
        physical = list(stage.get('contact_witnesses', {}).values())
        selection=(stage.get('selection') or {}).get('contact_witness')
        if conditions or physical or selection:
            rows.append({'stage_id':stage['stage_id'],
                'condition_snapshots':dict(Counter(w['status'] for w in conditions)),
                'physical_snapshots':dict(Counter(w['status'] for w in physical)),
                'selection_snapshot_status':selection.get('status') if selection else None,
                'failed_checks':sorted({f for w in conditions + physical + ([selection] if selection else []) for f in w.get('failed_checks',[])})})
    return rows


METHOD = (
    'Each geometric conditioning has separate continuous measurements in actual physical units. '
    'Position, contact and gap errors are reported in millimetres; orientation errors in degrees; '
    'footprint overlap and its shortfall as fractions; area in square millimetres; '
    'solid volume in cubic millimetres; relative material speed in mm/s; path duration in seconds. '
    'SE(3) translation and rotation are separate numbers. No tolerance normalization or '
    'combined score across conditioning types is used. '
    'Contact conditions use the worst eligible contact point, not the contact centroid. '
    'Means and medians include only independently reproduced observations. Missing events '
    'are N/A, never zero. Layer gaps need projected material overlap; absent overlap '
    'still has a measured coverage shortfall, but no measured vertical gap. '
    'Coverage is observed/declared conditions, including optional object candidates. '
    'Shared-event delta is mean(conditioned measurement − baseline measurement) over identical '
    'stage/condition identities observed in both arms of a verified pair, in the stated unit. '
    'Negative error delta is better; positive overlap delta is better. Positive finite-mesh '
    'clearance means spare aperture space. Signed separation '
    'depends on the requested relation and has no universal improvement direction. '
    'Different observed populations can change the separate arm means. Summaries group by '
    'action, condition, modifier and slot, weighting each observed condition equally rather '
    'than each task equally. '
    'One episode per arm gives descriptive results, not a statistical steering estimate.'
    ' Raw strike, handover, insertion and release witnesses are checked separately from numerical reproduction. '
    'Incompatible impact/retraction attempts are marked invalid_recognition_window '
    'and excluded from scalar summaries; their recorded values and native outcomes remain retained.'
    ' Material source/cohort, held-exit and adjacent crossing witnesses are also independently checked. '
    'Partial historical source evidence preserves sampled geometry without certifying missing witnesses; '
    'inconsistent source witnesses are marked invalid_source_witness and excluded.'
    ' Named-support force signs and body identities are audited separately. Inconsistent raw '
    'support witnesses are excluded as invalid_support_witness; historical booleans without '
    'raw forces remain partial physical evidence even when their geometry reproduces.'
    ' Fresh stage-success geometry requires qualified atomic completion. Tagged completion '
    'flags, clocks and pick lift bounds are audited; contradictory snapshots are excluded. '
    'Older endpoint-only stage-success snapshots retain partial evidence rather than being relabeled.'
)


def stats(values):
    values = list(values)
    return {'n': len(values), 'mean': statistics.mean(values) if values else None,
            'median': statistics.median(values) if values else None}


def measured_components(result):
    """Honor retained component observation flags without rewriting raw scores."""
    values = result['components']
    observed = result.get('observed')
    if isinstance(observed, dict) and observed.get('gap_observed') is False:
        return {k:v for k,v in values.items() if k not in (
            'minimum_layer_gap_m','maximum_layer_gap_m','layer_gap_shortfall_m','layer_gap_excess_m')}
    return values


def component_values(events, name):
    values = []
    for event in events:
        score = event['score']
        if score.get('status') != 'reproduced':
            continue
        value = measured_components(score['recorded_result']).get(name)
        if value is not None:
            value = float(value)
            if not math.isfinite(value):
                raise ValueError('nonfinite recorded geometric component')
            values.append(value)
    return values


def load_program(case, root):
    path = Path(case['program'])
    if path.exists():
        source = path.read_bytes()
        if hashlib.sha256(source).hexdigest() != case['program_sha256']:
            raise ValueError('conditioning program differs from frozen suite: ' + case['id'])
        return json.loads(source)
    # Collected directories can be moved without retaining the original program path.
    run = root / 'runs' / case['id']
    frozen = json.loads((run / 'prepared_case.json').read_text())
    overlay = run / 'robodojo-overlay.tar.gz'
    if hashlib.sha256(overlay.read_bytes()).hexdigest() != frozen['overlay_sha256']:
        raise ValueError('packaged conditioning differs from frozen preparation')
    with tarfile.open(overlay, 'r:gz') as archive:
        return json.load(archive.extractfile('task/atomic/inputs/program.json'))


def collect_events(row):
    events = {}
    for stage in row.get('atomic_scores', []):
        for ident, score in stage['conditions'].items():
            key = (stage['stage_id'], ident)
            if key in events:
                raise ValueError('duplicate stage/condition event identity')
            events[key] = {'family': stage.get('family', 'unknown'), 'score': score}
        for ident, path in stage.get('trajectories', {}).items():
            result = path.get('recorded_result', {})
            scored = path.get('status') == 'reproduced' and result.get('status') == 'scored'
            components = {k:v for k,v in result.items() if k.endswith(('_m','_s')) and v is not None}
            events[(stage['stage_id'],'path/'+ident)] = {'family':stage.get('family','unknown'),
                'score':{'status':'reproduced' if scored else (result.get('status','missing_raw_evidence')
                         if path.get('status') == 'reproduced' else path.get('status','missing_raw_evidence')),
                         'kind':'trajectory','slot':path.get('condition',{}).get('slot','path'),
                         'recorded_result':{'components':components}}}
        flow = stage.get('material_flow')
        if flow is not None:
            crossings = flow.get('crossings',{}) or {'unobserved':{'status':'event_not_observed'}}
            for ident, crossing in crossings.items():
                result = crossing.get('recorded_result', {})
                scored = crossing.get('status') == 'reproduced' and result.get('status') == 'scored'
                events[(stage['stage_id'],'flow/'+ident)] = {'family':stage.get('family','unknown'),
                    'score':{'status':'reproduced' if scored else (result.get('status','missing_raw_evidence')
                             if crossing['status'] == 'reproduced' else crossing['status']),
                             'condition_id':'opening_crossing','kind':'stream_crossing','slot':'opening',
                             'recorded_result':{'components':result.get('components',{})}}}
        selection = stage.get('selection')
        if selection:
            observed = selection.get('observed') or {}; contacts = observed.get('contacts',[])
            valid = selection.get('status') == 'reproduced' and selection.get('target_status') == 'resolved' and len(contacts) == 1
            label = contacts[0]['label'] if valid else None
            # Use initial geometry of the actually selected candidate, never its moved final pose.
            for ident, candidate in next(iter(selection.get('candidates',{}).values()),{}).items():
                score = selection['candidates'][label][ident] if valid else {'status':
                    selection['status'] if selection.get('status')!='reproduced' else 'selection_not_resolved'}
                events[(stage['stage_id'],'selection/'+ident)] = {'family':stage.get('family','unknown'),
                    'score':dict(score,slot='initial object selection',kind='selection',
                                 condition_id='selection/'+ident)}
    return events


def group_key(identity, event):
    score = event['score']
    return (event['family'],score.get('condition_id',identity[1]),score.get('kind','unknown'),score.get('slot','unknown'))


def arm_summary(events):
    events = list(events)
    reproduced = [e['score']['recorded_result'] for e in events
                  if e['score'].get('status') == 'reproduced']
    components = defaultdict(list)
    reasons = Counter()
    for result in reproduced:
        observed = result.get('observed')
        if isinstance(observed,dict) and observed.get('gap_observed') is False:
            reasons['no_projected_material_overlap_for_vertical_gap'] += 1
        for name, value in measured_components(result).items():
            if name.endswith(('_m', '_rad', '_m2', '_m3', '_m_s', '_s', '_fraction')) and name not in (
                    'required_overlap_fraction', 'vertical_tolerance_m', 'required_clearance_m',
                    'maximum_endpoint_weld_displacement_m'):
                components[name].append(float(value))
    return {'declared': len(events), 'observed': len(reproduced),
            'statuses': dict(Counter(e['score']['status'] for e in events)),
            'component_unavailable_reasons': dict(reasons),
            'components': {name: stats(values) for name, values in sorted(components.items())}}


def shared_summary(baseline, conditioned, matched):
    common = []
    if matched:
        for key in sorted(baseline.keys() & conditioned.keys()):
            a, b = baseline[key], conditioned[key]
            if a['score']['status'] == b['score']['status'] == 'reproduced':
                common.append((a, b))
    names = {name for a, b in common for name in arm_summary([a])['components']}
    components = {}
    for name in sorted(names):
        values = [(component_values([a], name), component_values([b], name)) for a, b in common]
        values = [(a[0], b[0]) for a, b in values if a and b]
        components[name] = {'n': len(values), 'baseline': stats(a for a, b in values),
                            'conditioned': stats(b for a, b in values),
                            'delta': stats(b - a for a, b in values)}
    return {'n_events': len(common), 'components': components}


def build_report(manifest, result, matrix, root):
    cases = {c['id']: c for c in manifest['cases']}
    rows = {r['case_id']: r for r in result['cases']}
    tasks, pooled = [], defaultdict(lambda: {'baseline': {}, 'conditioned': {}})
    for pair in matrix['pairs']:
        a, b = (cases[pair[k]] for k in ('baseline_case', 'conditioned_case'))
        ra, rb = rows[a['id']], rows[b['id']]
        programs = [load_program(c, root) for c in (a, b)]
        # Read the actual frozen targets even if the physical event was absent.
        definitions = defaultdict(list)
        for stage in programs[0]['stages']:
            for condition in stage.get('geometry', []):
                key = (stage['family'], condition['id'], condition['kind'], condition['slot'])
                definition = {'stage_id': stage['id'], 'condition': condition}
                if definition not in definitions[key]:
                    definitions[key].append(definition)
            for path in stage.get('trajectories',[]):
                definitions[(stage['family'],'path/'+path['id'],'trajectory',path['slot'])].append({'stage_id':stage['id'],'condition':path})
            flow = stage.get('recognition',{}).get('flow')
            if flow:
                definitions[(stage['family'],'opening_crossing','stream_crossing','opening')].append({'stage_id':stage['id'],'condition':flow})
            for c in stage.get('selection',{}).get('conditions',[]):
                definitions[(stage['family'],'selection/'+c['id'],'selection','initial object selection')].append({'stage_id':stage['id'],'condition':c})
        events = {'baseline': collect_events(ra), 'conditioned': collect_events(rb)}
        groups = set(definitions)
        for arm in events.values():
            groups.update(group_key(key,e) for key, e in arm.items())
        conditions = []
        for key in sorted(groups):
            selected = {mode: {identity: e for identity, e in arm.items()
                        if group_key(identity,e) == key}
                        for mode, arm in events.items()}
            conditions.append({'family': key[0], 'condition_id': key[1], 'kind': key[2], 'slot': key[3],
                'definitions': definitions.get(key, []),
                'baseline': arm_summary(selected['baseline'].values()),
                'conditioned': arm_summary(selected['conditioned'].values()),
                'shared': shared_summary(selected['baseline'], selected['conditioned'], pair['matched'])})
        task = dict(pair) | {'conditions': conditions, 'conditioning_prompt': b.get('geometric_prompt_append'),
            'physical_requirement_diagnostics':{mode:row.get('physical_requirement_diagnostics',[]) for mode,row in (('baseline',ra),('conditioned',rb))},
            'cloth_bending_diagnostics':{mode:row.get('cloth_bending_diagnostics',[]) for mode,row in (('baseline',ra),('conditioned',rb))},
            'cloth_contact_diagnostics':{mode:[{'counts':h['cloth_contact_probe'].get('counts',{}),
                'material_vertex_correspondence':h['cloth_contact_probe'].get('material_vertex_correspondence'),
                'scope':h['cloth_contact_probe'].get('scope')} for h in row.get('contact_instrumentation',[])
                if h and 'cloth_contact_probe' in h] for mode,row in (('baseline',ra),('conditioned',rb))},
            'material_source_validation': {mode: [{'stage_id':s['stage_id'],
                'statuses':s['material_flow']['witness_summary']}
                for s in row.get('atomic_scores',[]) if (s.get('material_flow') or {}).get('witness_summary')]
                for mode,row in (('baseline',ra),('conditioned',rb))},
            'twist_interval_diagnostics': {mode: [{'stage_id': s['stage_id'],
                'definition': next((stage.get('recognition', {}) for stage in programs[0]['stages']
                                    if stage['id'] == s['stage_id']), {}), **s['twist_rotation_diagnostic']}
                for s in row.get('atomic_scores', []) if s.get('twist_rotation_diagnostic')]
                for mode, row in (('baseline', ra), ('conditioned', rb))},
            'finite_material_validation': {mode: [{'stage_id': s['stage_id'], 'label': label, **bound}
                for s in row.get('atomic_scores', []) for label, bound in s.get('material_bounds', {}).items()]
                for mode, row in (('baseline', ra), ('conditioned', rb))},
            'source_candidate_diagnostics': {mode: [{'stage_id': s['stage_id'], **s['source_candidate_diagnostic']}
                for s in row.get('atomic_scores', []) if s.get('source_candidate_diagnostic', {}).get('status')
                not in (None, 'not_applicable')]
                for mode, row in (('baseline', ra), ('conditioned', rb))},
            'target_surface_validation': {mode: [{'stage_id': s['stage_id'],
                'capture':s['target_surface_validation'],'contact':s.get('target_surface_contact_validation')}
                for s in row.get('atomic_scores',[]) if s.get('target_surface_validation')]
                for mode,row in (('baseline',ra),('conditioned',rb))},
            'material_boundary_validation': {mode: [{'stage_id':s['stage_id'],**s['material_boundary_validation']}
                for s in row.get('atomic_scores',[]) if s.get('material_boundary_validation')]
                for mode,row in (('baseline',ra),('conditioned',rb))},
            'recognition_validation': {mode: [{'stage_id': s['stage_id'],
                'status': s['recognition_witness']['status'],
                'failed_checks': s['recognition_witness'].get('failed_checks', [])}
                for s in row.get('atomic_scores', []) if s.get('recognition_witness', {}).get('status') == 'inconsistent_evidence']
                for mode, row in (('baseline', ra), ('conditioned', rb))},
            'completion_validation': {mode: [{'stage_id': s['stage_id'], 'condition_id': ident, **c['stage_success_witness']}
                for s in row.get('atomic_scores', []) for ident, c in s['conditions'].items() if c.get('stage_success_witness')]
                for mode, row in (('baseline', ra), ('conditioned', rb))},
            'support_validation': {mode: [{'stage_id': s['stage_id'], 'condition_id': ident, **c['support_witness']}
                for s in row.get('atomic_scores', []) for ident, c in s['conditions'].items() if c.get('support_witness')]
                for mode, row in (('baseline', ra), ('conditioned', rb))},
            'contact_validation': {mode: contact_witness_summary(row.get('atomic_scores',[]))
                for mode, row in (('baseline', ra), ('conditioned', rb))},
            'program_sha256': {mode: cases[c]['program_sha256'] for mode, c in (
                ('baseline', a['id']), ('conditioned', b['id']))},
            'delivered_prompts': {mode: sorted({p['instruction'] for episode in row.get('policy_prompt_history', [])
                                               for p in episode}) for mode, row in (
                ('baseline', ra), ('conditioned', rb))},
            'actual_layouts': {mode: sorted({s['layout_id'] for s in row.get('atomic_scores', [])})
                               for mode, row in (('baseline', ra), ('conditioned', rb))},
            'baseline': arm_summary(events['baseline'].values()),
            'conditioned': arm_summary(events['conditioned'].values()),
            'shared_event_count': shared_summary(events['baseline'], events['conditioned'], pair['matched'])['n_events']}
        for mode in ('baseline', 'conditioned'):
            task[mode].pop('components')  # No task-wide mixture of conditioning types.
        tasks.append(task)
        if pair['matched']:
            for mode, arm in events.items():
                for identity, e in arm.items():
                    global_key = (pair['checkpoint_id'], pair['task'], *identity)
                    score = e['score']
                    group = (pair['checkpoint_id'], *group_key(identity,e))
                    pooled[group][mode][global_key] = e
    summary = [{'checkpoint_id': checkpoint, 'family': family, 'condition_id': ident, 'kind': kind, 'slot': slot,
                'baseline': arm_summary(arms['baseline'].values()),
                'conditioned': arm_summary(arms['conditioned'].values()),
                'shared': shared_summary(arms['baseline'], arms['conditioned'], True)}
               for (checkpoint, family, ident, kind, slot), arms in sorted(pooled.items())]
    return {'schema_version': 1, 'updated_at': result['updated_at'], 'method': METHOD,
            'included_tasks': sum(c['included'] for c in manifest.get('coverage', [])) or len(tasks),
            'catalog_tasks': len(manifest.get('coverage', [])) or len(tasks), 'valid_episodes': matrix['valid_episodes'],
            'matched_pairs': matrix['matched_pairs'], 'total_pairs': matrix['total_pairs'],
            'reproduced_event_scores': result.get('reproduced_event_scores'),
            'score_mismatches': result.get('score_mismatches'), 'checkpoints': manifest['checkpoints'],
            'recognition_witness_failures': result.get('recognition_witness_failures', 0),
            'summary': summary, 'tasks': tasks, 'coverage': manifest.get('coverage', []),
            'limitations': manifest.get('limitations', []), 'scope': manifest.get('scope', 'partial action observers')}


def number(value):
    return 'N/A' if value is None else f'{value:.3f}'


def coverage(summary):
    return f"{summary['observed']}/{summary['declared']}"


def component_unit(name):
    if name.endswith('_m_s'):
        return name[:-4].replace('_',' ') + ' (mm/s)',1000
    if name.endswith('_s'):
        return name[:-2].replace('_',' ') + ' (s)',1
    if name.endswith('_rad'):
        return name[:-4].replace('_', ' ') + ' (deg)', 180 / math.pi
    if name.endswith('_m2'):
        return name[:-3].replace('_', ' ') + ' (mm²)', 1e6
    if name.endswith('_m3'):
        return name[:-3].replace('_', ' ') + ' (mm³)', 1e9
    if name.endswith('_m'):
        return name[:-2].replace('_', ' ') + ' (mm)', 1000
    return name.replace('_', ' ') + ' (fraction)', 1


def raw_scalar(summary, name):
    _, scale = component_unit(name)
    s = summary['components'].get(name)
    return 'N/A' if not s else f"{s['mean'] * scale:.3f} / {s['median'] * scale:.3f}"


def component_names(condition):
    # Keep a row with N/A for every tested measurement even if no event occurred.
    expected = {'point': ['position_m'], 'relative_displacement': ['displacement_m'],
                'pose': ['position_m', 'orientation_rad'], 'relative_orientation': ['orientation_rad'],
                'spatial_relation': ['relation_error_m'],
                'trajectory':['max_deviation_m','rms_deviation_m','start_error_m','end_error_m','backtracking_m','duration_s'],
                'stream_crossing':['crossing_position_error_m','aperture_overrun_m','velocity_angle_rad','relative_speed_m_s'],
                'selection':[]}[condition['kind']]
    if condition['kind'] == 'spatial_relation':
        definitions = [d['condition'] for d in condition.get('definitions', [])]
        if definitions and all(d['expected'] == 'inside_region' for d in definitions):
            expected = ['vertex_containment_error_m', 'outside_volume_m3', 'outside_volume_fraction']
        elif definitions and all(d['expected'] in ('inside_aperture','inside_trace_aperture') for d in definitions):
            expected = ['section_area_m2','outside_aperture_area_m2', 'outside_allowed_area_m2', 'boundary_distance_m']
        elif definitions and all(d['expected'] == 'layered_over' for d in definitions):
            expected = ['footprint_overlap_fraction','overlap_shortfall_fraction','footprint_gap_m',
                        'minimum_layer_gap_m','maximum_layer_gap_m','layer_gap_shortfall_m','layer_gap_excess_m']
        elif definitions and all(d.get('relation_scope') == 'curves' for d in definitions):
            expected = ['curve_gap_m','curve_hausdorff_m','measurement_curve_length_m','reference_curve_length_m']
        elif definitions and all(d.get('relation_scope') == 'segments' for d in definitions):
            expected = ['segment_gap_m','segment_hausdorff_m','segment_axis_angle_rad',
                        'measurement_length_m','reference_length_m']
        elif definitions and all(d['expected']=='near' and d.get('relation_scope')=='objects' for d in definitions):
            expected = ['surface_distance_m']
        elif definitions and all(d['expected'] == 'inside_box' and d.get('relation_scope') == 'objects' for d in definitions):
            expected = ['containment_error_m']
        elif not definitions or any(d.get('relation_scope') == 'objects' for d in definitions):
            expected += ['signed_separation_m', 'footprint_gap_m', 'footprint_overlap_fraction',
                         'footprint_overlap_m2', 'overlap_shortfall_fraction']
    if condition['kind']=='selection':
        for definition in condition.get('definitions',[]):
            underlying = definition['condition']['kind']
            if underlying != 'selection':
                expected += component_names(dict(condition,kind=underlying))
    if condition['kind']=='stream_crossing' and any(d['condition'].get('finite_material_bound') for d in condition.get('definitions',[])):
        expected += ['finite_bound_radius_m','finite_bound_clearance_m','finite_bound_shortfall_m']
    return sorted(set(expected) | condition['baseline']['components'].keys() |
                  condition['conditioned']['components'].keys())


def measurement_row(condition, name):
    a, b = condition['baseline'], condition['conditioned']
    shared = condition['shared']['components'].get(name)
    scale = component_unit(name)[1]
    return [condition['family'] + ' / ' + condition['condition_id'], condition['kind'],
            component_unit(name)[0], raw_scalar(a, name), a['components'].get(name, {}).get('n', 0),
            raw_scalar(b, name), b['components'].get(name, {}).get('n', 0), shared['n'] if shared else 0,
            number(shared['delta']['mean'] * scale) if shared and shared['delta']['mean'] is not None else 'N/A']


def md_cell(value):
    return str(value).replace('|', '\\|').replace('\n', '<br>')


def table(headers, rows):
    return ['| ' + ' | '.join(headers) + ' |', '| ' + ' | '.join('---' for h in headers) + ' |',
            *('| ' + ' | '.join(md_cell(v) for v in row) + ' |' for row in rows)]


def condition_parameters(condition):
    definitions = condition['definitions']
    if not definitions:
        return [('Definition', 'See bound condition evidence in benchmark_results.json')]
    fields = [('measurement', 'Measurement'), ('reference', 'Reference frame / landmark'),
              ('expected', 'Target'), ('axes', 'Position axes'), ('orientation_axes', 'Orientation axes'),
              ('tolerance', 'Tolerance'), ('angle_tolerance_rad', 'Angle tolerance (rad)'),
              ('event', 'Measurement event'), ('relation_scope', 'Relation scope'),
              ('min_overlap_fraction', 'Minimum footprint overlap'), ('margin', 'Ordering margin (m)'),
              ('interior_boxes', 'Calibrated interior-box union (metres)'),
              ('aperture_profile', 'Calibrated aperture rings (metres)'),
              ('required_clearance_m', 'Required material clearance (metres)'),
              ('min_layer_gap_m','Minimum material layer gap (metres)'),
              ('max_layer_gap_m','Maximum material layer gap (metres)'),
              ('opening','Opening frame'),('target_xy_m','Crossing XY target (metres)'),
              ('position_tolerance_m','Crossing positional tolerance (metres)'),
              ('expected_velocity_direction','Requested velocity direction in opening frame'),
              ('start_event','Path start event'),('end_event','Path end event'),('min_samples','Required physics samples')]
    result = [('Action / modifier / slot', f"{condition['family']} / {condition['kind']} / {condition['slot']}")]
    for field, label in fields:
        converted = []
        for definition in definitions:
            c = definition['condition']
            definition_kind = c.get('kind',condition['kind'])
            if field not in c:
                continue
            value = c[field]
            if field == 'tolerance':
                angular = condition['kind'] == 'relative_orientation' or (
                    condition['kind'] == 'selection' and c.get('kind') == 'relative_orientation')
                label = 'Tolerance (deg)' if angular else 'Tolerance (mm)'
                value *= 180 / math.pi if angular else 1000
            elif field == 'angle_tolerance_rad':
                label, value = 'Angle tolerance (deg)', value * 180 / math.pi
            elif field == 'position_tolerance_m':
                label, value = 'Crossing positional tolerance (mm)', value*1000
            elif field in ('min_layer_gap_m','max_layer_gap_m','required_clearance_m'):
                label, value = label.replace('(metres)','(mm)'),value*1000
            elif field == 'target_xy_m':
                label, value = 'Crossing XY target (mm)', [v*1000 for v in value]
            elif field == 'margin':
                label, value = 'Ordering margin (mm)', value * 1000
            elif field == 'expected' and definition_kind in ('point', 'relative_displacement'):
                label, value = 'Target displacement (mm)', [v * 1000 for v in value]
            elif field == 'expected' and definition_kind == 'pose':
                value = {'position_mm': [v * 1000 for v in value['position']],
                         'orientation_wxyz': value['orientation']}
            elif field == 'expected' and definition_kind == 'relative_orientation':
                label = 'Target relative orientation (wxyz quaternion)'
            elif field == 'expected' and condition['kind'] == 'trajectory':
                label, value = 'Path waypoints (mm)', [[v*1000 for v in p] for p in value]
            elif field == 'event' and value.get('kind') == 'first_lift' and 'threshold' in value:
                value = {k: v for k, v in value.items() if k != 'threshold'} | {'threshold_mm': value['threshold'] * 1000}
            converted.append(json.dumps(value, ensure_ascii=False, sort_keys=True))
        values = sorted(set(converted))
        if values:
            result.append((label, '; '.join(values)))
    result.append(('Program stages', ', '.join(d['stage_id'] for d in definitions)))
    return result


def summary_rows(data):
    return [[*([r['suite']] if data.get('runs') else []), r['checkpoint_id'], *measurement_row(r, name)]
            for r in data['summary'] for name in component_names(r)]


CONDITION_HEADERS = ['Action / condition', 'Modifier', 'Measurement / unit',
                     'Baseline mean / median', 'B n', 'Conditioned mean / median',
                     'C n', 'Shared n', 'Shared Δ(C−B)']
SUMMARY_HEADERS = ['Checkpoint', *CONDITION_HEADERS]
TASK_HEADERS = ['Task', 'Conditioning tested', 'A/B comparison', 'B coverage', 'C coverage']


def task_rows(data):
    return [[t['task'], *([t['suite']] if data.get('runs') else []), '; '.join(sorted({c['family'] + ': ' + c['condition_id'] for c in t['conditions']})),
             'verified' if t['matched'] else 'EXCLUDED', coverage(t['baseline']),
             coverage(t['conditioned'])] for t in data['tasks']]


RUN_HEADERS = ['Suite', 'Cases', 'Collected', 'Completed episodes', 'Valid episodes',
               'Verified pairs', 'Reproduced events', 'Reproduced flow', 'Mismatches', 'Updated']


def run_rows(data):
    return [[r[k] for k in ('suite', 'cases', 'collected', 'completed_episodes', 'valid_episodes',
                           'matched_pairs', 'reproduced_event_scores', 'reproduced_flow_scores',
                           'score_mismatches', 'updated_at')] for r in data.get('runs', [])]


def provenance_rows(task):
    if 'suite' not in task:
        return []
    rows = [['Suite', task['suite']], ['Evidence directory', task['evidence_directory']]]
    for mode in ('baseline', 'conditioned'):
        row = task['provenance'][mode]
        rows += [[mode + ' case', row['case_id']], [mode + ' collection status', row['status']],
                 [mode + ' completed episodes', row.get('completed_episodes')],
                 [mode + ' native success', row.get('full_task_success')],
                 [mode + ' runtime SHA256', row.get('runtime_sha256')],
                 [mode + ' source archive SHA256', row.get('source_archive_sha256')]]
    return rows


def condition_rows(task):
    return [measurement_row(c, name) for c in task['conditions'] for name in component_names(c)]


def requirement_rows(diagnostics):
    return [[d['stage_id'], gate, counts.get('true', 0), counts.get('false', 0),
             counts.get('not_evaluated', 0)]
            for d in diagnostics
            for gate, counts in sorted(d['eligibility'].get('gate_counts', {}).items())]


REPLAY_HEADERS = ['Task', 'Stage', 'Mode', 'Boundary command', 'Substeps in command',
                  'Discarded tail', 'Prefix verified', 'Stage success', 'Root start error (mm)',
                  'Rigid root rotation error (degrees)', 'Rigid linear velocity error (mm/s)',
                  'Rigid angular velocity error (degrees/s)',
                  'Revolute joint position error (degrees)', 'Revolute joint velocity error (degrees/s)',
                  'Prismatic joint position error (mm)', 'Prismatic joint velocity error (mm/s)']
REPLAY_SCOPE = ('Selected-stage replay jobs are excluded from full-task A/B counts. '
                'Root residuals compare recorded and replayed starts in the same frame. '
                'Rotation and velocity are reported only for retained, bound activation-time rigid solver readbacks; '
                'missing historical fields are N/A. Columns show maxima over the compared named roots. '
                'Robot columns show maxima over bound solver DOFs of each live USD joint type, including grippers. '
                'Missing joint captures remain N/A; revolute residuals do not wrap full turns. '
                'This does not establish drive, effort, material, game or full simulator-state fidelity.')

DRIVE_HEADERS=['Task','Stage','Compared target DOFs',
    'Revolute position target error (degrees)','Revolute velocity target error (degrees/s)',
    'Prismatic position target error (mm)','Prismatic velocity target error (mm/s)']
DRIVE_SCOPE=('Command targets are current IsaacLab position/velocity target buffers, compared separately '
    'from measured joint motion. Columns show maxima within each live USD joint type. '
    'Historical absent captures are N/A. Target equality does not prove equal gains, efforts, '
    'actuator memory or full controller state.')


def drive_validation_rows(data):
    rows=[]
    for proof in data.get('replay_validations',[]):
        for episode in proof['episodes']:
            comparison=episode.get('boundary_position_comparison') or {}
            targets=comparison.get('robot_kinematics',{}).get('drive_targets',{}).get('joints',[])
            values=[]
            for kind in ('revolute','prismatic'):
                for key in ('position_target_error','velocity_target_error'):
                    found=[r[key] for r in targets if r['kind']==kind]
                    values.append(f'{max(found):.4f}' if found else 'N/A')
            rows.append([proof['task'],episode['atomic_start'].get('stage_id'),len(targets),*values])
    return rows


def replay_validation_rows(data):
    rows = []
    for proof in data.get('replay_validations', []):
        for episode in proof['episodes']:
            start = episode['atomic_start'];comparison = episode.get('boundary_position_comparison') or {}
            errors = [p['position_error_mm'] for p in comparison.get('positions', [])]
            kinematics=comparison.get('rigid_kinematics',{}).get('objects',[])
            residuals=[]
            for component in ('orientation_error_deg','linear_velocity_error_mm_s','angular_velocity_error_deg_s'):
                values=[r[component] for r in kinematics]
                residuals.append(f'{max(values):.4f}' if values else 'N/A')
            joints=comparison.get('robot_kinematics',{}).get('joints',[])
            for kind in ('revolute','prismatic'):
                for component in ('position_error','velocity_error'):
                    values=[j[component] for j in joints if j['kind']==kind]
                    residuals.append(f'{max(values):.4f}' if values else 'N/A')
            rows.append([proof['task'], start.get('stage_id'), start.get('mode'), start.get('action_index'),
                start.get('replayed_physics_substeps', 'N/A'), start.get('discarded_control_substeps', 'N/A'),
                episode.get('prefix_verified'), episode.get('selected_stage_success'),
                f'{max(errors):.4f}' if errors else 'N/A',*residuals])
    return rows


TWIST_DIAGNOSTIC_HEADERS = ['Arm', 'Stage', 'Evidence', 'Signed rotation (degrees)',
    'Rotation in requested direction (degrees)', 'Off-axis rotation (degrees)', 'Required rotation (degrees)']
FINITE_MATERIAL_HEADERS = ['Arm', 'Stage / material', 'Evidence', 'Enclosing radius (mm)', 'Closed oriented mesh']
SOURCE_CANDIDATE_HEADERS = ['Arm', 'Stage / material / physics step', 'Evidence',
    'Aperture overrun (mm)', 'Finite clearance (mm)', 'Source tilt (degrees)', 'Required tilt (degrees)',
    'Sustained hold observed', 'Inside source core', 'Qualified at crossing']
SOURCE_CANDIDATE_SCOPE = ('First 32 sampled outward candidates, including rejected crossings, '
    'with independent arithmetic and same-step observed hold/tilt/core checks. '
    'These diagnostics are separate from destination-crossing conditioning and successful pours. '
    'A missing observed hold does not independently prove absent contact. Historical summaries '
    'retain counts with N/A per-crossing measurements; truncated histories do not establish complete distributions.')
TWIST_DIAGNOSTIC_SCOPE = ('Net rotation over one retained held/contact-constrained interval. '
    'This is diagnostic progress, separate from completed action and conditioning-event scores. '
    'It is not torque, thread engagement, or summed rotation across regrasp intervals. '
    'Partial evidence retains missing binding/history caveats; contradictory metrics are excluded.')
FINITE_MATERIAL_SCOPE = ('Initialization bounds independently recomputed from the actual captured scaled mesh. '
    'A valid bound alone does not establish any observed or successful aperture crossing. '
    'Open mesh seams do not establish solid volume; the enclosing disk is a conservative sampled-plane fit.')


SURFACE_HEADERS = ['Arm','Stage','Live mesh capture','Contact validation','Max surface distance (mm)','Tolerance (mm)','USD collision configuration']
SURFACE_SCOPE = ('Actual scaled USD collision-mesh region bound to the reviewed model/file, triangles and authored landmark. '
    'Distance uses face interiors, edges and vertices of that region. Missing contacts are N/A; inconsistent metrics are excluded. '
    'This does not certify cooked collider part identity, exclusive key contact, sound or timing.')


def surface_validation_rows(task):
    rows=[]
    for mode,stages in task.get('target_surface_validation',{}).items():
        for stage in stages:
            capture=stage['capture'];contact=stage.get('contact') or {'status':'unobserved'}
            metrics=contact.get('metrics',{}) if contact['status']=='consistent_evidence' else {}
            distances=metrics.get('selected_surface_distances_m',[])
            status=capture['status'] + (': '+capture['reason'] if capture.get('reason') else '')
            configuration=capture.get('collision_configuration') or {'status':'partial_evidence'}
            config_text=configuration['status'] + ''.join('; '+r['relative_path']+': enabled='+str(r['collision_enabled'])+
                ', approximation='+str(r['approximation']) for r in configuration.get('meshes',[]))
            rows.append([mode,stage['stage_id'],status,contact['status'],
                number(max(distances)*1000) if distances else 'N/A',
                number(metrics['distance_tolerance_m']*1000) if 'distance_tolerance_m' in metrics else 'N/A',config_text])
    return rows


def twist_diagnostic_rows(task):
    rows = []
    for mode, intervals in task.get('twist_interval_diagnostics', {}).items():
        for interval in intervals:
            config = interval.get('definition', {})
            metrics = interval.get('metrics', {}) if interval['status'] in ('consistent_evidence', 'partial_evidence') else {}
            signed, off_axis = metrics.get('signed_angle_rad'), metrics.get('off_axis_rotation_rad')
            direction = config.get('direction')
            degrees = lambda value: number(value * 180 / math.pi) if value is not None else 'N/A'
            status = interval['status']
            detail = interval.get('failed_checks') or interval.get('unavailable')
            if detail: status += ': ' + ', '.join(detail)
            rows.append([mode, interval['stage_id'], status, degrees(signed),
                degrees(signed * direction) if signed is not None and direction is not None else 'N/A',
                degrees(off_axis), degrees(config.get('min_angle_rad'))])
    return rows


def finite_material_rows(task):
    rows = []
    for mode, bounds in task.get('finite_material_validation', {}).items():
        for bound in bounds:
            valid = bound['status'] == 'consistent_evidence'
            status = bound['status'] + (': ' + bound['reason'] if bound.get('reason') else '')
            rows.append([mode, bound['stage_id'] + ' / ' + bound['label'], status,
                number(bound['enclosing_radius_m'] * 1000) if valid else 'N/A',
                str(bound['closed_oriented_mesh']) if valid else 'N/A'])
    return rows


def source_candidate_rows(task):
    rows = []
    for mode, stages in task.get('source_candidate_diagnostics', {}).items():
        for stage in stages:
            summary = stage['status'] + '; recorded candidates=' + str(stage.get('candidate_crossings'))
            if stage.get('history_truncated'): summary += '; history truncated'
            if stage.get('history_counts_consistent') is False: summary += '; inconsistent history counts'
            if not stage.get('candidates'):
                rows.append([mode, stage['stage_id'], summary, *(['N/A'] * 7)])
            for candidate in stage.get('candidates', []):
                valid = candidate['status'] in ('consistent_evidence', 'partial_evidence')
                result = (candidate.get('result') or {}) if valid else {}
                q = (candidate.get('qualification') or {}) if valid else {}
                scalar = lambda value,scale: number(value * scale) if value is not None else 'N/A'
                state = lambda key: str(q[key]) if key in q else 'N/A'
                status = candidate['status']
                if candidate.get('failed_checks'): status += ': ' + ', '.join(candidate['failed_checks'])
                if candidate.get('unavailable'): status += ': ' + ', '.join(candidate['unavailable'])
                rows.append([mode, stage['stage_id'] + ' / ' + str(candidate['material_id']) + ' / ' + str(candidate['physics_step']),
                    summary + '; ' + status, scalar(result.get('aperture_overrun_m'),1000),
                    scalar(result.get('finite_bound_clearance_m'),1000), scalar(q.get('tilt_rad'),180/math.pi),
                    scalar(candidate.get('required_tilt_rad'),180/math.pi),
                    str(q['held_contact'] is not None) if 'held_contact' in q else 'N/A',
                    state('inside_source'), state('eligible_for_source_exit')])
    return rows


def bending_display(value):
    """Use report mm/degree units while preserving raw diagnostic evidence."""
    if not isinstance(value,dict):
        return [bending_display(v) for v in value] if isinstance(value,list) else value
    result={}
    for key,v in value.items():
        if key=='longest_component_m':key='largest_component_total_edge_length_m'
        if key.endswith('_rad'):
            result[key[:-4]+'_deg']=None if v is None else math.degrees(v)
        elif key.endswith('_m'):
            result[key[:-2]+'_mm']=None if v is None else v*1000
        else:result[key]=bending_display(v)
    return result


def report_markdown(data):
    lines = ['# RoboDojo conditioning: continuous geometric errors', '',
        f"**{data['valid_episodes']} valid episodes · {data['included_tasks']}/{data['catalog_tasks']} tasks · "
        f"{data['matched_pairs']}/{data['total_pairs']} verified A/B pairs.**", '',
        f"Collected: {data['updated_at']}. Offline reproduction: {data['reproduced_event_scores']} "
        f"event scores, {data['score_mismatches']} mismatches.", '', '## Measurements and units', '', data['method'], '',
        'Independent boundary witness validation: ' + str(data.get('recognition_witness_failures', 0))
        + ' inconsistent windows. These are separate from numerical reproduction mismatches.', '',
        'Distances below are in millimetres and angles in degrees. Raw components show mean / median. '
        'Targets and tolerances use the displayed mm/degree units; orientations use wxyz quaternions. '
        'Selector metadata with explicit `_m`/`_rad` suffixes retains those named units. '
        'Axes 0/1/2 denote local x/y/z. Raw signed separation/overlap are measurements, not unsigned errors. '
        'Unmatched episodes remain descriptive and contribute no shared delta or matched summary.', '',
        *(['## Original screen and expansion suites', '', *table(RUN_HEADERS, run_rows(data)), ''] if data.get('runs') else []),
        *(['## Atomic start validation', '', REPLAY_SCOPE, '',
           *table(REPLAY_HEADERS, replay_validation_rows(data)), ''] if data.get('replay_validations') else []),
        *(['### Drive command targets at activation', '',DRIVE_SCOPE,'',
           *table(DRIVE_HEADERS,drive_validation_rows(data)),''] if data.get('replay_validations') else []),
        '## Matched-pair summary', '', *table((['Suite'] if data.get('runs') else []) + SUMMARY_HEADERS, summary_rows(data)), '',
        '## Task index', '', *table(([TASK_HEADERS[0], 'Suite', *TASK_HEADERS[1:]] if data.get('runs') else TASK_HEADERS), task_rows(data)), '', '## Conditioning and results by task', '']
    for task in data['tasks']:
        lines += [f"### {task['task']} ({task['checkpoint_id']})" + (' — ' + task['suite'] if 'suite' in task else ''), '',
                  *([*table(['Provenance', 'Value'], provenance_rows(task)), ''] if 'suite' in task else []),
                  '**A/B comparison:** ' + ('verified' if task['matched'] else 'EXCLUDED: ' + '; '.join(task['exclusions'])), '',
                  '**Actual layouts:** baseline ' + str(task['actual_layouts']['baseline']) +
                  '; conditioned ' + str(task['actual_layouts']['conditioned']) + '.', '',
                  '**Conditioning supplied to the policy:**', '', '> ' + (task['conditioning_prompt'] or 'No append recorded.'), '',
                  *table(CONDITION_HEADERS, condition_rows(task)), '']
        if twist_diagnostic_rows(task):
            lines += ['**Retained twist intervals:**', '', TWIST_DIAGNOSTIC_SCOPE, '',
                *table(TWIST_DIAGNOSTIC_HEADERS, twist_diagnostic_rows(task)), '']
        if finite_material_rows(task):
            lines += ['**Finite material mesh bounds:**', '', FINITE_MATERIAL_SCOPE, '',
                *table(FINITE_MATERIAL_HEADERS, finite_material_rows(task)), '']
        if source_candidate_rows(task):
            lines += ['**Source-mouth candidate diagnostics:**', '', SOURCE_CANDIDATE_SCOPE, '',
                *table(SOURCE_CANDIDATE_HEADERS, source_candidate_rows(task)), '']
        if surface_validation_rows(task):
            lines += ['**Live strike surface validation:**','',SURFACE_SCOPE,'',
                *table(SURFACE_HEADERS,surface_validation_rows(task)),'']
        for mode,boundaries in task.get('material_boundary_validation',{}).items():
            if boundaries:
                lines += ['**Material boundary validation ('+mode+'):** `'+json.dumps(boundaries,sort_keys=True)+
                    '`. Source exit and first transfer are separate from destination crossing and settled full quantity. Missing historical core frames remain partial; contradictions exclude geometry at affected boundaries.','']
        for mode, failures in task.get('recognition_validation', {}).items():
            if failures:
                lines += ['**Recognition witness failures (' + mode + '):** `' + json.dumps(failures, sort_keys=True)
                          + '`. Geometry and paths using invalid boundary events are excluded from geometric summaries.', '']
        for mode, witnesses in task.get('material_source_validation', {}).items():
            if witnesses:
                lines += ['**Material source witness validation (' + mode + '):** `' + json.dumps(witnesses,sort_keys=True)
                          + '`. Partial evidence preserves sampled geometry without certifying missing source contact/cohort witnesses; inconsistent witnesses are excluded.', '']
        for mode, witnesses in task.get('completion_validation', {}).items():
            if witnesses:
                lines += ['**Stage-success qualification (' + mode + '):** `' + json.dumps(witnesses,sort_keys=True)
                    + '`. Historical missing completion metadata remains partial. Contradictory completion evidence is excluded; saved flags do not reconstruct unsaved force or hold histories.', '']
        for mode, witnesses in task.get('support_validation', {}).items():
            if witnesses:
                lines += ['**Named-support witness validation (' + mode + '):** `' + json.dumps(witnesses,sort_keys=True)
                    + '`. Force signs/body identity are separate from geometric arithmetic. Missing raw force or sleep-history proof remains partial; inconsistent witnesses are excluded.', '']
        for mode, witnesses in task.get('contact_validation', {}).items():
            if witnesses:
                lines += ['**Force-contact witness validation (' + mode + '):** `' + json.dumps(witnesses,sort_keys=True)
                    + '`. These count retained snapshots, not distinct actions. Missing historical root/environment bindings remain partial. Contradictory contact measurements are excluded; force closure and unsaved persistence are not certified.', '']
        for mode, diagnostics in task.get('cloth_contact_diagnostics',{}).items():
            if diagnostics:
                lines += ['**Native cloth contact probe ('+mode+'):** `'+json.dumps(diagnostics,sort_keys=True)
                          +'`. Diagnostic counts do not establish calibrated cloth grasp force.', '']
        for mode, diagnostics in task.get('cloth_bending_diagnostics',{}).items():
            if diagnostics:
                lines += ['**New cloth bending ('+mode+'):** `'+json.dumps(bending_display(diagnostics),sort_keys=True)
                          +'`. Lengths are mm and angles are degrees. Connected bending candidates are not certified settled creases.', '']
        for mode, diagnostics in task.get('physical_requirement_diagnostics',{}).items():
            if diagnostics:
                lines += ['**Observed recognition requirements ('+mode+'):**', '',
                    *table(['Stage', 'Requirement', 'True steps', 'False steps', 'Not evaluated steps'],
                           requirement_rows(diagnostics)), '',
                    'Counts include distinct observed physics steps across attempts. They do not measure '
                    'geometric error or independently prove sensor coverage or policy failure.', '']
        if not task['baseline']['observed'] and not task['conditioned']['observed']:
            lines += ['No geometric event was observed; continuous error is N/A for both arms.', '']
        for c in task['conditions']:
            lines += [f"**{c['family']} / {c['condition_id']} — tested definition:**", '',
                      *table(['Field', 'Value'], condition_parameters(c)), '',
                      'Observation statuses: baseline `' + json.dumps(c['baseline']['statuses'], sort_keys=True) +
                      '`; conditioned `' + json.dumps(c['conditioned']['statuses'], sort_keys=True) + '`.',
                      'Unobserved component reasons: baseline `' + json.dumps(c['baseline'].get('component_unavailable_reasons',{}),sort_keys=True) +
                      '`; conditioned `' + json.dumps(c['conditioned'].get('component_unavailable_reasons',{}),sort_keys=True) + '`.', '']
        lines += ['<details><summary>Exact delivered policy prompts</summary>', '']
        for mode in ('baseline', 'conditioned'):
            lines += [f'**{mode}:**', '', *('> ' + p.replace('\n', '\n> ') for p in task['delivered_prompts'][mode]), '']
        lines += ['</details>', '']
        unbound = task.get('unbound_families', next((c['unbound_families'] for c in data['coverage'] if c['task'] == task['task']), []))
        if unbound:
            lines += ['**Actions not conditioned/measured in this task:** ' + ', '.join(unbound) + '.', '']
    lines += ['## Eval tasks not run', '', *table(['Task', 'Reason', 'Conditioning tested'],
              [[c['task'], c.get('blocker') or 'Not selected', 'None; no episodes']
               for c in data['coverage'] if not c['included']]), '',
              '## Scope and limitations', '', data['scope'], '',
              *('- ' + x for x in data['limitations']), '',
              '- Missing events are not scores. A measured release error does not establish successful placement.',
              '- Source-audited recognizers without observed events do not establish live recognition accuracy.', '',
              'Inputs: `suite.json`, frozen conditioning programs and `benchmark_results.json`. '
              'Machine-readable continuous values: `eval-matrix-continuous.json`. '
              'Raw results and binary action outcomes remain in `benchmark_results.json`.', '']
    return '\n'.join(lines)


def html_table(headers, rows):
    esc = html.escape
    return '<div class="table-wrap"><table><thead><tr>' + ''.join('<th scope="col">' + esc(str(h)) + '</th>' for h in headers) + \
           '</tr></thead><tbody>' + ''.join('<tr>' + ''.join('<td>' + esc(str(v)) + '</td>' for v in row) + '</tr>' for row in rows) + \
           '</tbody></table></div>'


def report_html(data):
    esc = html.escape
    cards = []
    if data.get('replay_validations'):
        cards.append('<section class="method"><h2>Atomic start validation</h2><p>' + esc(REPLAY_SCOPE)
                     + '</p>' + html_table(REPLAY_HEADERS, replay_validation_rows(data))
                     + '<h3>Drive command targets at activation</h3><p>'+esc(DRIVE_SCOPE)+'</p>'
                     + html_table(DRIVE_HEADERS,drive_validation_rows(data)) + '</section>')
    for task in data['tasks']:
        content = '<p class="status">' + esc('Verified A/B pair' if task['matched'] else 'Excluded: ' + '; '.join(task['exclusions'])) + '</p>'
        if 'suite' in task:
            content += html_table(['Provenance', 'Value'], provenance_rows(task))
        content += '<p>Actual layouts: baseline ' + esc(str(task['actual_layouts']['baseline'])) + '; conditioned ' + esc(str(task['actual_layouts']['conditioned'])) + '.</p>'
        content += '<h3>Conditioning supplied to the policy</h3><blockquote>' + esc(task['conditioning_prompt'] or 'No append recorded.') + '</blockquote>'
        content += html_table(CONDITION_HEADERS, condition_rows(task))
        if twist_diagnostic_rows(task):
            content += '<h3>Retained twist intervals</h3><p>' + esc(TWIST_DIAGNOSTIC_SCOPE) + '</p>' + html_table(TWIST_DIAGNOSTIC_HEADERS, twist_diagnostic_rows(task))
        if finite_material_rows(task):
            content += '<h3>Finite material mesh bounds</h3><p>' + esc(FINITE_MATERIAL_SCOPE) + '</p>' + html_table(FINITE_MATERIAL_HEADERS, finite_material_rows(task))
        if source_candidate_rows(task):
            content += '<h3>Source-mouth candidate diagnostics</h3><p>' + esc(SOURCE_CANDIDATE_SCOPE) + '</p>' + html_table(SOURCE_CANDIDATE_HEADERS, source_candidate_rows(task))
        if surface_validation_rows(task):
            content += '<h3>Live strike surface validation</h3><p>'+esc(SURFACE_SCOPE)+'</p>'+html_table(SURFACE_HEADERS,surface_validation_rows(task))
        for mode,boundaries in task.get('material_boundary_validation',{}).items():
            if boundaries:
                content += '<p><strong>Material boundary validation ('+esc(mode)+'):</strong> <code>'+esc(json.dumps(boundaries,sort_keys=True))+'</code>. Source exit and first transfer are separate from destination crossing and settled full quantity. Missing historical core frames remain partial; contradictions exclude geometry at affected boundaries.</p>'
        for mode, failures in task.get('recognition_validation', {}).items():
            if failures:
                content += '<p><strong>Recognition witness failures (' + esc(mode) + '):</strong> <code>' + esc(json.dumps(failures, sort_keys=True)) + '</code>. Geometry and paths using invalid boundary events are excluded from geometric summaries.</p>'
        for mode, witnesses in task.get('material_source_validation', {}).items():
            if witnesses:
                content += '<p><strong>Material source witness validation (' + esc(mode) + '):</strong> <code>' + esc(json.dumps(witnesses,sort_keys=True)) + '</code>. Partial evidence preserves sampled geometry without certifying missing source contact/cohort witnesses; inconsistent witnesses are excluded.</p>'
        for mode, witnesses in task.get('completion_validation', {}).items():
            if witnesses:
                content += '<p><strong>Stage-success qualification (' + esc(mode) + '):</strong> <code>' + esc(json.dumps(witnesses,sort_keys=True)) + '</code>. Historical missing completion metadata remains partial. Contradictory completion evidence is excluded; saved flags do not reconstruct unsaved force or hold histories.</p>'
        for mode, witnesses in task.get('support_validation', {}).items():
            if witnesses:
                content += '<p><strong>Named-support witness validation (' + esc(mode) + '):</strong> <code>' + esc(json.dumps(witnesses,sort_keys=True)) + '</code>. Force signs/body identity are separate from geometric arithmetic. Missing raw force or sleep-history proof remains partial; inconsistent witnesses are excluded.</p>'
        for mode, witnesses in task.get('contact_validation', {}).items():
            if witnesses:
                content += '<p><strong>Force-contact witness validation (' + esc(mode) + '):</strong> <code>' + esc(json.dumps(witnesses,sort_keys=True)) + '</code>. These count retained snapshots, not distinct actions. Missing historical root/environment bindings remain partial. Contradictory contact measurements are excluded; force closure and unsaved persistence are not certified.</p>'
        for mode, diagnostics in task.get('cloth_contact_diagnostics',{}).items():
            if diagnostics:
                content += '<p><strong>Native cloth contact probe ('+esc(mode)+'):</strong> <code>'+esc(json.dumps(diagnostics,sort_keys=True))+'</code>. Diagnostic counts do not establish calibrated cloth grasp force.</p>'
        for mode, diagnostics in task.get('cloth_bending_diagnostics',{}).items():
            if diagnostics:
                content += '<p><strong>New cloth bending ('+esc(mode)+'):</strong> <code>'+esc(json.dumps(bending_display(diagnostics),sort_keys=True))+'</code>. Lengths are mm and angles are degrees. Connected bending candidates are not certified settled creases.</p>'
        for mode, diagnostics in task.get('physical_requirement_diagnostics',{}).items():
            if diagnostics:
                content += '<h3>Observed recognition requirements ('+esc(mode)+')</h3>' + html_table(
                    ['Stage', 'Requirement', 'True steps', 'False steps', 'Not evaluated steps'],
                    requirement_rows(diagnostics)) + '<p>Counts include distinct observed physics steps across attempts. They do not measure geometric error or independently prove sensor coverage or policy failure.</p>'
        if not task['baseline']['observed'] and not task['conditioned']['observed']:
            content += '<p>No geometric event observed. Error is N/A for both arms.</p>'
        for c in task['conditions']:
            content += '<details class="definition"><summary>' + esc(c['family'] + ' / ' + c['condition_id'] + ' — tested definition') + '</summary>'
            content += html_table(['Field', 'Value'], condition_parameters(c))
            content += '<p>Observation statuses: baseline <code>' + esc(json.dumps(c['baseline']['statuses'], sort_keys=True)) + '</code>; conditioned <code>' + esc(json.dumps(c['conditioned']['statuses'], sort_keys=True)) + '</code>.</p>'
            content += '<p>Unobserved component reasons: baseline <code>' + esc(json.dumps(c['baseline'].get('component_unavailable_reasons',{}),sort_keys=True)) + '</code>; conditioned <code>' + esc(json.dumps(c['conditioned'].get('component_unavailable_reasons',{}),sort_keys=True)) + '</code>.</p></details>'
        content += '<details class="prompts"><summary>Exact delivered policy prompts</summary>'
        for mode in ('baseline', 'conditioned'):
            content += '<h4>' + mode.capitalize() + '</h4>' + ''.join('<blockquote>' + esc(p) + '</blockquote>' for p in task['delivered_prompts'][mode])
        content += '</details>'
        unbound = task.get('unbound_families', next((c['unbound_families'] for c in data['coverage'] if c['task'] == task['task']), []))
        if unbound:
            content += '<p>Actions not conditioned/measured in this task: <strong>' + esc(', '.join(unbound)) + '</strong>.</p>'
        families = sorted({c['family'] for c in task['conditions']})
        searchable = ' '.join([task['task'], task['checkpoint_id'], task.get('suite', ''), *families, task['conditioning_prompt'] or ''])
        label = task['task'] + (' · ' + task['suite'] if 'suite' in task else '')
        cards.append('<details class="task" data-search="' + esc(searchable.lower(), quote=True) + '" data-matched="' + str(task['matched']).lower() + '"><summary><span>' + esc(label) + '</span><span class="badge">' + esc('verified' if task['matched'] else 'excluded') + '</span></summary><div class="task-body">' + content + '</div></details>')
    css = '''
    :root{color-scheme:light;--ink:#172d43;--muted:#526475;--line:#dbe4eb;--accent:#096d80}
    *{box-sizing:border-box}body{margin:0;background:#f3f6f8;color:var(--ink);font:15px/1.6 system-ui,sans-serif}
    main{max-width:1440px;margin:auto;padding:36px 28px 70px}header{padding:24px 30px;background:#12324b;color:white;border-radius:16px}
    h1{font-size:30px;line-height:1.2;margin:0 0 12px}h2{margin:32px 0 12px}h3{font-size:17px;margin:22px 0 10px}
    .eyebrow{font-size:12px;text-transform:uppercase;letter-spacing:1.3px;color:#b6dae6;margin-bottom:10px}
    .method{background:white;padding:22px 26px;border:1px solid var(--line);border-radius:12px;margin-top:22px}
    .method p{margin:8px 0}blockquote{margin:10px 0;padding:14px 18px;border-left:4px solid var(--accent);background:#edf7f9;white-space:pre-wrap}
    .table-wrap{overflow:auto;border:1px solid var(--line);border-radius:9px;background:white;margin:12px 0}
    table{border-collapse:collapse;width:100%;font-size:13px}th,td{text-align:left;padding:10px 12px;border-bottom:1px solid var(--line);vertical-align:top}
    th{background:#eaf0f4;white-space:nowrap;color:#23415a}tr:last-child td{border-bottom:0}tbody tr:nth-child(even){background:#f8fafb}
    .controls{display:flex;gap:14px;flex-wrap:wrap;align-items:center;background:white;padding:16px;border:1px solid var(--line);border-radius:10px}
    input[type=search]{padding:10px;border:1px solid #a9bcc8;border-radius:6px;flex:1;min-width:240px;font:inherit}
    button{font:inherit;padding:8px 13px;border:1px solid #b2c4cf;background:#fff;border-radius:6px;cursor:pointer}button:hover{background:#edf7f9}
    .task{border:1px solid var(--line);background:white;border-radius:10px;margin:13px 0}.task>summary{padding:16px 20px;cursor:pointer;display:flex;justify-content:space-between;gap:15px;font-weight:650}
    .task-body{padding:0 20px 22px}.badge{font-size:12px;color:var(--accent);font-weight:500}.status{color:var(--muted)}
    .definition,.prompts{margin:10px 0}.definition>summary,.prompts>summary{cursor:pointer;color:var(--accent)}
    code{font-size:12px;overflow-wrap:anywhere}.definition td:last-child{overflow-wrap:anywhere}.muted{color:var(--muted)}
    footer{margin-top:30px;font-size:13px;color:var(--muted)}[hidden]{display:none!important}
    @media(max-width:650px){main{padding:15px}header{padding:20px}h1{font-size:24px}.task-body{padding:0 12px 15px}}
    @media print{body{background:white}main{padding:0}.controls,button{display:none}header{color:black;background:white;padding:0}.eyebrow{color:#526475}.task,.table-wrap{break-inside:avoid}details>summary{font-weight:bold}}
    '''
    javascript = '''
    const cards=[...document.querySelectorAll('.task')],search=document.getElementById('search'),matched=document.getElementById('matched');
    function filter(){const q=search.value.toLowerCase().trim();let n=0;cards.forEach(c=>{c.hidden=!(c.dataset.search.includes(q)&&(!matched.checked||c.dataset.matched==='true'));if(!c.hidden)n++;});document.getElementById('count').textContent=n+' tasks shown';}
    search.addEventListener('input',filter);matched.addEventListener('change',filter);
    document.getElementById('expand').addEventListener('click',()=>cards.filter(c=>!c.hidden).forEach(c=>c.open=true));
    document.getElementById('collapse').addEventListener('click',()=>cards.forEach(c=>c.open=false));filter();
    let printOpen=[];window.addEventListener('beforeprint',()=>{printOpen=[...document.querySelectorAll('details')].map(d=>[d,d.open]);printOpen.forEach(([d])=>d.open=true)});
    window.addEventListener('afterprint',()=>printOpen.forEach(([d,open])=>d.open=open));
    '''
    excluded = [[c['task'], c.get('blocker') or 'Not selected', 'None; no episodes'] for c in data['coverage'] if not c['included']]
    return '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>RoboDojo · Continuous conditioning errors</title><style>' + css + '</style></head><body><main><header><div class="eyebrow">RoboDojo · Geometric conditioning benchmark</div><h1>Continuous conditioning errors</h1><p>' + esc(f"{data['valid_episodes']} valid episodes · {data['included_tasks']}/{data['catalog_tasks']} tasks · {data['matched_pairs']}/{data['total_pairs']} verified A/B pairs") + '</p><p>Collected ' + esc(data['updated_at']) + ' · ' + esc(str(data['reproduced_event_scores'])) + ' event scores reproduced · ' + esc(str(data['score_mismatches'])) + ' mismatches</p><p>Independent boundary witness validation: ' + esc(str(data.get('recognition_witness_failures', 0))) + ' inconsistent windows</p></header><section class="method"><h2 style="margin-top:0">Measurements and units</h2><p>' + esc(data['method']) + '</p><p class="muted">Distances: mm. Angles: degrees. Components: mean / median. Targets and tolerances use mm/degrees; orientations use wxyz quaternions. Selector metadata keeps named _m/_rad units. Axes 0/1/2 mean local x/y/z. Signed separation and footprint overlap are measurements, not unsigned errors.</p></section>' + ('<h2>Original screen and expansion suites</h2>' + html_table(RUN_HEADERS, run_rows(data)) if data.get('runs') else '') + '<h2>Matched-pair summary</h2>' + html_table((['Suite'] if data.get('runs') else []) + SUMMARY_HEADERS, summary_rows(data)) + '<h2>Task index</h2>' + html_table(([TASK_HEADERS[0], 'Suite', *TASK_HEADERS[1:]] if data.get('runs') else TASK_HEADERS), task_rows(data)) + '<h2>Conditioning and results by task</h2><div class="controls"><label for="search">Find task / action</label><input id="search" type="search" placeholder="Search tasks, actions or conditioning"><label><input id="matched" type="checkbox"> Verified pairs only</label><button id="expand">Expand tasks</button><button id="collapse">Collapse tasks</button><span id="count" aria-live="polite"></span></div>' + ''.join(cards) + '<h2>Eval tasks not run</h2>' + html_table(['Task', 'Reason', 'Conditioning tested'], excluded) + '<h2>Scope and limitations</h2><p>' + esc(data['scope']) + '</p><ul>' + ''.join('<li>' + esc(x) + '</li>' for x in data['limitations']) + '<li>Missing events are not scores. A release error does not establish successful placement.</li><li>Recognizers without observed events do not establish live recognition accuracy.</li></ul><footer>Generated from suite.json, frozen conditioning programs and benchmark_results.json. Exact continuous values: eval-matrix-continuous.json. For integrated reports, raw action outcomes remain in each listed evidence directory’s benchmark_results.json. This HTML is self-contained and needs no network connection.</footer></main><script>' + javascript + '</script></body></html>\n'


def write_continuous_report(manifest, result, matrix, root):
    data = build_report(manifest, result, matrix, root)
    atomic_write_json(root / 'eval-matrix-continuous.json', data)
    atomic_write_text(root / 'EVAL_MATRIX_REPORT.md', report_markdown(data))
    atomic_write_text(root / 'EVAL_MATRIX_REPORT.html', report_html(data))
    return data
