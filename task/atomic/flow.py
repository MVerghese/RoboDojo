"""Persistent-material crossings of a calibrated receptacle opening."""
from copy import deepcopy
import math
import numpy as np

from task.atomic.geometry import _rotation, _angular_error
from task.atomic.fit import aperture_polygon


def validate_flow(config, validate_selector):
    fields = {'opening', 'aperture_profile', 'target_xy_m', 'position_tolerance_m', 'angle_tolerance_rad'}
    if not isinstance(config, dict) or not fields.issubset(config) or set(config)-fields-{'expected_velocity_direction'}:
        raise ValueError('flow needs opening, aperture, XY target and independent position/angular tolerances')
    validate_selector(config['opening'], 'flow.opening')
    if config['opening']['kind'] not in ('functional_point', 'support_point', 'object_pose','calibrated_frame') or config['opening'].get('time','live') != 'live':
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
