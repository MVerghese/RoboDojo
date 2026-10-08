#!/usr/bin/env python3
"""Clone the reviewed strict-region pair with actual scaled USD strike surface gates."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
REPO=Path(__file__).resolve().parents[2];sys.path.insert(0,str(REPO))
from task.atomic.spec import AtomicProgram
from scripts.atomic.run_suite import validate_suite


def generate(output,source,profile_path):
    if output.exists() and any(output.iterdir()):raise ValueError('use an empty output directory')
    manifest=json.loads(source.read_text());cases=[c for c in manifest['cases'] if c['task']=='play_Xylophone']
    if len(cases)!=2 or {c['prompt_mode'] for c in cases}!={'baseline','conditioned'}:
        raise ValueError('one matched xylophone pair required')
    profile_raw=profile_path.read_bytes();profile=json.loads(profile_raw)
    if profile['asset_key']!='Geometry/xylophone/00000' or profile['mesh_path']!='collision':
        raise ValueError('reviewed xylophone collision profile required')
    programs=[]
    for case in cases:
        raw=Path(case['program']).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=case['program_sha256']:raise ValueError('source program hash changed')
        data=json.loads(raw);data.pop('geometric_instruction',None);programs.append(data)
    if programs[0]!=programs[1]:raise ValueError('source recognition/scoring differs across arms')
    manifest=deepcopy(manifest);manifest['cases']=[];manifest['phase']='live_strike_surface_regions'
    manifest['coverage']=[r for r in manifest['coverage'] if r['task']=='play_Xylophone']
    output.mkdir(parents=True,exist_ok=True);provenance=[]
    for case in cases:
        data=json.loads(Path(case['program']).read_text());strikes=[s for s in data['stages']
            if (s.get('recognition') or {}).get('kind')=='held_tool_strike']
        if len(strikes)!=8:raise ValueError('reviewed eight ordered strikes required')
        for i,stage in enumerate(strikes):
            c=stage['recognition'];tag=f'hit_{i}';binding=profile['bindings'][tag]
            if c['target_point'].get('tag')!=tag or c['target_label']!='xylophone' or c['label']!='mallet' or 'target_candidates' not in c:
                raise ValueError('reviewed strict-region target binding required')
            c['target_surface']={'kind':'model_mesh_region','label':'xylophone','surface_tag':tag,
                'mesh_paths':['collision'],'distance_tolerance_m':.002,'require_contact':True,
                'models':{'xylophone/00000':{'asset_sha256':profile['asset_sha256'],
                    'scaled_bounds_m':profile['scaled_bounds_m'],'local_pose':[0,0,0,1,0,0,0],
                    'calibration_id':'reviewed authored collision component '+tag,
                    **{k:binding[k] for k in ('triangle_indices','expected_triangles_m','landmark_root_pose')}}}}
        path=output/'pairs'/case['checkpoint_id']/case['task']/(case['prompt_mode']+'.program.json')
        path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(data,indent=2)+'\n');AtomicProgram.load(path)
        copied=deepcopy(case);copied.update(program=str(path.resolve()),program_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        manifest['cases'].append(copied)
        provenance.append({'source_suite':str(source.resolve()),'source_program_sha256':case['program_sha256'],
            'profile_path':str(profile_path.resolve()),'profile_sha256':hashlib.sha256(profile_raw).hexdigest(),
            'prompt_mode':case['prompt_mode'],'prompt_changed':False,'changes':'same required live 2 mm collision-mesh-region distance gate in both arms',
            'scope':'actual scaled USD surface region; no exclusive/cooked-collider identity, sound or timing'})
    validate_suite(manifest);(output/'suite.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (output/'clone-provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
    return manifest


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--source-suite',type=Path,required=True)
    p.add_argument('--profile',type=Path,required=True)
    a=p.parse_args();generate(a.output_dir,a.source_suite,a.profile);print('Generated matched live-surface strike pair; source prompts preserved')
