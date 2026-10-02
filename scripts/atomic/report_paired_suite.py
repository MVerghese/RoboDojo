"""Human-readable paired report, generated from collected evidence only."""
import json
import math
from pathlib import Path
from scripts.atomic.storage import atomic_write_text


def metrics(score):
    if score.get('status') != 'reproduced':
        return score.get('status', 'unobserved')
    result = score['recorded_result']
    c = result['components']
    values = []
    for key, label, scale, suffix in (
        ('position_m', 'position error', 1000, ' mm'),
        ('displacement_m', 'contact region error', 1000, ' mm'),
        ('orientation_rad', 'angle error', 180 / math.pi, '°'),
        ('signed_separation_m', 'vertical separation', 100, ' cm'),
        ('footprint_overlap_fraction', 'footprint overlap', 100, '%'),
    ):
        if key in c:
            values.append(f'{label} {c[key] * scale:.2f}{suffix}')
    return ('PASS: ' if result['passed'] else 'FAIL: ') + ', '.join(values or [str(c)])


def write_report(manifest, result, root):
    total = len(manifest['cases'])
    if total % 2:
        raise ValueError('paired report requires baseline/conditioned pairs')
    for base, conditioned in zip(manifest['cases'][::2], manifest['cases'][1::2]):
        if (base['prompt_mode'], conditioned['prompt_mode']) != ('baseline', 'conditioned') or base['task'] != conditioned['task']:
            raise ValueError('paired report requires adjacent same-task baseline/conditioned cases')
    completed_episodes = sum(r.get('completed_episodes', 0) for r in result['cases'])
    rejected = list((root / 'runs').glob('*/attempts/attempt-*/eval_report.json'))
    lines = ['# Paired geometric benchmark', '',
             f"Completed policy episodes: **{completed_episodes} / {total}**. Collected case results: **{result['completed_cases']} / {total}**. "
             f"Score mismatches: **{result['score_mismatches']}**. Archived infrastructure attempts: **{len(rejected)}**.", '',
             'Each baseline receives the baseline full-task instruction (native unless explicitly overridden). Its conditioned partner receives '
             'the same instruction plus the geometric text below. Both are evaluated against the same '
             'geometric targets. Atomic stages are observers; they do not switch the policy prompt.', '',
             '| Task | Prompt | Pipeline | Native task success | Atomic action recognition | Geometric event scores |',
             '| --- | --- | --- | --- | --- | --- |']
    for row in result['cases']:
        native = row.get('full_task_success')
        native_text = ', '.join('yes' if x else 'no' for x in native) if native else 'pending'
        actions, geometry = [], []
        for stage in row.get('atomic_scores', []):
            contact_missing = any(c.get('status') == 'contact_not_observed_at_event'
                                  for c in stage['conditions'].values())
            actions.append(stage['stage_id'] + ': ' + ('yes' if stage['action_success'] else 'no') +
                           (' (optional route not selected)' if not stage.get('required',True) else
                            ' (unreached)' if not stage.get('reached', True) else
                            ' (interaction unverified)' if contact_missing and not stage['action_success'] else ''))
            for name, score in stage['conditions'].items():
                geometry.append(name + ': ' + metrics(score))
            for name,score in stage.get('trajectories',{}).items():
                value=score.get('recorded_result',{})
                geometry.append(name+' path: '+(f"{'PASS' if value['passed'] else 'FAIL'}, max deviation {value['max_deviation_m']*1000:.2f} mm, {value['visited_waypoints']}/{value['waypoint_count']} ordered waypoints" if value.get('status')=='scored' else value.get('status',score['status'])))
            if stage.get('selection'):
                selection=stage['selection']
                unscored_status = (selection['target_status'] if selection['target_status'] != 'resolved' else
                                   (selection.get('observed') or {}).get('status', 'contact_not_observed'))
                geometry.append('selection: '+('PASS' if selection['passed'] else 'FAIL' if selection['passed'] is False else unscored_status)+
                                (' (score mismatch)' if selection['status']=='score_mismatch' else ''))
        lines.append(f"| {row['task']} | {row['prompt_mode']} | {row['status']} | {native_text} | "
                     f"{'; '.join(actions) or 'pending'} | {'; '.join(geometry) or 'pending'} |")
    lines += ['', '## Pair controls and captured prompts', '']
    controls_path = root / 'pair-controls.json'
    if controls_path.exists():
        controls = json.loads(controls_path.read_text())
        lines += [f"Immutable runtime identical across all eight bundles: **{controls['runtime_identical_all_eight']}**. "
                  f"Checkpoint/seeds identical: **{controls['checkpoint_and_seeds_identical']}**. "
                  f"Packaged programs match manifest: **{controls['all_programs_match_manifest']}**.", '',
                  f"Policy adapter mapping: `{controls['adapter_mapping']}` "
                  f"at `{controls['adapter_source']}`.", '']
    by_id = {r['case_id']: r for r in result['cases']}
    for base, conditioned in zip(manifest['cases'][::2], manifest['cases'][1::2]):
        lines += [f"### {base['task']}", '', '**Geometric append:**', '', conditioned['geometric_prompt_append'], '']
        prompts = []
        for case in (base, conditioned):
            row = by_id[case['id']]
            history = [p for episode in row.get('policy_prompt_history', []) for p in episode]
            if not history:
                lines += [f"**{case['prompt_mode']} delivered prompt:** pending collection.", '']
                prompts.append(None)
            else:
                values = [p['instruction'] for p in history]
                lines += [f"**{case['prompt_mode']} delivered prompt:**", '', '```text', *values, '```', '']
                prompts.append(values[0] if len(values) == 1 else None)
            contact = row.get('contact_instrumentation')
            if contact:
                lines += [f"**{case['prompt_mode']} contact instrumentation:** " +
                          '; '.join(f"reports={x['reports']}, steps={x['steps']}, callback errors={len(x['errors'])}" for x in contact if x), '']
        if all(p is not None for p in prompts):
            append = conditioned['geometric_prompt_append']
            expected = prompts[0] + ' ' + append
            lines += [f"**Only geometric append differs in the delivered prompts:** {prompts[1] == expected}.", '']
        a = by_id[base['id']].get('atomic_scores', [])
        b = by_id[conditioned['id']].get('atomic_scores', [])
        if a and b:
            layouts_a, layouts_b = {x['layout_id'] for x in a}, {x['layout_id'] for x in b}
            planned = {base['layout_id']}
            lines += [f"**Actual layout IDs:** baseline {sorted(layouts_a)}, conditioned {sorted(layouts_b)}; "
                      f"matched planned layout {base['layout_id']}: {layouts_a == layouts_b == planned and conditioned['layout_id'] == base['layout_id']}.", '']
    lines += ['## Interpretation', '',
              '- Native task success, audited atomic recognition, and geometric adherence are separate outcomes.',
              '- Contact scores use actual PhysX finger/object manifold points, with no end-effector fallback.',
              '- Grasp success requires two finger bodies of the same arm plus the required lift.',
              '- Pick/push recognition requires contact evidence at the declared lift/motion event. A missing contact leaves the interaction unverified, even when a goal-pose condition passes; it does not prove no push occurred.',
              '- Object “above” requires signed relative height and projected mesh-footprint overlap.',
              '- Pour recognition checks whole balls within finite vase bounds; insertion uses annotated connector/opening frames.',
              '- Missing/unreached events have no geometric pass. Callback or collection errors are infrastructure failures.',
              '- One episode per prompt establishes an integration pilot, not a statistical steering effect.',
              '', '## Evidence', '',
              f"- Manifest: `{root / 'suite.json'}`",
              f"- Full results: `{root / 'benchmark_results.json'}`",
              '- Per-run directories contain eval_report.json, atomic-score-audit.json, gpu_admission.json and layout-linked action traces.', '']
    restart_path = root / 'live-audit-restart.json'
    if restart_path.exists():
        restart = json.loads(restart_path.read_text())
        lines += ['## Excluded initial instrumentation attempts', '',
                  restart['reason'], '',
                  'All initial attempts are excluded from the paired comparison and retained in '
                  f"`{root / 'invalid-instrumentation-attempts'}`. Corrected runtime commit: "
                  f"`{restart['new_git_commit']}`.", '']
    atomic_write_text(root / 'REPORT.md', '\n'.join(lines))
