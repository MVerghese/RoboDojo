#!/usr/bin/env python3
"""Initial source-vessel role probes calibrated before policy execution."""
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
from scripts.atomic.storage import atomic_write_json

TASKS={
    'pour_liquid_into_cup':('bottle','cup',{'wuliangye'},{'mug','goblet'}),
    'pour_balls_into_vase':('cup','vase',{'cup'},{'vase'}),
    'play_Xylophone':('mallet','xylophone',{'mallet'},{'xylophone'}),
}
ROLES={task:{'family':'pour','slot':'source'} for task in TASKS if task!='play_Xylophone'}
ROLES['play_Xylophone']={'family':'touch_with_tool','slot':'tool'}
FACTORS=('point','pose','displacement','orientation','relation')


def probes(scene,task):
    source,target,source_models,target_models=TASKS[task];poses={}
    if scene.get('coordinate_frame')!='environment_local_world' or scene.get('quaternion_order')!='wxyz':
        raise ValueError('actual environment-local initial scene and wxyz required')
    for label,models in ((source,source_models),(target,target_models)):
        row=scene['objects'][label];root=np.asarray(row['initial_root_pose'],float)
        bounds=np.asarray(row['local_mesh_bounds_m'],float)
        if (row.get('errors') or row['category'] not in ('rigid','geometry')
                or row['metadata']['model_name'] not in models
                or root.shape!=(7,) or bounds.shape!=(2,3) or not np.isfinite(root).all()
                or not np.isfinite(bounds).all() or np.any(bounds[0]>=bounds[1])):
            raise ValueError('reviewed vessel model, actual initial pose and scaled mesh bounds required')
        poses[label]=np.r_[root[:3]+_rotation(root[3:])@bounds.mean(0),root[3:]]
    ref=poses[target];offset=_rotation(ref[3:]).T@(poses[source][:3]-ref[:3])
    q=matrix_quaternion(_rotation(ref[3:]).T@_rotation(poses[source][3:])).tolist()
    reference={'kind':'object_center_pose','label':target}
    role=ROLES[task]
    common={'id':'initial_'+role['slot'],'slot':role['slot'],'measurement':{'kind':'object_center_position','label':'@candidate'}}
    axis=int(np.argmax(np.abs(offset[:2])));sign=1 if offset[axis]>0 else -1
    relation={(0,1):'right_of',(0,-1):'left_of',(1,1):'in_front_of',(1,-1):'behind'}[axis,sign]
    # Half the measured separation gives a discriminating initial center relation.
    margin=float(abs(offset[axis])/2)
    definitions={
        'point':{**common,'kind':'point','expected':poses[source][:3].tolist(),'tolerance':.02},
        'pose':{**common,'kind':'pose','measurement':{'kind':'object_center_pose','label':'@candidate'},
            'reference':reference,'expected':{'position':offset.tolist(),'orientation':q},'tolerance':.02,'angle_tolerance_rad':math.pi/18},
        'displacement':{**common,'kind':'relative_displacement','reference':reference,'expected':offset.tolist(),'tolerance':.02},
        'orientation':{**common,'kind':'relative_orientation','measurement':{'kind':'object_center_pose','label':'@candidate'},
            'reference':reference,'expected':q,'tolerance':math.pi/18},
        'relation':{**common,'kind':'spatial_relation','reference':reference,'expected':relation,
            'relation_scope':'points','margin':margin,'tolerance':.005},
    }
    rows={};blocked={}
    for factor,c in definitions.items():
        results={label:evaluate_geometry(c,pose if c['measurement']['kind'].endswith('_pose') else pose[:3],
            ref if 'reference' in c else None).as_dict() for label,pose in poses.items()}
        eligible=[label for label,r in results.items() if r['passed']]
        if eligible!=[source]:
            blocked[factor]={'reason':'initial geometric factor does not uniquely select source','eligible':eligible,'preflight':results}
            continue
        description='pour source vessel' if role['family']=='pour' else 'tool for touching the xylophone'
        text='Begin by choosing the '+description+' using its initial scaled mesh-bounds center and root axes. '
        if factor=='point':text+='Its initial center must be at '+json.dumps([v*1000 for v in c['expected']])+' mm in environment-local world XYZ, within 20 mm Euclidean distance. '
        else:
            text+='Use the initial '+target+' mesh-bounds-center frame, whose initial world XYZ is '+json.dumps((ref[:3]*1000).tolist())+' mm and wxyz orientation is '+json.dumps(ref[3:].tolist())+'. '
            if factor in ('pose','displacement'):text+='The initial source center offset must be '+json.dumps((offset*1000).tolist())+' mm in those initial reference axes, within 20 mm Euclidean error. '
            if factor in ('pose','orientation'):text+='Its initial root orientation relative to those axes must match wxyz '+json.dumps(q)+', within 10 degrees full orientation error. '
            if factor=='relation':text+=f'Its initial center must be {relation} the reference center, at least {margin*1000:.9f} mm along the named reference axis, allowing 5 mm shortfall. This is a center-point relation. '
        text+='These candidate positions and orientations refer to the beginning of the episode and stay fixed when objects move. Selection is measured at the first sustained two-finger contact with either candidate; this does not certify a completed action.'
        rows[factor]={'condition':c,'target':source,'preflight':results,'prompt':text}
    return rows,blocked


def generate(output,source_suite,calibration_reports,suite_prefix='geometry-source-selection'):
    if output.exists() and any(output.iterdir()):raise ValueError('use a fresh empty output directory')
    if suite_prefix not in ('geometry-source-selection','geometry-tool-selection'):raise ValueError('reviewed suite prefix required')
    source_manifest=json.loads(source_suite.read_text());pairs={};calibrations={};blocked={}
    for task,path in calibration_reports.items():
        cases=[c for c in source_manifest['cases'] if c['task']==task]
        if len(cases)!=2 or [c['prompt_mode'] for c in cases]!=['baseline','conditioned']:raise ValueError('reviewed source pair required')
        originals=[]
        for c in cases:
            raw=Path(c['program']).read_bytes()
            if hashlib.sha256(raw).hexdigest()!=c['program_sha256']:raise ValueError('source program hash changed')
            d=json.loads(raw);d.pop('geometric_instruction',None);originals.append(d)
        if originals[0]!=originals[1]:raise ValueError('source pair differs beyond prompt')
        report=json.loads(path.read_text());details=report['native_results'][0]['details']
        if report.get('task')!=task or report.get('seed')!=0 or len(details)!=1:raise ValueError('one seed-0 calibration episode required')
        detail=next(iter(details.values()))
        if detail['layout_id']!=0:raise ValueError('layout zero required')
        rows,blocked[task]=probes(detail['atomic_sequence']['scene_calibration'],task)
        pairs[task]=(cases,originals[0],rows)
        calibrations[task]={'report':str(path.resolve()),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'scope':'initial pre-policy scene; targets do not use completed policy outcomes'}
    output.mkdir(parents=True,exist_ok=True);atomic_write_json(output/'blocked-factors.json',blocked)
    suites=[]
    for factor in FACTORS:
        eligible=[task for task,pair in pairs.items() if factor in pair[2]]
        if not eligible:continue
        root=output/f'{suite_prefix}-{factor}-1006';root.mkdir()
        manifest={**deepcopy(source_manifest),'cases':[],'phase':'initial_source_'+factor,
            'calibration':deepcopy(calibrations),'scope':'first selected object-role initial geometry; no completed-action or language-role inference'}
        if 'coverage' in manifest:manifest['coverage']=[r for r in manifest['coverage'] if r['task'] in eligible]
        for task in eligible:
            cases,original,rows=pairs[task];row=rows[factor];base=deepcopy(original)
            pickups=[s for s in base['stages'] if s['family']=='pick' and s['recognition']['label']==row['target']]
            if len(pickups)!=1 or base['stage_dependencies'].get(pickups[0]['id'])!=[]:raise ValueError('initial source pickup stage required')
            stage=pickups[0]
            if stage.get('selection'):raise ValueError('existing selector must be preserved rather than replaced')
            stage['selection']={'role':deepcopy(ROLES[task]),'candidates':list(TASKS[task][:2]),
                'arm':'any','min_finger_bodies':2,'min_contact_steps':2,'conditions':[row['condition']]}
            for old in cases:
                program=deepcopy(base)
                if old['prompt_mode']=='conditioned':program['geometric_instruction']=row['prompt']
                path=root/'pairs'/old['checkpoint_id']/task/(old['prompt_mode']+'.program.json');path.parent.mkdir(parents=True,exist_ok=True)
                atomic_write_json(path,program);AtomicProgram.load(path)
                case=deepcopy(old);case.update(program=str(path.resolve()),program_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                    geometric_prompt_append=program.get('geometric_instruction'));manifest['cases'].append(case)
        validate_suite(manifest);atomic_write_json(root/'suite.json',manifest)
        atomic_write_json(root/'clone-provenance.json',{'source_suite':str(source_suite.resolve()),'calibration':calibrations,
            'factor':factor,'preflight':{t:pairs[t][2][factor] for t in eligible},
            'changes':'identical initial object-role selection observer in both arms; append isolates selection factor; existing recognition and scored action targets retained'})
        suites.append(root)
    return suites


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--source-suite',type=Path,required=True);p.add_argument('--liquid-calibration',type=Path)
    p.add_argument('--balls-calibration',type=Path);p.add_argument('--xylophone-calibration',type=Path)
    p.add_argument('--suite-prefix',choices=['geometry-source-selection','geometry-tool-selection'],default='geometry-source-selection');a=p.parse_args()
    reports={task:path for task,path in [('pour_liquid_into_cup',a.liquid_calibration),('pour_balls_into_vase',a.balls_calibration),('play_Xylophone',a.xylophone_calibration)] if path is not None}
    if not reports:p.error('at least one reviewed task calibration report is required')
    print('\n'.join(map(str,generate(a.output_dir,a.source_suite,reports,a.suite_prefix))))
