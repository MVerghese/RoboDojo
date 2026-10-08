#!/usr/bin/env python3
"""Matched, isolated spout-factor trials at the first qualified source-mouth exit."""
import argparse
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import sys
REPO=Path(__file__).resolve().parents[2];sys.path.insert(0,str(REPO))
from task.atomic.spec import AtomicProgram
from scripts.atomic.run_suite import validate_suite


def conditions(stage,factor):
    mouth=deepcopy(stage['recognition']['source_exit']['opening'])
    opening=deepcopy(stage['recognition']['flow']['opening'])
    if mouth['kind']!='model_calibrated_frame' or opening['kind']!='model_calibrated_frame':
        raise ValueError('reviewed actual model/file/scale mouth frames required')
    event={'kind':'recognition_event','name':'source_exit'}
    common={'slot':'spout','measurement':mouth,'reference':opening,'event':event,'track_closest':False}
    if factor in ('point','displacement','spatial_relation'):
        common['measurement']['kind']='model_calibrated_position'
    point=[0,0,.08];orientation=[math.sqrt(.5),0,-math.sqrt(.5),0]
    prefix='At the first source-qualified liquid exit through the actual bottle mouth while held and tilted, '
    if factor=='point':
        common['reference']['time']='stage_start'
        rows=[{**common,'id':'spout_initial_point','kind':'point','expected':point,'tolerance':.025}]
        text=prefix+'put the calibrated bottle mouth at [0, 0, 80] mm in the cup opening frame frozen at the beginning of the episode, within 25 mm XYZ distance. This target stays fixed if the cup moves.'
    elif factor=='pose':
        rows=[{**common,'id':'spout_live_pose','kind':'pose','expected':{'position':point,'orientation':orientation},
            'tolerance':.025,'angle_tolerance_rad':math.pi/6}]
        text=prefix+'put the calibrated bottle mouth 80 mm along positive z above the live calibrated cup opening, with zero x/y offset, within 25 mm XYZ distance. Match minus 90 degrees about the cup opening y axis, within 30 degrees full orientation error.'
    elif factor=='displacement':
        rows=[{**common,'id':'spout_live_offset','kind':'relative_displacement','expected':point,'tolerance':.025}]
        text=prefix+'keep the calibrated bottle mouth at offset [0, 0, 80] mm from the live calibrated cup opening, expressed in its current axes, within 25 mm XYZ displacement error.'
    elif factor=='orientation':
        rows=[{**common,'id':'spout_live_z','kind':'relative_orientation','expected':orientation,
            'orientation_axes':[2],'tolerance':math.pi/6}]
        text=prefix+'point the calibrated bottle mouth local z axis along the negative x direction of the live calibrated cup opening frame, within 30 degrees. Rotation about that mouth axis is unrestricted.'
    elif factor=='spatial_relation':
        corridor=deepcopy(opening)
        for row in corridor['models'].values():
            # These reviewed opening frames have identity root-local rotations.
            if row['local_pose'][3:]!=[1,0,0,0]:raise ValueError('reviewed opening root axes required')
            row['local_pose'][2]+=.08;row['calibration_id']+='; requested point corridor 80mm above opening'
        rows=[{**common,'id':'spout_above_opening','kind':'spatial_relation','relation_scope':'points',
            'expected':'above','margin':.04,'tolerance':.001},
            {**common,'reference':corridor,'id':'spout_opening_corridor','kind':'spatial_relation',
            'relation_scope':'points','expected':'inside_box','half_extents':[.01,.01,.04],'tolerance':.001}]
        text=prefix+'keep the actual bottle mouth at least 40 mm above the live cup opening along its positive z axis, allowing 1 mm shortfall. Keep the mouth point within the 20 x 20 mm column centered over the opening and between 40 and 120 mm above it, allowing 1 mm point-box outside distance. This is mouth-point geometry, not whole-bottle footprint or cavity containment.'
    else:raise ValueError('unknown factor')
    return rows,text


def generate(output,source,factor):
    if output.exists() and any(output.iterdir()):raise ValueError('use an empty output directory')
    manifest=json.loads(source.read_text());cases=[c for c in manifest['cases'] if c['task']=='pour_liquid_into_cup']
    if len(cases)!=2 or {c['prompt_mode'] for c in cases}!={'baseline','conditioned'}:raise ValueError('one matched liquid pair required')
    originals=[]
    for case in cases:
        raw=Path(case['program']).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=case['program_sha256']:raise ValueError('source program hash changed')
        data=json.loads(raw);data.pop('geometric_instruction',None);originals.append(data)
    if originals[0]!=originals[1]:raise ValueError('source recognition/scoring differs across arms')
    manifest=deepcopy(manifest);manifest['cases']=[];manifest['phase']='isolated_spout_'+factor
    if 'coverage' in manifest:
        manifest['coverage']=[r for r in manifest['coverage'] if r['task']=='pour_liquid_into_cup']
    manifest['contact_frame_bindings']=[r for r in manifest.get('contact_frame_bindings',[]) if r['task']=='pour_liquid_into_cup']
    output.mkdir(parents=True,exist_ok=True);provenance=[]
    for case,original in zip(cases,originals):
        data=deepcopy(original);stages=[s for s in data['stages'] if (s.get('recognition') or {}).get('kind')=='fluid_material_transfer']
        if len(stages)!=1 or stages[0]['recognition']['required_count']!=1:raise ValueError('reviewed one-particle liquid prototype required')
        stage=stages[0];added,text=conditions(stage,factor);stage.setdefault('geometry',[]).extend(added)
        if case['prompt_mode']=='conditioned':data['geometric_instruction']=text
        path=output/'pairs'/case['checkpoint_id']/case['task']/(case['prompt_mode']+'.program.json')
        path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(data,indent=2)+'\n');AtomicProgram.load(path)
        copy=deepcopy(case);copy.update(program=str(path.resolve()),program_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            geometric_prompt_append=text if case['prompt_mode']=='conditioned' else None)
        manifest['cases'].append(copy)
        provenance.append({'source_suite':str(source.resolve()),'source_program_sha256':case['program_sha256'],
            'factor':factor,'event':added[0]['event'],'prompt_mode':case['prompt_mode'],
            'changes':'identical added source-exit spout scoring; isolated append replaces earlier geometric append',
            'recognition_changed':False,'scope':'prototype named calibrated mouth targets; no arbitrary IK reachability, statistical steering or whole-fluid quantity claim'})
    validate_suite(manifest);(output/'suite.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (output/'clone-provenance.json').write_text(json.dumps(provenance,indent=2)+'\n');return manifest


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source-suite',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--factor',choices=['point','pose','displacement','orientation','spatial_relation'],required=True)
    a=p.parse_args();generate(a.output_dir,a.source_suite,a.factor);print('Generated isolated spout',a.factor,'pair')
