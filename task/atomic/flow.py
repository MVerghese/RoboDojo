"""Persistent-material crossings of a calibrated receptacle opening."""
from copy import deepcopy
from collections import Counter
import math
import numpy as np

from task.atomic.geometry import _rotation, _angular_error
from task.atomic.fit import aperture_polygon


def validate_flow(config, validate_selector):
    fields = {'opening', 'aperture_profile', 'target_xy_m', 'position_tolerance_m', 'angle_tolerance_rad'}
    if not isinstance(config, dict) or not fields.issubset(config) or set(config)-fields-{'expected_velocity_direction'}:
        raise ValueError('flow needs opening, aperture, XY target and independent position/angular tolerances')
    validate_selector(config['opening'], 'flow.opening')
    if config['opening']['kind'] not in ('functional_point', 'support_point', 'object_pose','calibrated_frame','model_calibrated_frame') or config['opening'].get('time','live') != 'live':
        raise ValueError('flow opening needs a live calibrated frame')
    aperture_polygon(config['aperture_profile'])
    target = np.asarray(config['target_xy_m'], dtype=float)
    if target.shape != (2,) or not np.isfinite(target).all(): raise ValueError('flow target must be finite XY metres')
    direction=np.asarray(config.get('expected_velocity_direction',[0,0,-1]),dtype=float)
    if direction.shape!=(3,) or not np.isfinite(direction).all() or np.linalg.norm(direction)<=1e-12:
        raise ValueError('flow velocity direction needs a finite nonzero vector in the opening frame')
    for key in ('position_tolerance_m', 'angle_tolerance_rad'):
        value=config[key]
        if type(value) not in (int,float) or not math.isfinite(value) or value < 0: raise ValueError('flow tolerances must be finite and nonnegative')


def score_crossing(config, before, after):
    """Linear substep crossing; retain its interpolation and measured velocity.

    This certifies the sampled crossing model, not an unobserved curved path.
    Large opening rotation is explicitly unscored. Velocity subtracts opening
    translation; target angular motion is constrained by the sampling guard.
    """
    p0,p1=np.asarray(before['position']),np.asarray(after['position'])
    f0,f1=np.asarray(before['opening']),np.asarray(after['opening'])
    dt=float(after['dt_s'])
    if dt <= 0 or not np.isfinite(dt):raise ValueError('crossing needs positive physics dt')
    if _angular_error(f0[3:],f1[3:]) > .05:return {'status':'opening_rotation_sampling_limit','passed':None}
    local0=_rotation(f0[3:]).T@(p0-f0[:3]);local1=_rotation(f1[3:]).T@(p1-f1[:3])
    if not local0[2] > 0 >= local1[2]:return {'status':'no_downward_crossing','passed':None}
    alpha=float(local0[2]/(local0[2]-local1[2]))
    point=(1-alpha)*local0+alpha*local1
    velocity=_rotation(f1[3:]).T@((p1-p0)-(f1[:3]-f0[:3]))/dt
    speed=float(np.linalg.norm(velocity))
    if speed <= 1e-12:return {'status':'unresolved_velocity','passed':None}
    direction=np.asarray(config.get('expected_velocity_direction',[0,0,-1]),dtype=float)
    direction=direction/np.linalg.norm(direction)
    angle=float(np.arccos(np.clip(velocity@direction/speed,-1,1)))
    error=float(np.linalg.norm(point[:2]-np.asarray(config['target_xy_m'])))
    from shapely.geometry import Point
    aperture=aperture_polygon(config['aperture_profile']);cross=Point(point[:2])
    aperture_error=float(cross.distance(aperture))
    return {'status':'scored','passed':bool(error<=config['position_tolerance_m'] and angle<=config['angle_tolerance_rad'] and aperture.covers(cross)),
            'components':{'crossing_position_error_m':error,'aperture_overrun_m':aperture_error,
                          'velocity_angle_rad':angle,'relative_speed_m_s':speed},
            'point_in_opening_m':point.tolist(),'relative_velocity_m_s':velocity.tolist(),'substep_fraction':alpha}


class FlowObserver:
    def __init__(self,config):
        self.config=deepcopy(config);self.previous={};self.crossings={};self.failures=[];self.last_step=None

    def observe(self,positions,opening,qualified,step,dt,action_index=None):
        if step==self.last_step:return
        if self.last_step is not None and step!=self.last_step+1:
            self.previous.clear();self.failures.append({'physics_step':step,'status':'sampling_gap'})
        self.last_step=step
        current={str(ident):{'position':np.asarray(position).tolist(),'opening':np.asarray(opening).tolist(),
                            'physics_step':step,'dt_s':float(dt),'policy_action_index':action_index}
                 for ident,position in positions.items()}
        for ident,row in current.items():
            if ident in self.crossings or ident not in self.previous or ident not in qualified:continue
            if not (qualified[ident].get('eligible') and qualified[ident].get('exited_while_held_and_tilted')):continue
            before=self.previous[ident]
            if before['dt_s']!=row['dt_s']:
                self.failures.append({'physics_step':step,'status':'simulation_dt_changed'});continue
            result=score_crossing(self.config,before,row)
            if result['status']!='no_downward_crossing':
                self.crossings[ident]={'before':deepcopy(before),'after':deepcopy(row),
                                       'source_exit_provenance':deepcopy(qualified[ident]),'result':result}
        self.previous=current

    def summary(self):
        return {'condition':deepcopy(self.config),'crossings':deepcopy(self.crossings),
                'failures':deepcopy(self.failures),'scored_crossings':sum(r['result']['status']=='scored' for r in self.crossings.values()),
                'interpretation':'first sampled downward opening crossing for source-qualified material identities; not liquid density/volume'}


def validate_source_exit(config, validate_selector, label):
    if not isinstance(config, dict) or set(config) != {'opening', 'aperture_profile'}:
        raise ValueError('source_exit needs an actual opening frame and aperture profile')
    selector = config['opening']
    validate_selector(selector, 'source_exit.opening')
    if (selector['kind'] not in ('calibrated_frame', 'model_calibrated_frame')
            or selector.get('time', 'live') != 'live' or selector['label'] != label):
        raise ValueError('source_exit requires a live calibrated source mouth frame')
    aperture_polygon(config['aperture_profile'])


def score_source_exit(config, before, after):
    """Outward center crossing of the real mouth, preserving aperture holes.

    The local mouth +z points out of the vessel. This sampled center witness
    does not certify a finite particle/ball's entire cross-section fits.
    """
    from shapely.geometry import Point
    p0, p1 = (np.asarray(r['position'], dtype=float) for r in (before, after))
    f0, f1 = (np.asarray(r['opening'], dtype=float) for r in (before, after))
    if (p0.shape != (3,) or p1.shape != (3,) or f0.shape != (7,) or f1.shape != (7,)
            or not all(np.isfinite(v).all() for v in (p0, p1, f0, f1))):
        raise ValueError('source exit needs finite center positions and mouth poses')
    dt = float(after['dt_s'])
    if not np.isfinite(dt) or dt <= 0:raise ValueError('source exit needs positive physics dt')
    if _angular_error(f0[3:], f1[3:]) > .05:
        return {'status': 'opening_rotation_sampling_limit', 'passed': None}
    local0 = _rotation(f0[3:]).T @ (p0-f0[:3])
    local1 = _rotation(f1[3:]).T @ (p1-f1[:3])
    if not local0[2] < 0 <= local1[2]:
        return {'status': 'no_outward_crossing', 'passed': None}
    alpha = float(-local0[2]/(local1[2]-local0[2]))
    point = (1-alpha)*local0+alpha*local1
    overrun = float(Point(point[:2]).distance(aperture_polygon(config['aperture_profile'])))
    return {'status': 'scored', 'passed': bool(aperture_polygon(config['aperture_profile']).covers(Point(point[:2]))),
            'point_in_opening_m': point.tolist(), 'substep_fraction': alpha,
            'aperture_overrun_m': overrun,
            'relative_velocity_m_s': ((_rotation(f1[3:]).T@((p1-p0)-(f1[:3]-f0[:3])))/dt).tolist(),
            'scope': 'sampled material center crosses outward through calibrated source aperture; not whole-material fit'}


class SourceExitObserver:
    """Track adjacent source-mouth samples before source qualification.

    Candidate filtering is vectorized over persistent IDs. Hold and tilt gates
    are applied by the recognizer at the crossing, not inferred from motion.
    """
    def __init__(self, config):
        self.config = deepcopy(config)
        self.previous = {};self.opening = None;self.step = None;self.dt = None
        self.failures = [];self.candidate_count = 0;self.reentries = set();self.outcomes = Counter()

    def observe(self, positions, opening, eligible, step, dt, action_index=None, opening_source=None):
        frame = np.asarray(opening, dtype=float)
        current = {str(i): np.asarray(p, dtype=float) for i, p in positions.items()}
        candidates = {}
        if self.step is not None and step != self.step:
            self.reentries = set()
            if step != self.step+1 or dt != self.dt:
                self.failures.append({'physics_step': step, 'status': 'sampling_gap_or_dt_change'})
            else:
                ids = [i for i in current if i in self.previous and i in eligible]
                if ids:
                    old = np.asarray([self.previous[i] for i in ids])
                    new = np.asarray([current[i] for i in ids])
                    local0 = (old-self.opening[:3])@_rotation(self.opening[3:])
                    local1 = (new-frame[:3])@_rotation(frame[3:])
                    for index in np.flatnonzero((local0[:, 2] >= 0) & (local1[:, 2] < 0)):
                        a = {'position': new[index], 'opening': frame, 'dt_s': dt}
                        b = {'position': old[index], 'opening': self.opening, 'dt_s': dt}
                        if score_source_exit(self.config, a, b)['passed'] is True:
                            self.reentries.add(ids[index])
                    for index in np.flatnonzero((local0[:, 2] < 0) & (local1[:, 2] >= 0)):
                        ident = ids[index]
                        before = {'position': old[index].tolist(), 'opening': self.opening.tolist(),
                                  'physics_step': self.step, 'dt_s': float(self.dt)}
                        after = {'position': new[index].tolist(), 'opening': frame.tolist(),
                                 'physics_step': step, 'dt_s': float(dt), 'policy_action_index': action_index}
                        if opening_source is not None:after['opening_source']=deepcopy(opening_source)
                        candidates[ident] = {'before': before, 'after': after,
                                             'result': score_source_exit(self.config, before, after)}
        if step != self.step:
            self.previous, self.opening, self.step, self.dt = current, frame.copy(), step, dt
            self.candidate_count += len(candidates)
            for row in candidates.values():
                result=row['result']
                self.outcomes['inside_aperture' if result['passed'] is True else
                              'outside_aperture' if result['passed'] is False else result['status']] += 1
        return candidates

    def summary(self):
        return {'condition': deepcopy(self.config), 'candidate_crossings': self.candidate_count,
                'candidate_outcomes':dict(self.outcomes), 'failures': deepcopy(self.failures),
                'scope': 'outward center crossing candidates; accepted witnesses also require source hold and tilt'}
