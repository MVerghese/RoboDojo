#!/usr/bin/env python3
"""Set attainable nominal contact axes from independently verified live grasps."""
import argparse
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import sys

REPO=Path(__file__).resolve().parents[2];sys.path.insert(0,str(REPO))
from task.atomic.contact_validation import validate_contact_witness
from task.atomic.geometry import _rotation,evaluate_geometry
from task.atomic.landmarks import matrix_quaternion
from task.atomic.spec import AtomicProgram
from scripts.atomic.run_suite import validate_suite


def calibrate(program,detail):
    if detail.get('layout_id')!=0:raise ValueError('calibration layout must be zero')
    retained={s['stage_id']:s for s in detail['atomic_sequence']['stages']};result=deepcopy(program);rows=[]
    for stage in result['stages']:
        if stage['family']!='pick':continue
        geometry={c['id']:c for c in stage['geometry']}
        if not {'contact_frame_pose','contact_frame_z'}<=set(geometry):continue
        actual=retained[stage['id']]
        if actual.get('action_success') is not True:raise ValueError('nominal target requires a successful physical pickup')
        raw=actual['geometry']['contact_frame_pose'];measurement=raw['condition']['measurement']
        witness=validate_contact_witness(raw['measurement_source'],measurement,raw['measured_state'])
        if witness['status']!='consistent_contact_evidence':raise ValueError('nominal contact frame has no consistent raw witness')
        if (measurement!=geometry['contact_frame_pose']['measurement'] or
                raw['condition']['reference']!=geometry['contact_frame_pose']['reference'] or
                raw['condition']['event']!=geometry['contact_frame_pose']['event']):
            raise ValueError('live source frame/reference/event differs from requested binding')
        rotation=matrix_quaternion(_rotation(raw['reference_state'][3:]).T@
                                   _rotation(raw['measured_state']['orientation'])).tolist()
        geometry['contact_frame_pose']['expected']['orientation']=rotation
        geometry['contact_frame_pose']['angle_tolerance_rad']=math.pi/12
        geometry['contact_frame_z']['expected']=rotation
        geometry['contact_frame_z']['tolerance']=math.pi/12
        nominal={c['id']:evaluate_geometry(c,raw['measured_state'],raw['reference_state']).as_dict()
                 for c in (geometry['contact_frame_pose'],geometry['contact_frame_z'])}
        if not all(v['passed'] for v in nominal.values()):raise ValueError('live grasp cannot satisfy the nominal target')
        if geometry['contact_frame_pose']['expected']['position']!=[0,0,0] or geometry['contact_frame_pose']['tolerance']!=.03:
            raise ValueError('reviewed nominal probe needs a 30 mm contact-center target')
        axes=_rotation(rotation)
        rows.append({'stage':stage['id'],'reference':geometry['contact_frame_pose']['reference'],
            'event':geometry['contact_frame_pose']['event'],'orientation_frame':measurement['orientation_frame'],
            'resolved_link':raw['measurement_source']['orientation_frame_source']['ee_link_name'],
            'relative_orientation_wxyz':rotation,'axes_in_reference':[axes[:,i].tolist() for i in range(3)],
            'nominal':nominal,'scope':'witnessed same-step grasp axes; no certificate for an arbitrary altered orientation'})
    if not rows:raise ValueError('no verified grasp contact frames to calibrate')
    text=[]
    for row in rows:
        axes=[[round(v,6) for v in direction] for direction in row['axes_in_reference']]
        text.append(f"At the first 25 mm lift of {row['reference']['label']}, orient the physically contacting arm's "
            f"named end-effector link ({row['resolved_link']}) so its local x, y and z directions are respectively "
            f"{axes} in the object's mesh-center frame axes, within 15 degrees full rotation error; "
            'also keep its local z direction within 15 degrees of the specified z direction. '
            'Keep every actual finger contact within 30 mm of that object center and inside its '
            'reference-origin box with 30 mm half extents on each axis.')
    return result,' '.join(text),rows


def generate(output,source_suite,report_path,prior_suite):
    if output.exists() and any(output.iterdir()):raise ValueError('use a fresh empty directory')
    source=json.loads(source_suite.read_text());prior=json.loads(prior_suite.read_text());task='stack_blocks_by_language'
    cases=[c for c in source['cases'] if c['task']==task]
    if len(cases)!=2 or [c['prompt_mode'] for c in cases]!=['baseline','conditioned']:raise ValueError('matched block-language pair required')
    programs=[]
    for c in cases:
        data=Path(c['program']).read_bytes()
        if hashlib.sha256(data).hexdigest()!=c['program_sha256']:raise ValueError('source program hash changed')
        b=json.loads(data);b.pop('geometric_instruction',None);programs.append(b)
    if programs[0]!=programs[1]:raise ValueError('source differs beyond the prompt')
    report=json.loads(report_path.read_text())
    if report.get('task')!=task or report.get('seed')!=0:raise ValueError('actual seed-0 block-language report required')
    details=report['native_results'][0]['details']
    if len(details)!=1:raise ValueError('one actual source episode required')
    base,text,rows=calibrate(programs[0],next(iter(details.values())))
    previous=[c for c in prior['cases'] if c['task']==task and c['prompt_mode']=='conditioned']
    if len(previous)!=1:raise ValueError('one prior conditioning definition required')
    prior_path=Path(previous[0]['program']);raw=prior_path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=previous[0]['program_sha256']:raise ValueError('prior prompt source changed')
    append=json.loads(raw)['geometric_instruction']+' '+text
    manifest=deepcopy(source);manifest['cases']=[];manifest['phase']='calibrated_grasp_contact_frames'
    manifest['coverage']=[r for r in source['coverage'] if r['task']==task]
    manifest['contact_frame_bindings']=rows
    manifest['calibration']={'report':str(report_path.resolve()),'sha256':hashlib.sha256(report_path.read_bytes()).hexdigest(),
        'targets':rows,'scope':'observed feasible nominal grasp frames; descriptive fresh A/B evaluation, not a causal estimate'}
    output.mkdir(parents=True,exist_ok=True)
    for c in cases:
        program=deepcopy(base)
        if c['prompt_mode']=='conditioned':program['geometric_instruction']=append
        path=output/'pairs'/c['checkpoint_id']/task/(c['prompt_mode']+'.program.json');path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(program,indent=2)+'\n');AtomicProgram.load(path)
        case=deepcopy(c);case.update(program=str(path.resolve()),program_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            geometric_prompt_append=program.get('geometric_instruction'));manifest['cases'].append(case)
    validate_suite(manifest);(output/'suite.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('output-dir','source-suite','report','prior-suite'):parser.add_argument('--'+name,type=Path,required=True)
    a=parser.parse_args();generate(a.output_dir,a.source_suite,a.report,a.prior_suite)
    print('Generated one nominal contact-frame A/B pair from verified live grasps')
