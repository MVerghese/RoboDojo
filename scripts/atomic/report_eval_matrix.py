"""Aggregate observed scores without converting absent events into outcomes."""
from collections import defaultdict
import statistics

from scripts.atomic.storage import atomic_write_json, atomic_write_text


def delivered_prompt(row):
    values = {p['instruction'] for episode in row.get('policy_prompt_history', []) for p in episode}
    return next(iter(values)) if len(values) == 1 else None


def valid_episode(row):
    health = row.get('contact_instrumentation', [])
    return (row['status'] == 'passed' and row.get('completed_episodes') == 1
            and len(row.get('full_task_success', [])) == 1
            and bool(health) and all(h and h.get('steps', 0) > 0 and h.get('reports', 0) > 0
                                    and not h.get('errors') for h in health))


def aggregate(manifest, result):
    rows = {r['case_id']: r for r in result['cases']}
    pairs, groups = [], defaultdict(list)
    for a, b in zip(manifest['cases'][::2], manifest['cases'][1::2]):
        ra, rb = rows[a['id']], rows[b['id']]
        reasons = []
        if not all(valid_episode(r) for r in (ra, rb)):
            reasons.append('missing valid completed episode or unhealthy contact instrumentation')
        if not ra.get('runtime_sha256') or ra.get('runtime_sha256') != rb.get('runtime_sha256'):
            reasons.append('runtime equality unverified')
        if not ra.get('source_archive_sha256') or ra.get('source_archive_sha256') != rb.get('source_archive_sha256'):
            reasons.append('source archive equality unverified')
        if not ra.get('execution_controls') or ra.get('execution_controls') != rb.get('execution_controls'):
            reasons.append('checkpoint/inference/execution equality unverified')
        expected_checkpoint = manifest.get('checkpoints', {}).get(a.get('checkpoint_id'), {}).get('checkpoint')
        if expected_checkpoint and any(r.get('checkpoint') != expected_checkpoint for r in (ra, rb)):
            reasons.append('checkpoint differs from manifest')
        pa, pb = delivered_prompt(ra), delivered_prompt(rb)
        if pa is None or pb != pa + ' ' + b['geometric_prompt_append']:
            reasons.append('delivered prompt append unverified')
        layouts = [{s['layout_id'] for s in r.get('atomic_scores', [])} for r in (ra, rb)]
        if any(x != {a.get('layout_id', 0)} for x in layouts):
            reasons.append('actual layout unverified')
        if any(c.get('status') == 'score_mismatch' for r in (ra, rb)
               for s in r.get('atomic_scores', []) for c in s['conditions'].values()):
            reasons.append('offline geometric audit mismatch')
        matched = not reasons
        pairs.append({'task': a['task'], 'checkpoint_id': a.get('checkpoint_id', 'default'),
                      'matched': matched, 'exclusions': reasons,
                      'baseline_case': a['id'], 'conditioned_case': b['id']})
        # Single completed episodes are useful descriptive results, even while
        # their partner is queued. Matched-only aggregates are also emitted.
        for row in (ra, rb):
            if not valid_episode(row):
                continue
            for stage in row.get('atomic_scores', []):
                key = (row['checkpoint_id'], row['task'], stage.get('family') or 'unknown', row['prompt_mode'])
                groups[key].append((stage, matched))
    output = []
    for key, stages in sorted(groups.items()):
        for scope in ('all_valid_episodes', 'matched_pairs_only'):
            selected = [s for s, matched in stages if scope == 'all_valid_episodes' or matched]
            if not selected:
                continue
            conditions = defaultdict(list)
            for stage in selected:
                for ident, score in stage['conditions'].items():
                    conditions[(ident, score.get('kind', 'unknown'), score.get('slot', 'unknown'))].append(score)
            metrics = []
            for (ident, kind, slot), scores in sorted(conditions.items()):
                observed = [s['recorded_result'] for s in scores if s['status'] == 'reproduced']
                components = defaultdict(list)
                for score in observed:
                    for name, value in score['components'].items():
                        components[name].append(value)
                statuses = defaultdict(int)
                for s in scores:
                    statuses[s['status']] += 1
                metrics.append({'condition_id': ident, 'kind': kind, 'slot': slot,
                    'declared': len(scores), 'observed': len(observed),
                    'passed_when_observed': sum(s['passed'] for s in observed),
                    'unobserved_or_invalid': len(scores) - len(observed), 'statuses': dict(statuses),
                    'components': {k: {'n': len(v), 'mean': statistics.mean(v), 'median': statistics.median(v)}
                                   for k, v in components.items()}})
            output.append(dict(zip(('checkpoint_id', 'task', 'family', 'prompt_mode'), key)) | {
                'scope': scope, 'observer_instances': len(selected),
                'candidate_instances': sum(not s.get('required', True) for s in selected),
                'reached_instances': sum(s.get('reached', True) for s in selected),
                'successful_actions': sum(s['action_success'] for s in selected), 'geometry': metrics})
    return {'updated_at': result['updated_at'], 'coverage': manifest['coverage'], 'pairs': pairs,
            'valid_episodes': sum(valid_episode(r) for r in rows.values()),
            'matched_pairs': sum(p['matched'] for p in pairs), 'total_pairs': len(pairs), 'metrics': output,
            'limitations': manifest['limitations'], 'scope': manifest['scope']}


def write_matrix_report(manifest, result, root):
    data = aggregate(manifest, result)
    atomic_write_json(root / 'eval-matrix-results.json', data)
    included = sum(c['included'] for c in manifest['coverage'])
    lines = ['# RoboDojo eval matrix baseline', '',
        f"Included tasks: **{included}/{len(manifest['coverage'])}**. Valid episodes: **{data['valid_episodes']}/{len(result['cases'])}**. "
        f"Verified matched pairs: **{data['matched_pairs']}/{data['total_pairs']}**.", '',
        'Full-task policy prompts are fixed within each episode. Candidate observers measure the first recognized instance per bound object; '
        'they do not establish complete task segmentation. Unobserved conditions have no error or pass score. '
        'Component names ending in `_m` use metres; `_rad` use radians; fractions are unitless. '
        'Action success is recorded by live recognition; the offline audit independently reproduces geometry.', '',
        '| Checkpoint | Task | Action | Prompt | Successful actions / observers | Observed / declared conditions | Geometry passes / observed |',
        '| --- | --- | --- | --- | --- | --- | --- |']
    for m in data['metrics']:
        if m['scope'] != 'all_valid_episodes':
            continue
        declared = sum(c['declared'] for c in m['geometry'])
        observed = sum(c['observed'] for c in m['geometry'])
        passed = sum(c['passed_when_observed'] for c in m['geometry'])
        lines.append(f"| {m['checkpoint_id']} | {m['task']} | {m['family']} | {m['prompt_mode']} | "
            f"{m['successful_actions']}/{m['observer_instances']} | {observed}/{declared} | {passed}/{observed} |")
    lines += ['', 'Counts describe observer instances, including optional object candidates; they are not a fraction of required native actions.',
              'Continuous errors, unobserved-event reasons, and separate matched-only aggregates are in `eval-matrix-results.json`.', '',
              '## Excluded or partially bound tasks', '']
    for c in manifest['coverage']:
        if c.get('blocker') or c['unbound_families']:
            lines.append(f"- **{c['task']}**: " + (c.get('blocker') or 'included with partial observers') +
                         (f"; unbound families: {', '.join(c['unbound_families'])}" if c['unbound_families'] else ''))
    lines += ['', '## Limitations', '', *('- ' + x for x in manifest['limitations'])]
    atomic_write_text(root / 'EVAL_MATRIX_REPORT.md', '\n'.join(lines) + '\n')
