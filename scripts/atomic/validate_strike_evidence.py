#!/usr/bin/env python3
"""Check retained strike witnesses without running or trusting the recognizer.

This checks recorded contact boundaries and sampled kinematics. It cannot
reconstruct contact persistence at intermediate steps absent from the artifact.
It never changes an episode's native or atomic outcome.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from task.atomic.geometry import _rotation


def validate_strike(stage):
    config = stage.get('recognition') or {}
    if config.get('kind') != 'held_tool_strike':
        return {'status': 'not_applicable'}
    events = stage.get('physical_events', {})
    if not {'impact', 'retracted', 'strike'} <= events.keys():
        return {'status': 'unobserved', 'reason': 'complete_strike_events_absent'}
    checks, metrics, unavailable = {}, {}, []

    def close(name, observed, expected):
        checks[name] = bool(np.allclose(observed, expected, rtol=1e-7, atol=1e-9))

    try:
        impact, final = events['impact'], events['strike']
        start, end = impact['physics_step'], final['physics_step']
        checks['event_order'] = (type(start) is int and type(end) is int and
            start < end == events['retracted']['physics_step'] and
            end-start <= config['max_retraction_steps'])
        close('elapsed_steps', final['elapsed_physics_steps'], end-start)
        samples = impact['approach_samples']
        checks['contiguous_preimpact_samples'] = (len(samples) == 2 and
            [s['physics_step'] for s in samples] == [start-2, start-1])
        dt = samples[1]['dt_s']
        checks['finite_fixed_dt'] = math.isfinite(dt) and dt > 0 and samples[0]['dt_s'] == dt
        relative = []
        for index, sample in enumerate(samples):
            tool, target = np.asarray(sample['tool_pose']), np.asarray(sample['target_pose'])
            close(f'approach_relative_position_{index}', sample['relative_position'], tool[:3]-target[:3])
            relative.append(tool[:3]-target[:3])
        velocity = (relative[1]-relative[0])/dt
        speed = -float(velocity @ _rotation(samples[1]['target_pose'][3:])[:, 2])
        close('approach_velocity', impact['relative_velocity_m_s'], velocity)
        close('approach_speed', impact['toward_surface_speed_m_s'], speed)
        checks['approach_threshold'] = speed >= config['min_approach_speed_m_s']
        metrics['approach_speed_m_s'] = speed
        points = np.asarray(impact['contact_points'], dtype=float)
        rows = impact['tool_target_contacts']
        checks['contact_point_count'] = points.shape == (len(rows), 3) and len(rows) > 0
        if 'target_candidates' in config:
            from task.atomic.target_regions import validate_target_region_witness
            checks.update(validate_target_region_witness(config,impact))
        distances = {}
        for side in ('tool', 'target'):
            distances[side] = np.linalg.norm(points-np.asarray(impact[f'{side}_landmark_position']), axis=1)
            close(f'{side}_contact_distances', impact[f'{side}_landmark_distances_m'], distances[side])
            checks[f'{side}_contact_neighborhood'] = bool(np.all(distances[side] <= config[f'{side}_radius_m']))
            metrics[f'max_{side}_contact_distance_m'] = float(max(distances[side]))
        impulse = sum(float(np.linalg.norm(row['impulse'])) for row in rows)
        close('impact_impulse', impact['total_impulse_ns'], impulse)
        checks['impact_force'] = (impulse >= config['min_impulse_ns'] and all(
            np.isfinite(row['impulse']).all() and np.linalg.norm(row['impulse']) > 1e-9
            and np.isclose(np.linalg.norm(row['normal_world']), 1., atol=1e-3, rtol=0)
            and row['force_report_physics_step'] == start for row in rows))
        metrics['impact_impulse_ns'] = impulse
        arms = []
        for boundary, event in (('impact', impact), ('completion', final)):
            hold = event['held_contact']; step = event['physics_step']
            fingers = set(row['finger_body'] for row in hold['contacts'])
            checks[f'{boundary}_hold'] = (len(fingers) >= 2 and fingers == set(hold['finger_bodies'])
                and hold['consecutive_contact_steps'] >= config['min_contact_steps']
                and hold['contact_interval_start_step'] == step-hold['consecutive_contact_steps']+1
                and all(row['arm'] == hold['resolved_arm'] and
                    row['force_report_physics_step'] == step and
                    np.isfinite(row['impulse']).all() and np.linalg.norm(row['impulse']) > 1e-9
                    for row in hold['contacts']))
            arms.append(hold['resolved_arm'])
        checks['same_arm_hold_interval'] = arms[0] == arms[1] and final['held_contact']['contact_interval_start_step'] <= start
        checks['reported_retraction_threshold'] = (final['rise_m'] >= config['min_retraction_m']
            and final['separated_steps'] >= config['min_retraction_steps'])
        close('retraction_event_rise', events['retracted']['rise_m'], final['rise_m'])
        close('retraction_event_separation', events['retracted']['separated_steps'], final['separated_steps'])
        paths = [row for row in stage.get('trajectories', {}).values()
            if row.get('condition', {}).get('measurement') == config['tool_point']
            and row['condition'].get('reference') == config['target_point']
            and row['condition'].get('start_event') == {'kind': 'recognition_event', 'name': 'impact'}
            and row['condition'].get('end_event') == {'kind': 'recognition_event', 'name': 'strike'}]
        if len(paths) != 1 or not paths[0].get('complete') or not paths[0].get('samples'):
            unavailable.append('matching_complete_retraction_trajectory_absent_or_ambiguous')
        else:
            path = paths[0]; raw = path['samples']
            checks['contiguous_retraction_samples'] = (not path.get('failures') and
                [s['physics_step'] for s in raw] == list(range(start, end+1)))
            heights = [float((_rotation(s['reference_state'][3:]).T @
                (np.asarray(s['measured_state'][:3])-s['reference_state'][:3]))[2]) for s in (raw[0], raw[-1])]
            rise = heights[1]-heights[0]
            close('retraction_rise_from_raw_poses', final['rise_m'], rise)
            metrics['retraction_m'] = rise
            metrics['duration_s'] = sum(s['dt_s'] for s in raw[1:])
            checks['finite_retraction_dt'] = all(math.isfinite(s['dt_s']) and s['dt_s'] > 0 for s in raw)
        checks['finite_metrics'] = all(math.isfinite(v) for v in metrics.values())
    except (KeyError, TypeError, ValueError, IndexError, ZeroDivisionError) as error:
        checks['well_formed_evidence'] = False
        unavailable.append(f'{type(error).__name__}: {error}')
    failed = [name for name, ok in checks.items() if not ok]
    return {'status': 'inconsistent_evidence' if failed else 'partial_evidence' if unavailable else 'consistent_evidence',
        'checks': checks, 'failed_checks': failed, 'unavailable': unavailable, 'metrics': metrics,
        'scope': 'recorded impact/completion contacts and sampled approach/retraction kinematics; intermediate contact persistence is not independently reconstructed'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    data = args.report.read_bytes(); report = json.loads(data); rows = []
    for native in report.get('native_results', []):
        details = native.get('details', {})
        for episode, detail in (details.items() if isinstance(details, dict) else enumerate(details)):
            for stage in detail.get('atomic_sequence', {}).get('stages', []):
                if (stage.get('recognition') or {}).get('kind') == 'held_tool_strike':
                    rows.append({'episode': str(episode), 'layout_id': detail['layout_id'],
                        'stage_id': stage['stage_id'], **validate_strike(stage)})
    args.output.write_text(json.dumps({'report': str(args.report.resolve()),
        'report_sha256': hashlib.sha256(data).hexdigest(),
        'validator_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'strikes': rows}, indent=2)+'\n')
    print(json.dumps({'output': str(args.output), 'statuses': {s: sum(r['status'] == s for r in rows)
        for s in sorted({r['status'] for r in rows})}}))


if __name__ == '__main__':
    main()
