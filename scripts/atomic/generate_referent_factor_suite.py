#!/usr/bin/env python3
"""Calibrated initial referent probes, each in a separate matched suite."""
import argparse
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import sys
import numpy as np

REPO=Path(__file__).resolve().parents[2];sys.path.insert(0,str(REPO))
from task.atomic.geometry import _rotation,evaluate_geometry
from task.atomic.landmarks import matrix_quaternion
from task.atomic.spec import AtomicProgram
from scripts.atomic.run_suite import validate_suite


def probes(scene):
    """Reviewed three-cube scene; independent landmark is the third block."""
    objects=scene['objects'];labels=['block_0','block_1','block_2'];poses={}
    if scene.get('coordinate_frame')!='environment_local_world' or scene.get('quaternion_order')!='wxyz':
        raise ValueError('calibration frame/quaternion order not comparable')
    for label in labels:
        row=objects[label];root=np.asarray(row['initial_root_pose'],dtype=float)
        bounds=np.asarray(row['local_mesh_bounds_m'],dtype=float)
        if row['category']!='rigid' or row.get('errors') or root.shape!=(7,) or bounds.shape!=(2,3):
            raise ValueError('need actual rigid block poses and mesh bounds without calibration errors')
        if row['metadata'].get('model_name')!='cube':raise ValueError('reviewed cube binding changed')
        if not np.isfinite(root).all() or not np.isfinite(bounds).all() or np.any(bounds[0]>=bounds[1]):raise ValueError('invalid calibration bounds/pose')
        poses[label]=np.r_[root[:3]+_rotation(root[3:])@bounds.mean(axis=0),root[3:]]
    reference={'kind':'object_center_pose','label':'block_2'};ref=poses['block_2']
    offset=(_rotation(ref[3:]).T@(poses['block_0'][:3]-ref[:3])).tolist()
    rotation=matrix_quaternion(_rotation(ref[3:]).T@_rotation(poses['block_0'][3:])).tolist()
    common={'id':'initial_referent','slot':'object','reference':reference}
    definitions={
        'pose':{**common,'kind':'pose','measurement':{'kind':'object_center_pose','label':'@candidate'},
            'expected':{'position':offset,'orientation':rotation},'tolerance':.02,'angle_tolerance_rad':math.pi/18},
        'relative_displacement':{**common,'kind':'relative_displacement','measurement':{'kind':'object_center_position','label':'@candidate'},
            'expected':offset,'tolerance':.02},
        'relative_orientation':{**common,'kind':'relative_orientation','measurement':{'kind':'object_center_pose','label':'@candidate'},
            'expected':rotation,'tolerance':math.pi/18},
        'spatial_relation':{**common,'kind':'spatial_relation','measurement':{'kind':'object_center_position','label':'@candidate'},
            'expected':'left_of','relation_scope':'points','margin':.3,'tolerance':.005}}
    rows={}
    for factor,c in definitions.items():
        results={label:evaluate_geometry(c,pose if c['measurement']['kind'].endswith('_pose') else pose[:3],ref).as_dict()
                 for label,pose in poses.items()}
        expected='block_1' if factor=='spatial_relation' else 'block_0'
        eligible=[label for label,result in results.items() if result['passed']]
        if eligible!=[expected]:raise ValueError(f'{factor} does not resolve a unique reviewed candidate: {eligible}')
        rows[factor]={'condition':c,'target':expected,'preflight':results}
    return rows,poses


def generate(output,source_suite,calibration_report):
    if output.exists() and any(output.iterdir()):raise ValueError('use a fresh empty output directory')
    source=json.loads(source_suite.read_text())
    cases=[c for c in source['cases'] if c['task']=='stack_blocks_by_language']
    if len(cases)!=2 or [c['prompt_mode'] for c in cases]!=['baseline','conditioned']:
        raise ValueError('reviewed matched block-language pair required')
    for case in cases:
        if hashlib.sha256(Path(case['program']).read_bytes()).hexdigest()!=case['program_sha256']:
            raise ValueError('source program differs from retained hash')
    originals=[json.loads(Path(c['program']).read_text()) for c in cases]
    originals[1].pop('geometric_instruction',None)
    if originals[0]!=originals[1]:raise ValueError('source pair differs beyond prompt')
    report=json.loads(calibration_report.read_text());details=report['native_results'][0]['details']
    if report.get('task')!='stack_blocks_by_language' or report.get('seed')!=0 or len(details)!=1:
        raise ValueError('one actual seed-0 block-language calibration episode required')
    if next(iter(details.values())).get('layout_id')!=0:raise ValueError('calibration must use layout zero')
    scene=next(iter(details.values()))['atomic_sequence']['scene_calibration']
    rows,poses=probes(scene);output.mkdir(parents=True,exist_ok=True)
    reference_description=('block_2, whose initial world center is '+
        json.dumps((poses['block_2'][:3]*1000).tolist())+' mm, using its initial local axes')
    for factor,row in rows.items():
        root=output/f'geometry-referent-{factor.replace("relative_", "")}-1006';root.mkdir()
        base=deepcopy(originals[0]);base.pop('geometric_instruction',None)
        # Isolate which conditioning was prompted. Existing action predicates stay intact.
        for stage in base['stages']:stage['geometry']=[];stage['trajectories']=[]
        target=row['target'];stage={'id':'initial_geometric_referent','family':'pick','required':False,
            'instruction':'Observe the first sustained two-finger candidate selection.',
            'recognition':{'kind':'finger_contact_motion','label':target,'arm':'any',
                'motion_threshold_m':.025,'min_contact_steps':2},
            'success_checks':[{'name':'is_lift','args':{'label':target,'z_threshold':.025}}],
            'geometry':[], 'selection':{'candidates':{'prefix':'block_','category':'rigid','min':3,'max':3},
                'arm':'any','min_finger_bodies':2,'min_contact_steps':2,'conditions':[row['condition']]}}
        base['stages'].append(stage);base['stage_dependencies']['initial_geometric_referent']=[]
        c=row['condition'];expected=c['expected'];text='Begin by selecting the block with the following initial geometry relative to '+reference_description+'. '
        if factor in ('pose','relative_displacement'):
            text+='Its mesh-bounds center must have offset '+json.dumps([x*1000 for x in (expected['position'] if factor=='pose' else expected)])+' mm in those reference axes, within 20 mm Euclidean error. '
        if factor in ('pose','relative_orientation'):
            q=expected['orientation'] if factor=='pose' else expected
            yaw=math.degrees(math.atan2(_rotation(q)[1,0],_rotation(q)[0,0]))
            text+=f'Its full root orientation must be {yaw:.6f} degrees about reference local z from aligned axes, within 10 degrees full orientation error. '
        if factor=='spatial_relation':
            text+='Its initial mesh-bounds center must be at least 300 mm toward negative local x (left), allowing at most 5 mm shortfall. This is a center relation.'
        manifest={'schema_version':3,'task':'robodojo_geometry_expansion','mode':'paired_native_and_geometrically_conditioned',
            'checkpoints':deepcopy(source['checkpoints']),'layout_id':0,'phase':'initial_referent_'+factor,'cases':[],
            'coverage':[{'task':'stack_blocks_by_language','included':True,'families':['pick','place'],'unbound_families':[],'blocker':None}],
            'scope':'initial selected-referent geometry; existing recognition retained, other geometric scores omitted',
            'source_programs':[{'path':case['program'],'sha256':case['program_sha256']} for case in cases],
            'calibration':{'report':str(calibration_report.resolve()),'sha256':hashlib.sha256(calibration_report.read_bytes()).hexdigest(),
                'factor':factor,**row,'scope':'actual pre-policy poses and mesh bounds; fresh runtime must resolve the same unique target'}}
        for old in cases:
            program=deepcopy(base)
            if old['prompt_mode']=='conditioned':program['geometric_instruction']=text
            path=root/'pairs'/old['checkpoint_id']/old['task']/(old['prompt_mode']+'.program.json');path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(json.dumps(program,indent=2)+'\n');AtomicProgram.load(path)
            case=deepcopy(old);case.update(program=str(path.resolve()),program_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                geometric_prompt_append=program.get('geometric_instruction'));manifest['cases'].append(case)
        validate_suite(manifest)
        (root/'suite.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return rows


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',required=True,type=Path)
    parser.add_argument('--source-suite',required=True,type=Path)
    parser.add_argument('--calibration-report',required=True,type=Path)
    args=parser.parse_args();generate(args.output_dir,args.source_suite,args.calibration_report)
    print('Generated four independently calibrated referent-factor pairs')
