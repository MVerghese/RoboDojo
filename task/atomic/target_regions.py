"""Distinct contact target regions defined by live physical landmarks."""
import json
import math
import numpy as np


def validate_target_regions(config,validate_selector):
    candidates=config['target_candidates'];margin=config['target_identity_margin_m']
    if (not isinstance(candidates,list) or not 2<=len(candidates)<=64
            or isinstance(margin,bool) or not isinstance(margin,(int,float)) or not math.isfinite(margin) or margin<=0):
        raise ValueError('target regions require 2..64 physical landmarks and a positive identity margin in metres')
    for candidate in candidates:
        validate_selector(candidate,'recognition.target_candidates')
        if (candidate['kind'] not in ('object_pose','object_center_pose','functional_point','calibrated_frame',
                'model_calibrated_frame','articulated_link_pose','joint_link_pose')
                or candidate.get('label')!=config['target_label'] or candidate.get('time','live')!='live'):
            raise ValueError('target region landmarks must be live frames on the named target')
    if (len({json.dumps(c,sort_keys=True) for c in candidates})!=len(candidates)
            or sum(c==config['target_point'] for c in candidates)!=1):
        raise ValueError('target region landmarks must be distinct and include the requested target exactly once')


def region_membership(points,poses,target_index,margin_m):
    points=np.asarray(points,dtype=float);poses=np.asarray(poses,dtype=float)
    if (points.ndim!=2 or points.shape[1]!=3 or poses.ndim!=2 or poses.shape[1]!=7 or len(poses)<2
            or type(target_index) is not int or not 0<=target_index<len(poses)
            or not np.isfinite(points).all() or not np.isfinite(poses).all()
            or isinstance(margin_m,bool) or not math.isfinite(margin_m) or margin_m<=0):
        raise ValueError('target regions require finite synchronized contact points and physical landmark poses')
    from task.atomic.geometry import _quaternion
    for pose in poses:_quaternion(pose[3:])
    distances=np.linalg.norm(points[:,None,:]-poses[None,:,:3],axis=2)
    selected=distances[:,target_index];others=np.delete(distances,target_index,axis=1).min(axis=1)
    return {'eligible':(selected+margin_m<=others).tolist(),
            'selected_distance_m':selected.tolist(),'nearest_competing_distance_m':others.tolist(),
            'identity_gap_m':(others-selected).tolist()}


def validate_target_region_witness(config,event):
    """Reproduce retained region assignment; no visual key/part inference."""
    checks={}
    try:
        raw=event['target_identity'];selectors=config['target_candidates'];index=selectors.index(config['target_point'])
        checks['target_region_binding']=(raw['kind']=='nearest_landmark_region'
            and raw['candidate_selectors']==selectors and raw['target_index']==index
            and type(raw['target_index']) is int and len(raw['candidate_poses'])==len(selectors)
            and raw['margin_m']==config['target_identity_margin_m']
            and raw['physics_step']==event['physics_step'] and raw['frame']=='environment_local_world')
        poses=raw['candidate_poses'];sources=raw['candidate_sources']
        checks['target_region_sources']=(len(sources)==len(selectors) and all(
            source.get('label')==selector['label'] and (source.get('kind')==selector['kind'] or
                selector['kind']=='model_calibrated_frame' and source.get('kind')=='calibrated_frame' and source.get('model_frame_proof'))
            and source.get('frame')=='environment_local_world' and source.get('physics_step')==event['physics_step']
            and (selector.get('tag') is None or source.get('tag')==selector['tag'])
            for source,selector in zip(sources,selectors)))
        recomputed=region_membership(event['contact_points'],poses,index,config['target_identity_margin_m'])
        checks['target_region_points']=all(recomputed['eligible']) and bool(recomputed['eligible'])
        checks['target_region_distances']=all(np.allclose(raw[k],recomputed[k],rtol=1e-7,atol=1e-9)
            for k in ('selected_distance_m','nearest_competing_distance_m','identity_gap_m'))
        checks['target_region_position']=bool(np.allclose(poses[index][:3],event['target_landmark_position'],rtol=0,atol=1e-9))
    except (KeyError,ValueError,TypeError,IndexError,AttributeError):checks['target_region_fields']=False
    return checks
