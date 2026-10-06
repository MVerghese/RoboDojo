"""Combine the original screen and expansion evidence without pooling runtimes."""
import argparse
from copy import deepcopy
import errno
import json
import os
from pathlib import Path

from scripts.atomic.continuous_report import build_report, report_html, report_markdown
from scripts.atomic.report_eval_matrix import aggregate
from scripts.atomic.storage import atomic_write_json, atomic_write_text


def integrate(suites):
    """Suites are (name, evidence directory, manifest, result, continuous data)."""
    combined = deepcopy(suites[0][4])
    combined.update(tasks=[], summary=[], runs=[], limitations=[], checkpoints={})
    counts = ('valid_episodes', 'matched_pairs', 'total_pairs',
              'reproduced_event_scores', 'score_mismatches')
    for key in counts:
        combined[key] = 0
    included = set()
    for name, directory, manifest, result, data in suites:
        rows = {r['case_id']: r for r in result['cases']}
        combined['checkpoints'].update(data['checkpoints'])
        for task in deepcopy(data['tasks']):
            task.update(suite=name, evidence_directory=str(directory), provenance={})
            task['unbound_families'] = next((c.get('unbound_families', [])
                for c in data['coverage'] if c['task'] == task['task']), [])
            for mode in ('baseline', 'conditioned'):
                row = rows[task[mode + '_case']]
                task['provenance'][mode] = {k: row.get(k) for k in (
                    'case_id', 'status', 'completed_episodes', 'full_task_success',
                    'runtime_sha256', 'source_archive_sha256')}
            combined['tasks'].append(task)
            included.add(task['task'])
        # Retain each suite's matched summary, never average different targets
        # or allow similarly named stages to overwrite another suite's events.
        combined['summary'].extend(dict(row, suite=name) for row in deepcopy(data['summary']))
        for key in counts:
            combined[key] += data.get(key) or 0
        combined['runs'].append({
            'suite': name, 'evidence_directory': str(directory),
            'cases': len(manifest['cases']), 'collected': result['completed_cases'],
            'completed_episodes': sum(r['status'] == 'passed' and r.get('completed_episodes') == 1
                                      for r in result['cases']),
            **{k: data.get(k) or 0 for k in counts},
            'reproduced_flow_scores': result.get('reproduced_flow_scores', 0),
            'updated_at': data['updated_at']})
        combined['limitations'].extend(name + ': ' + text for text in data['limitations'])
    # The first suite is the original catalog screen. Preserve its exclusions,
    # updating task coverage where an expansion now provides an observer pair.
    for row in combined['coverage']:
        row['included'] = row['task'] in included
    combined['included_tasks'] = len(included)
    combined['updated_at'] = max(s[4]['updated_at'] for s in suites)
    combined['scope'] = ('Original evaluation screen plus additional-conditioning suites. '
        'Each task/suite entry is a distinct frozen comparison. Pending cases remain visible; '
        'verified-pair summaries are kept separate by suite, checkpoint, action and conditioning. '
        'Counts of tasks refer to unique eval tasks; pair and episode counts include repeated tasks.')
    combined['method'] += (' This integrated report keeps matched summaries separate by suite. '
        'Identical condition names in different suites may use different targets or runtimes. '
        'Native task success and collection status are shown separately from geometric observations.')
    return combined


def generate(original, expansion_root, output):
    directories = [original, *sorted(expansion_root.glob('geometry-*-1006'))]
    suites = []
    for directory in directories:
        source = directory / 'benchmark_results.json'
        if not source.exists():
            if directory == original:
                raise FileNotFoundError(source)
            continue
        manifest = json.loads((directory / 'suite.json').read_text())
        result = json.loads(source.read_text())
        data = build_report(manifest, result, aggregate(manifest, result), directory)
        suites.append((directory.name, directory.resolve(), manifest, result, data))
    data = integrate(suites)
    output.mkdir(parents=True, exist_ok=True)
    atomic_write_json(output / 'eval-matrix-continuous.json', data)
    atomic_write_text(output / 'EVAL_MATRIX_REPORT.md', report_markdown(data))
    atomic_write_text(output / 'EVAL_MATRIX_REPORT.html', report_html(data))
    return data


def publish_original(original, output):
    """Retain the original report, then refresh the user's existing report paths.

    Lustre's project inode quota may prevent an atomic replacement. Only that
    error permits updating an existing inode; a durable copy is kept on home.
    Operational manifests, raw results and frozen programs are never changed.
    """
    backups = output / 'original-report-backup'
    backups.mkdir(exist_ok=True)
    for name in ('EVAL_MATRIX_REPORT.md', 'EVAL_MATRIX_REPORT.html', 'eval-matrix-continuous.json'):
        target = original / name
        if not target.is_file():
            raise FileNotFoundError(target)
        saved = backups / name
        if not saved.exists():
            atomic_write_text(saved, target.read_text())
        content = (output / name).read_text()
        try:
            atomic_write_text(target, content)
        except OSError as error:
            if error.errno != errno.EDQUOT:
                raise
            # Existing inode, with a durable original and complete new copy
            # already saved on home. Never bypass permission/network errors.
            with target.open('w') as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--original', type=Path, required=True)
    parser.add_argument('--expansion-root', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--publish-original', action='store_true')
    args = parser.parse_args()
    data = generate(args.original, args.expansion_root, args.output_dir)
    if args.publish_original:
        publish_original(args.original, args.output_dir)
    print(f"Integrated {len(data['runs'])} suites, {len(data['tasks'])} task comparisons, "
          f"{data['valid_episodes']} valid episodes into {args.output_dir}")
