#!/usr/bin/env python3
"""Generate a full-task A/B pair with identical scoring and different prompts."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from task.atomic.spec import AtomicProgram


def generate(program_path, instruction_path, output):
    AtomicProgram.load(program_path)
    base = json.loads(program_path.read_text())
    base.pop('geometric_instruction', None)
    append = instruction_path.read_text().strip()
    if not append:
        raise ValueError('geometric instruction must be nonempty')
    if output.exists() and any(output.iterdir()):
        raise ValueError('use an empty output directory; existing suite inputs are immutable')
    output.mkdir(parents=True, exist_ok=True)
    manifest = {'schema_version': 2, 'task': base['task_name'],
                'mode': 'paired_native_and_geometrically_conditioned',
                'pair_control': 'identical baseline program and scoring; only geometric_instruction differs',
                'limitations': ['one episode per arm; no statistical claim',
                                'layout 0 requires base-run seeds=[0], eval_num=1',
                                'targets require asset feasibility calibration'], 'cases': []}
    for mode in ('baseline', 'conditioned'):
        program = deepcopy(base)
        if mode == 'conditioned':
            program['geometric_instruction'] = append
        path = output / f'{mode}.program.json'
        path.write_text(json.dumps(program, indent=2) + '\n')
        AtomicProgram.load(path)
        manifest['cases'].append({'id': mode, 'task': base['task_name'], 'prompt_mode': mode,
                                  'stage': 'multiple', 'kind': 'multiple', 'program': str(path.resolve()),
                                  'layout_id': 0, 'geometric_prompt_append': append if mode == 'conditioned' else None})
    path = output / 'suite.json'
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    return path


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--program', type=Path, required=True)
    parser.add_argument('--geometric-instruction-file', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    print(generate(args.program, args.geometric_instruction_file, args.output_dir))
