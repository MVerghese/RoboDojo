"""Sample a declared path every physics step, retaining reproducible evidence."""
from copy import deepcopy
import math

import numpy as np

from task.atomic.geometry import _observed_pose, _pose, _rotation
from task.atomic.contacts import ContactUnavailable


def validate_trajectory(c, validate_selector, validate_event):
    from task.atomic.spec import FRAME_KINDS
    required = {'id','slot','measurement','expected','tolerance','axes','min_samples','start_event','end_event'}
    if not isinstance(c, dict) or not required <= set(c) or set(c) - required - {'reference','backtrack_tolerance_m'}:
        raise ValueError('trajectory requires explicit path, axes, tolerance and sampling window')
    if any(not isinstance(c[k], str) or not c[k] for k in ('id','slot')):
        raise ValueError('trajectory requires nonempty id and slot')
    validate_selector(c['measurement'], 'trajectory.measurement')
    if c['measurement']['kind'] not in FRAME_KINDS | {'object_position','object_center_position'} or c['measurement'].get('time','live') != 'live':
        raise ValueError('path measurement requires a live physical landmark, not a contact centroid')
    if 'reference' in c:
        validate_selector(c['reference'], 'trajectory.reference')
        if c['reference']['kind'] not in FRAME_KINDS:
            raise ValueError('path reference requires an oriented frame')
    axes = c['axes']
    if not isinstance(axes,list) or not axes or any(type(a) is not int or a not in (0,1,2) for a in axes) or len(set(axes)) != len(axes):
        raise ValueError('path axes must be a unique nonempty subset of [0,1,2]')
    path = c['expected']
    if (not isinstance(path,list) or len(path)<2 or any(not isinstance(p,list) or len(p)!=3 or
        any(type(x) not in (int,float) or not math.isfinite(x) for x in p) for p in path)):
        raise ValueError('path requires at least two finite 3D waypoints')
    if np.any(np.linalg.norm(np.diff(np.asarray(path)[:,axes],axis=0),axis=1) <= 0):
        raise ValueError('path segments must have positive length in scored axes')
    for field in ('tolerance','backtrack_tolerance_m'):
        if field in c and (type(c[field]) not in (int,float) or not math.isfinite(c[field]) or c[field]<0):
            raise ValueError('path tolerances must be finite and nonnegative')
    if type(c['min_samples']) is not int or c['min_samples']<2:
        raise ValueError('path requires at least two distinct physics samples')
    for field in ('start_event','end_event'):
        event=c[field]
        if field=='start_event' and event == {'kind':'stage_start'}:
            continue
        validate_event(event)
        if event['kind']=='before_contact':
            raise ValueError('path window events must occur in the current physical sample')
        if field == 'start_event' and event['kind'] == 'attempt_end':
            raise ValueError('attempt_end can close a path, not start one')


def path_sample(c, measured, reference=None):
    point, _ = _observed_pose(measured)
    origin, rotation = _pose(reference,'reference')
    local = _rotation(rotation).T @ (point-origin)
    axes=c['axes']; path=np.asarray(c['expected'],dtype=float)[:,axes]
    starts, vectors = path[:-1], np.diff(path,axis=0)
    lengths=np.linalg.norm(vectors,axis=1)
    t=np.clip(np.sum((local[axes]-starts)*vectors,axis=1)/lengths**2,0,1)
    errors=np.linalg.norm(local[axes]-(starts+t[:,None]*vectors),axis=1)
    index=int(np.argmin(errors))
    progress=float(np.sum(lengths[:index])+t[index]*lengths[index])
    return {'point_in_reference':local.tolist(),'deviation_m':float(errors[index]),
            'progress_m':progress,'path_length_m':float(np.sum(lengths)),
            'start_error_m':float(np.linalg.norm(local[axes]-path[0])),
            'end_error_m':float(np.linalg.norm(local[axes]-path[-1]))}


def aggregate_path(c, samples, failures, complete):
    """Unknown coverage has no pass/error score; observed deviations still persist."""
    if not complete:
        return {'status':'window_incomplete','passed':None,'sample_count':len(samples)}
    steps=[s['physics_step'] for s in samples]
    times=[s['dt_s'] for s in samples]
    continuous=all(b==a+1 for a,b in zip(steps,steps[1:]))
    timing=all(math.isfinite(t) and t>0 and t==times[0] for t in times)
    if failures or len(samples)<c['min_samples'] or not continuous or not timing:
        return {'status':'coverage_failed','passed':None,'sample_count':len(samples)}
    values=[path_sample(c,s['measured_state'],s.get('reference_state')) for s in samples]
    errors=np.array([v['deviation_m'] for v in values])
    # A nearest-segment projection alone can skip a corner or declare a
    # stationary point successful on a closed path. Require ordered waypoint
    # witnesses, then project onto the currently enabled segment.
    path=np.asarray(c['expected'],dtype=float)[:,c['axes']]
    vectors=np.diff(path,axis=0); lengths=np.linalg.norm(vectors,axis=1)
    cursor=1; visited=1 if values[0]['start_error_m']<=c['tolerance'] else 0
    progress=[]; nearest_progress=[]; out_of_order=0
    for value in values:
        point=np.asarray(value['point_in_reference'])[c['axes']]
        while visited and cursor<len(path) and np.linalg.norm(point-path[cursor])<=c['tolerance']:
            visited+=1;cursor+=1
        segment=min(cursor-1,len(vectors)-1)
        t=float(np.clip((point-path[segment])@vectors[segment]/lengths[segment]**2,0,1))
        progress.append(float(lengths[:segment].sum()+t*lengths[segment]))
        enabled_distance=float(np.linalg.norm(point-(path[segment]+t*vectors[segment])))
        if enabled_distance>c['tolerance'] and value['deviation_m']<=c['tolerance']:
            out_of_order+=1
        nearest_progress.append(float(lengths.sum()) if visited==len(path) and value['end_error_m']<=c['tolerance'] else value['progress_m'])
    progress=np.asarray(progress)
    # Count every backward move, rather than letting a forward recovery hide it.
    backtracking=float(max(np.maximum(0,-np.diff(progress)).sum(),np.maximum(0,-np.diff(nearest_progress)).sum()))
    backtrack_tolerance=c.get('backtrack_tolerance_m',c['tolerance'])
    endpoint=max(values[0]['start_error_m'],values[-1]['end_error_m'])
    return {'status':'scored','passed':bool(errors.max()<=c['tolerance'] and endpoint<=c['tolerance'] and backtracking<=backtrack_tolerance and visited==len(path) and not out_of_order),
            'sample_count':len(samples),'max_deviation_m':float(errors.max()),
            'visited_waypoints':visited,'waypoint_count':len(path),'out_of_order_samples':out_of_order,
            'rms_deviation_m':float(np.sqrt(np.mean(errors**2))),
            'start_error_m':values[0]['start_error_m'],'end_error_m':values[-1]['end_error_m'],
            'backtracking_m':backtracking,'duration_s':float((samples[-1]['physics_step']-samples[0]['physics_step'])*samples[0]['dt_s'])}


class TrajectoryObserver:
    def __init__(self,session):
        self.session=session
        self.rows={c['id']:{'condition':deepcopy(c),'started':False,'complete':False,'samples':[],'failures':[]} for c in session.stage.trajectories}
        self.last_step=None

    def observe(self,success_now):
        contacts=getattr(self.session.env,'_atomic_contacts',None)
        if contacts is None:
            raise RuntimeError('path scoring requires a synchronized physics clock')
        if contacts.errors:
            raise RuntimeError('path scoring cannot use a broken contact/physics callback')
        step=contacts.steps
        if step == self.last_step:
            return
        dt=float(getattr(self.session.env,'dt',float('nan')))
        if not math.isfinite(dt) or dt<=0:
            raise RuntimeError('path scoring requires finite positive simulation dt')
        previous=self.last_step; self.last_step=step
        for row in self.rows.values():
            if row['complete']:continue
            c=row['condition']
            if not row['started']:
                if c['start_event'] != {'kind':'stage_start'} and not self.session._event_fired(c['start_event'],success_now):continue
                row.update(started=True,start_physics_step=step)
            elif previous is not None and step != previous+1:
                row['failures'].append({'physics_step':step,'reason':'sampling_gap','previous_step':previous})
            if row['samples'] and dt != row['samples'][0]['dt_s']:
                row['failures'].append({'physics_step':step,'reason':'simulation_dt_changed'})
            try:
                measured,source=self.session._resolve_with_source(c['measurement'])
                reference,ref_source=self.session._resolve_with_source(c['reference']) if c.get('reference') else (None,None)
                sample={'physics_step':step,'policy_action_index':self.session._action_index(),'dt_s':dt,
                        'measured_state':measured.tolist(),'reference_state':reference.tolist() if reference is not None else None,
                        'measurement_source':deepcopy(source),'reference_source':deepcopy(ref_source)}
                path_sample(c,sample['measured_state'],sample['reference_state'])
                row['samples'].append(sample)
            except ContactUnavailable as error:
                row['failures'].append({'physics_step':step,'reason':str(error)})
            if self.session._event_fired(c['end_event'],success_now):
                row.update(complete=True,end_physics_step=step)

    def summary(self):
        return {ident:{**deepcopy(row),'result':aggregate_path(row['condition'],row['samples'],row['failures'],row['complete'])}
                for ident,row in self.rows.items()}

    def abort_events(self, names):
        """Archive and reset paths that belong to the interrupted interaction."""
        archived = {}
        for ident, row in self.rows.items():
            c = row['condition']
            if not row['started'] or not any(c[key].get('kind') == 'recognition_event'
                    and c[key]['name'] in names for key in ('start_event', 'end_event')):
                continue
            archived[ident] = {**deepcopy(row),
                'result': aggregate_path(c, row['samples'], row['failures'], row['complete'])}
            self.rows[ident] = {'condition': deepcopy(c), 'started': False, 'complete': False,
                               'samples': [], 'failures': []}
        return archived

    def finalize(self):
        """Close an attempt-end window without duplicating a physics sample."""
        contacts = self.session.env._atomic_contacts
        if contacts.steps != self.last_step:
            self.observe(False)
        for row in self.rows.values():
            if (row['started'] and not row['complete'] and
                    row['condition']['end_event']['kind'] == 'attempt_end'):
                row.update(complete=True, end_physics_step=contacts.steps)
