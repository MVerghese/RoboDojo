#!/usr/bin/env python3
"""Compare archived strike contacts to calibrated authored key surfaces.

The root is reconstructed from retained functional poses, not read from the
simulator. Missing live mesh/scale capture deliberately remains partial evidence.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import numpy as np

REPO=Path(__file__).resolve().parents[2];sys.path.insert(0,str(REPO))
from task.atomic.geometry import _rotation
from task.atomic.surface_distance import point_surface_distances
from scripts.atomic.storage import atomic_write_json


def audit_stage(stage,profile):
    event=stage.get('physical_events',{}).get('impact')
    if event is None:return {'stage_id':stage['stage_id'],'status':'unobserved'}
    checks={};metrics={}
    try:
        identity=event['target_identity'];selectors=identity['candidate_selectors'];poses=np.asarray(identity['candidate_poses'])
        tags=[selector['tag'] for selector in selectors]
        checks['all_calibrated_landmarks_retained']=(len(tags)==len(set(tags)) and set(tags)==set(profile['bindings'])
            and all(selector['kind']=='functional_point' and selector.get('type')=='passive'
                and selector.get('index',0)==0 for selector in selectors))
        index=identity['target_index'];selected=profile['bindings'][tags[index]]
        local=np.asarray(selected['landmark_root_pose']);root_rotation=_rotation(poses[index,3:])@_rotation(local[3:]).T
        root_origin=poses[index,:3]-root_rotation@local[:3]
        errors=[];rotation_errors=[]
        for tag,pose in zip(tags,poses):
            landmark=np.asarray(profile['bindings'][tag]['landmark_root_pose'])
            errors.append(float(np.linalg.norm(root_origin+root_rotation@landmark[:3]-pose[:3])))
            rotation_errors.append(float(np.linalg.norm(root_rotation@_rotation(landmark[3:])-_rotation(pose[3:]))))
        checks['all_landmark_positions_reconstruct']=max(errors)<=1e-7
        checks['all_landmark_orientations_reconstruct']=max(rotation_errors)<=1e-7
        checks['target_selector_binding']=selectors[index]==stage['recognition']['target_point']
        hold=event['held_contact'];origin=np.asarray(hold['environment_origin_world_m'])
        points=np.asarray(event['contact_points']);rows=event['tool_target_contacts'];step=event['physics_step']
        checks['synchronized_force_points']=(points.shape==(len(rows),3) and len(rows)>0
            and np.allclose(np.asarray([r['position_world'] for r in rows])-origin,points,rtol=0,atol=1e-7)
            and all(r['force_report_physics_step']==step and np.isfinite(r['impulse']).all()
                and np.linalg.norm(r['impulse'])>1e-9 for r in rows))
        model=profile['asset_key'].split('/')[-2];model_id=int(profile['asset_key'].split('/')[-1])
        pattern=r'/'+re.escape(model)+r'/'+re.escape(model)+'_'+str(model_id)+r'_[0-9]+(?:/|$)'
        checks['named_target_model_actor']=all(any(re.search(pattern,r['actor'+str(i)]) for i in (0,1)) for r in rows)
        root_points=(points-root_origin)@root_rotation;distances={}
        for tag,binding in profile['bindings'].items():
            triangles=np.asarray(binding['expected_triangles_m']);faces=np.arange(len(triangles)*3).reshape(-1,3)
            distances[tag]=point_surface_distances(root_points,triangles.reshape(-1,3),faces)
        own=distances[tags[index]];others=np.min([d for tag,d in distances.items() if tag!=tags[index]],axis=0)
        metrics={'selected_surface_distance_m':own.tolist(),'nearest_other_key_distance_m':others.tolist(),
            'surface_identity_gap_m':(others-own).tolist(),'max_landmark_reconstruction_error_m':max(errors)}
    except (KeyError,TypeError,ValueError,IndexError,AttributeError):checks['archive_fields']=False
    failed=[k for k,v in checks.items() if not v]
    return {'stage_id':stage['stage_id'],'action_success':stage['action_success'],
        'status':'inconsistent_evidence' if failed else 'partial_evidence','checks':checks,'failed_checks':failed,
        'unavailable':['live_selected_mesh_and_scale_capture_absent'],'metrics':metrics if not failed else {},
        'scope':'archived force contacts and all-landmark root reconstruction against authored mesh components; not live mesh readback, cooked-collider part identity, exclusive impact, acoustics or native success'}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--profile',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    profile=json.loads(a.profile.read_text());raw=a.report.read_bytes();report=json.loads(raw);rows=[]
    for native in report.get('native_results',[]):
        details=native.get('details',{})
        for episode,detail in (details.items() if isinstance(details,dict) else enumerate(details)):
            for stage in detail.get('atomic_sequence',{}).get('stages',[]):
                if (stage.get('recognition') or {}).get('kind')=='held_tool_strike':
                    rows.append({'episode':str(episode),'layout_id':detail['layout_id'],**audit_stage(stage,profile)})
    result={'report_sha256':hashlib.sha256(raw).hexdigest(),
        'profile_sha256':hashlib.sha256(a.profile.read_bytes()).hexdigest(),'stages':rows}
    atomic_write_json(a.output,result)
    print(json.dumps({'output':str(a.output),'statuses':{status:sum(r['status']==status for r in rows)
        for status in sorted({r['status'] for r in rows})}}))
