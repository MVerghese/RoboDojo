"""Material deformation evidence for folding, independent of prompt geometry.

This observes cloth deformation, region approach, bend and layer settling. It
does not claim finger/particle force measurements or identify a grasp contact.
"""
from copy import deepcopy
import numpy as np
from task.atomic.geometry import _rotation, _angular_error


def fold_metrics(initial, current):
    moving, target = np.asarray(current['moving']), np.asarray(current['target'])
    normal = _rotation(current['stationary_frame'][3:])[:, 2]
    if _rotation(initial['stationary_frame'][3:])[:,2] @ np.array([0,0,1]) < 0: normal = -normal
    vector = moving-target
    bend = np.arccos(np.clip(_rotation(current['moving_frame'][3:])[:,2] @ _rotation(current['stationary_frame'][3:])[:,2],-1,1))
    initial_bend = np.arccos(np.clip(_rotation(initial['moving_frame'][3:])[:,2] @ _rotation(initial['stationary_frame'][3:])[:,2],-1,1))
    initial_distance = np.linalg.norm(np.asarray(initial['moving'])-initial['target'])
    length = np.linalg.norm(np.asarray(current['crease_b'])-current['crease_a'])
    initial_length = np.linalg.norm(np.asarray(initial['crease_b'])-initial['crease_a'])
    if initial_length <= 1e-8: raise ValueError('fold crease endpoints must be distinct actual material landmarks')
    return {'region_distance_m':float(np.linalg.norm(vector)),
            'closure_m':float(initial_distance-np.linalg.norm(vector)),
            'layer_gap_m':float(vector @ normal),
            'bend_change_rad':float(max(0,bend-initial_bend)),
            'crease_length_fraction':float(length/initial_length)}


class ClothFoldObserver:
    def __init__(self, config, initial):
        self.config=config;self.initial=deepcopy(initial);self.previous=None
        self.peak_gap=0.;self.settle_steps=0;self.metrics={};self.evidence=None
        self.settle_anchor=None

    def observe(self, current):
        c=self.config;m=fold_metrics(self.initial,current)
        baseline=fold_metrics(self.initial,self.initial)['layer_gap_m']
        self.peak_gap=max(self.peak_gap,m['layer_gap_m']-baseline)
        initial_gap=m['layer_gap_m']
        candidate=(self.peak_gap>=c['min_relative_lift_m'] and m['closure_m']>=c['min_closure_m']
                   and m['region_distance_m']<=c['max_region_distance_m']
                   and m['bend_change_rad']>=c['min_bend_rad']
                   and c['min_layer_gap_m']<=initial_gap<=c['max_layer_gap_m']
                   and m['crease_length_fraction']>=c['min_crease_length_fraction'])
        stable=(self.previous is not None and
                max(np.linalg.norm(np.asarray(current[k])-self.previous[k]) for k in ('moving','target','crease_a','crease_b'))<=c['max_position_step_m']
                and max(_angular_error(current[k][3:],self.previous[k][3:]) for k in ('moving_frame','stationary_frame'))<=c['max_angle_step_rad'])
        if self.settle_anchor is not None:
            stable = stable and max(np.linalg.norm(np.asarray(current[k])-self.settle_anchor[k]) for k in ('moving','target','crease_a','crease_b')) <= c['max_settle_displacement_m']
            stable = stable and max(_angular_error(current[k][3:],self.settle_anchor[k][3:]) for k in ('moving_frame','stationary_frame')) <= c['max_settle_angle_rad']
        self.settle_steps=self.settle_steps+1 if candidate and stable else 1 if candidate else 0
        if self.settle_steps == 1:self.settle_anchor=deepcopy(current)
        elif self.settle_steps == 0:self.settle_anchor=None
        self.metrics={**m,'relative_lift_peak_m':self.peak_gap,'stable_steps':self.settle_steps,
                      'evidence_semantics':'material deformation; finger/particle contact not measured'}
        self.previous=deepcopy(current)
        if self.settle_steps>=c['settle_steps']:
            self.evidence={'initial_material_state':deepcopy(self.initial),'current_material_state':deepcopy(current),**self.metrics}
            return True
        return False
