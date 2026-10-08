#!/usr/bin/env python3
"""Distinct actual vessel-center pose target, derived from reviewed mouth geometry."""
import argparse
from copy import deepcopy
import hashlib,json,math
from pathlib import Path
import sys
import numpy as np
REPO=Path(__file__).resolve().parents[2];sys.path.insert(0,str(REPO))
from task.atomic.geometry import _rotation
from task.atomic.spec import AtomicProgram
from task.atomic.slot_semantics import condition_slot
from scripts.atomic.run_suite import validate_suite
from scripts.atomic.storage import atomic_write_json


def vessel_condition(stage):
    mouth=deepcopy(stage['recognition']['source_exit']['opening'])
    if mouth['label']!='bottle' or mouth['kind']!='model_calibrated_frame' or set(mouth['models'])!={'wuliangye/00000'}:
        raise ValueError('reviewed actual bottle mouth binding required')
    row=mouth['models']['wuliangye/00000'];local=np.asarray(row['local_pose'],float);bounds=np.asarray(row['scaled_bounds_m'],float)
    if local.shape!=(7,) or bounds.shape!=(2,3) or not np.isfinite(local).all() or not np.isfinite(bounds).all() or np.any(bounds[0]>=bounds[1]):
        raise ValueError('finite reviewed actual scaled vessel geometry required')
    if not np.allclose(local[3:],[1,0,0,0],rtol=0,atol=1e-12):raise ValueError('mouth root axes must match reviewed body axes')
    center=bounds.mean(0);q=[math.sqrt(.5),0,-math.sqrt(.5),0]
    # The desired physical mouth target is independent of policy outcomes.
    expected=np.array([0,0,.08])-_rotation(q)@(local[:3]-center)
    row['local_pose']=[*center.tolist(),1,0,0,0]
    row['calibration_id']='actual scaled mesh-bounds center with vessel root axes; '+row['asset_sha256']
    condition={'id':'vessel_center_at_first_transfer','slot':'source pour pose','kind':'pose','measurement':mouth,
        'reference':deepcopy(stage['recognition']['flow']['opening']),
        'expected':{'position':expected.tolist(),'orientation':q},'tolerance':.025,'angle_tolerance_rad':math.pi/6,
        'event':{'kind':'recognition_event','name':'first_transfer'},'track_closest':False}
    proof={'source_mouth_local_pose':local.tolist(),'vessel_center_local_pose':row['local_pose'],
        'desired_mouth_offset_m':[0,0,.08],'derived_vessel_center_offset_m':expected.tolist(),
        'scope':'reviewed rigid-frame composition; not IK reachability or a target fitted to policy outcomes'}
    return condition,proof


def generate(output,source):
    if output.exists() and any(output.iterdir()):raise ValueError('fresh empty output directory required')
    manifest=json.loads(source.read_text());cases=[c for c in manifest['cases'] if c['task']=='pour_liquid_into_cup']
    if len(cases)!=2 or [c['prompt_mode'] for c in cases]!=['baseline','conditioned']:raise ValueError('one reviewed liquid pair required')
    originals=[]
    for c in cases:
        raw=Path(c['program']).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=c['program_sha256']:raise ValueError('source program changed')
        d=json.loads(raw);d.pop('geometric_instruction',None);originals.append(d)
    if originals[0]!=originals[1]:raise ValueError('source controls differ beyond prompt')
    output.mkdir(parents=True);manifest=deepcopy(manifest);manifest['cases']=[];manifest['phase']='distinct_vessel_center_pose'
    if 'coverage' in manifest:manifest['coverage']=[r for r in manifest['coverage'] if r['task']=='pour_liquid_into_cup']
    for c,original in zip(cases,originals):
        d=deepcopy(original);pour=next(s for s in d['stages'] if s['family']=='pour')
        condition,proof=vessel_condition(pour)
        for stage in d['stages']:
            for old in stage.get('geometry',[]):old['slot']=condition_slot(stage,old)[0]
        pour['geometry'].append(condition)
        text='At the first source-qualified liquid particle transfer into the cup core while the bottle is held and tilted, '
        text+='put the actual bottle scaled mesh-bounds center at offset '+json.dumps([v*1000 for v in condition['expected']['position']])
        text+=' mm from the live calibrated cup opening, in its current axes, within 25 mm Euclidean distance. '
        text+='Match bottle root axes to minus 90 degrees about the cup opening y axis, within 30 degrees full orientation error. '
        text+='This conditions the vessel body center and root axes; the bottle mouth is a separate landmark.'
        if c['prompt_mode']=='conditioned':d['geometric_instruction']=text
        path=output/'pairs'/c['checkpoint_id']/c['task']/(c['prompt_mode']+'.program.json');path.parent.mkdir(parents=True,exist_ok=True)
        atomic_write_json(path,d);AtomicProgram.load(path);copy=deepcopy(c)
        copy.update(program=str(path.resolve()),program_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            geometric_prompt_append=d.get('geometric_instruction'));manifest['cases'].append(copy)
    validate_suite(manifest);atomic_write_json(output/'suite.json',manifest)
    atomic_write_json(output/'clone-provenance.json',{'source_suite':str(source.resolve()),'derivation':proof,
        'changes':'identical added actual vessel-center scoring; historical mouth slot corrected to spout in both fresh programs; append isolates vessel pose; physical recognition unchanged'})


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',required=True,type=Path)
    p.add_argument('--source-suite',required=True,type=Path);a=p.parse_args();generate(a.output_dir,a.source_suite)
    print('Generated distinct actual vessel-center pose pair')
