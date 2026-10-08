"""Geometry-independent physical intervals for rigid manipulation.

These recognizers consume synchronized contact reports and live state. Thresholds
are physical recognition parameters, never copied from conditioning targets.
Missing contacts reset intervals; a broken backend raises. No Isaac imports are
needed except resolving a live articulated joint's moving body.
"""
from copy import deepcopy
import math

import numpy as np

from task.atomic.contacts import ContactUnavailable
from task.atomic.geometry import _rotation, _angular_error
from task.atomic.diagnostics import record_requirements


SCHEMAS = {
    'cloth_landmark_fold': ('fold', {'label','moving','target','moving_frame','stationary_frame','crease_a','crease_b',
        'min_relative_lift_m','min_closure_m','min_bend_rad','max_region_distance_m','min_layer_gap_m',
        'max_layer_gap_m','min_crease_length_fraction','settle_steps','max_position_step_m','max_angle_step_rad',
        'max_settle_displacement_m','max_settle_angle_rad'}),
    'supported_release': ('place', {'label', 'arm', 'min_contact_steps', 'transport_threshold_m',
        'support_labels', 'settle_steps', 'max_position_step_m', 'max_angle_step_rad',
        'max_settle_displacement_m', 'max_settle_angle_rad'}),
    'held_tool_push': ('push_with_tool', {'label', 'arm', 'min_contact_steps', 'target_label',
        'support_labels', 'motion_threshold_m', 'tool_motion_threshold_m', 'max_vertical_motion_m'}),
    'held_tool_contact': ('touch_with_tool', {'label', 'arm', 'min_contact_steps', 'target_label',
        'min_impulse_ns', 'tool_contact_suffix', 'target_contact_suffix'}),
    'grip_transfer': ('handover', {'label', 'giver_arm', 'receiver_arm', 'min_contact_steps',
        'overlap_steps', 'receiver_steps', 'max_position_step_m'}),
    'held_insertion': ('insert', {'label', 'arm', 'min_contact_steps', 'target_label', 'tip',
        'opening', 'entry_clearance_m', 'min_depth_m', 'max_depth_m', 'lateral_tolerance_m',
        'axis_tolerance_rad'}),
    'held_multi_tip_insertion': ('insert', {'label', 'arm', 'min_contact_steps', 'target_label',
        'tip_pairs', 'entry_clearance_m', 'min_depth_m', 'max_depth_m', 'axis_tolerance_rad'}),
    'contact_joint_motion': ('actuate', {'label', 'arm', 'min_contact_steps', 'joint_name',
        'min_travel', 'direction'}),
    'button_press_cycle': ('actuate', {'label', 'arm', 'min_contact_steps', 'joint_tag',
        'pressed_ratio', 'released_ratio', 'initial_ratio'}),
    'held_tool_landmark_contact': ('touch_with_tool', {'label', 'arm', 'min_contact_steps',
        'target_label', 'tool_point', 'target_point', 'tool_radius_m', 'target_radius_m', 'min_impulse_ns'}),
    'held_tool_strike': ('touch_with_tool', {'label', 'arm', 'min_contact_steps',
        'target_label', 'tool_point', 'target_point', 'tool_radius_m', 'target_radius_m', 'min_impulse_ns',
        'min_approach_speed_m_s', 'min_retraction_m', 'min_retraction_steps', 'max_retraction_steps'}),
    'contact_constrained_twist': ('twist', {'label', 'arm', 'min_contact_steps', 'target_label',
        'pivot', 'axis', 'direction', 'min_angle_rad', 'max_off_axis_rad', 'max_radius_m',
        'min_depth_m', 'max_depth_m'}),
    'rigid_material_transfer': ('pour', {'label', 'arm', 'min_contact_steps', 'target_label',
        'source_frame', 'target_frame', 'source_half_extents_m', 'target_half_extents_m',
        'material_labels', 'required_count', 'min_tilt_rad', 'settle_steps'}),
    'fluid_material_transfer': ('pour', {'label', 'arm', 'min_contact_steps', 'target_label','fluid_label',
        'source_frame','target_frame','source_half_extents_m','target_half_extents_m',
        'required_count','min_tilt_rad','settle_steps'}),
}

TRANSITIONS = {
    'cloth_landmark_fold': {'folded'},
    'supported_release': {'release', 'settled'}, 'held_tool_push': {'stroke'},
    'held_tool_contact': {'contact'}, 'grip_transfer': {'giver_hold', 'overlap', 'receiver_only'},
    'held_insertion': {'entry', 'inserted'}, 'held_multi_tip_insertion': {'entry', 'inserted'},
    'contact_joint_motion': {'motion'},
    'contact_constrained_twist': {'rotation'},
    'rigid_material_transfer': {'source_exit', 'first_transfer', 'transfer_complete'},
    'button_press_cycle': {'press', 'release', 'cycle'},
    'held_tool_landmark_contact': {'contact'},
    'held_tool_strike': {'impact', 'retracted', 'strike'},
    'fluid_material_transfer': {'source_exit','first_transfer','transfer_complete'},
}
COMPLETION = {'supported_release': 'settled', 'held_tool_push': 'stroke', 'held_tool_contact': 'contact',
              'grip_transfer': 'receiver_only', 'held_insertion': 'inserted',
              'contact_joint_motion': 'motion', 'contact_constrained_twist': 'rotation'}
COMPLETION['rigid_material_transfer'] = 'transfer_complete'
COMPLETION.update(button_press_cycle='cycle', held_tool_landmark_contact='contact')
COMPLETION['held_tool_strike'] = 'strike'
COMPLETION['fluid_material_transfer'] = 'transfer_complete'
COMPLETION['cloth_landmark_fold'] = 'folded'
COMPLETION['held_multi_tip_insertion'] = 'inserted'


def validate_recognition(config, family, validate_selector):
    kind = config.get('kind')
    if kind not in SCHEMAS or SCHEMAS[kind][0] != family:
        raise ValueError(f'unsupported physical recognizer {kind!r} for {family}')
    fields = SCHEMAS[kind][1] | {'kind'}
    optional = {'flow', 'source_exit'} if kind in ('rigid_material_transfer', 'fluid_material_transfer') else set()
    if kind in ('held_tool_strike','held_tool_landmark_contact'):
        optional={'target_candidates','target_identity_margin_m'}
    if set(config) - optional != fields:
        raise ValueError(f'{kind} requires exactly {sorted(fields)}')
    if {'target_candidates','target_identity_margin_m'} & set(config):
        if not {'target_candidates','target_identity_margin_m'} <= set(config):
            raise ValueError('target regions require both candidates and identity margin')
        from task.atomic.target_regions import validate_target_regions
        validate_target_regions(config,validate_selector)
    if 'flow' in config:
        from task.atomic.flow import validate_flow
        validate_flow(config['flow'], validate_selector)
        if config['flow']['opening']['label'] != config['target_label']:
            raise ValueError('flow opening must belong to the material target')
    if 'source_exit' in config:
        from task.atomic.flow import validate_source_exit
        validate_source_exit(config['source_exit'], validate_selector, config['label'])
    if any(config.get(k,{}).get('finite_material_bound') for k in ('flow','source_exit')) and kind!='rigid_material_transfer':
        raise ValueError('finite material mesh bounds require rigid material transfer; fluid radius is not inferred')
    for key in fields & {'label', 'arm', 'giver_arm', 'receiver_arm', 'target_label', 'joint_name', 'joint_tag','fluid_label'}:
        if not isinstance(config[key], str) or not config[key]:
            raise ValueError(f'{kind}.{key} must be a nonempty name')
    for key in fields & {'min_contact_steps', 'settle_steps', 'overlap_steps', 'receiver_steps', 'min_retraction_steps', 'max_retraction_steps'}:
        if type(config[key]) is not int or config[key] < 2:
            raise ValueError(f'{kind}.{key} must be at least two distinct physics steps')
    numeric = fields - {'kind', 'label', 'arm', 'giver_arm', 'receiver_arm', 'target_label',
        'joint_name', 'joint_tag', 'fluid_label','tool_point', 'target_point', 'support_labels', 'tip', 'opening', 'tip_pairs', 'pivot', 'axis', 'direction',
        'tool_contact_suffix', 'target_contact_suffix', 'moving','target','moving_frame','stationary_frame','crease_a','crease_b', 'min_contact_steps', 'settle_steps',
        'overlap_steps', 'receiver_steps', 'source_frame', 'target_frame', 'source_half_extents_m',
        'target_half_extents_m', 'material_labels', 'required_count', 'min_retraction_steps', 'max_retraction_steps'}
    for key in numeric:
        value = config[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ValueError(f'{kind}.{key} must be finite and positive')
    if 'direction' in fields and (type(config['direction']) is not int or config['direction'] not in (-1, 1)):
        raise ValueError('direction must be +1 or -1')
    if 'support_labels' in fields:
        supports = config['support_labels']
        supported = config.get('target_label', config['label'])
        if (not isinstance(supports, list) or not supports or any(not isinstance(s, str) or not s for s in supports)
                or len(set(supports)) != len(supports) or supported in supports):
            raise ValueError('support_labels must name distinct supports excluding the supported object')
    if 'target_label' in fields and config['label'] == config['target_label']:
        raise ValueError('recognition requires distinct manipulated and target objects')
    if kind == 'held_multi_tip_insertion':
        from task.atomic.fit import aperture_polygon
        pairs = config['tip_pairs']
        if not isinstance(pairs, list) or not 2 <= len(pairs) <= 8:
            raise ValueError('multi-tip insertion requires two to eight explicit tip/opening pairs')
        import json
        for pair in pairs:
            if not isinstance(pair, dict) or set(pair) != {'tip', 'opening', 'aperture_profile'}:
                raise ValueError('each tip pair needs a tip, opening and reviewed aperture polygon')
            aperture_polygon(pair['aperture_profile'])
            for key, label in [('tip', config['label']), ('opening', config['target_label'])]:
                validate_selector(pair[key], key)
                if (pair[key]['kind'] not in ('calibrated_frame', 'model_calibrated_frame')
                        or pair[key].get('time', 'live') != 'live' or pair[key]['label'] != label):
                    raise ValueError('tip pairs require live calibrated frames on the specified assets')
        for key in ('tip', 'opening'):
            if len({json.dumps(p[key], sort_keys=True) for p in pairs}) != len(pairs):
                raise ValueError('tip pairs must use distinct tips and openings')
    if kind == 'grip_transfer':
        if config['giver_arm'] == config['receiver_arm'] or {config['giver_arm'], config['receiver_arm']} & {'any', 'nearest'}:
            raise ValueError('handover requires two distinct explicit arms')
    for key in fields & {'tip', 'opening', 'pivot', 'source_frame', 'target_frame', 'tool_point', 'target_point'}:
        validate_selector(config[key], key)
        if config[key]['kind'] not in ('functional_point', 'support_point', 'object_pose', 'object_center_pose','calibrated_frame','model_calibrated_frame') or config[key].get('time', 'live') != 'live':
            raise ValueError(f'{key} must select a live oriented object landmark')
        expected_label = config['label'] if key in ('tip', 'source_frame', 'tool_point') else config['target_label']
        if config[key]['label'] != expected_label:
            raise ValueError(f'{key} must belong to {expected_label}')
    if kind == 'cloth_landmark_fold':
        for key in ('moving','target','moving_frame','stationary_frame','crease_a','crease_b'):
            validate_selector(config[key],key)
            expected = ('cloth_patch_frame','cloth_tag_frame') if key.endswith('frame') else ('cloth_landmark',)
            if config[key]['kind'] not in expected or config[key]['label'] != config['label'] or config[key].get('time','live') != 'live':
                raise ValueError('fold requires live same-garment material landmarks and tangent frames')
        if config['min_crease_length_fraction']>1 or config['min_layer_gap_m']>=config['max_layer_gap_m']:
            raise ValueError('fold layer gap and crease preservation bounds are inconsistent')
    if kind == 'button_press_cycle' and not 0 < config['pressed_ratio'] < config['released_ratio'] <= config['initial_ratio'] <= 1:
        raise ValueError('button ratios require 0 < pressed < released <= initial <= 1')
    if kind == 'held_tool_strike' and config['max_retraction_steps'] < config['min_retraction_steps']:
        raise ValueError('strike retraction window must allow the minimum sample count')
    if 'min_depth_m' in fields and config['max_depth_m'] <= config['min_depth_m']:
        raise ValueError('max_depth_m must exceed min_depth_m')
    if 'axis' in fields:
        axis = np.asarray(config['axis'], dtype=float)
        if axis.shape != (3,) or not np.isfinite(axis).all() or np.linalg.norm(axis) == 0:
            raise ValueError('twist axis must be a finite nonzero 3-vector')
    for key in fields & {'tool_contact_suffix', 'target_contact_suffix'}:
        suffix = config[key]
        if (not isinstance(suffix, str) or not suffix or suffix.startswith('/')
                or any(s in ('', '.', '..') for s in suffix.split('/'))):
            raise ValueError(f'{key} must be a relative collider/body suffix')
    if kind == 'rigid_material_transfer':
        labels = config['material_labels']
        if (not isinstance(labels, list) or not labels or any(not isinstance(l, str) or not l for l in labels)
                or len(set(labels)) != len(labels) or set(labels) & {config['label'], config['target_label']}):
            raise ValueError('material_labels must name distinct rigid contents, excluding vessels')
        if type(config['required_count']) is not int or not 1 <= config['required_count'] <= len(labels):
            raise ValueError('required_count must be within the material population')
    if kind=='fluid_material_transfer':
        if config['fluid_label'] in (config['label'],config['target_label']) or type(config['required_count']) is not int or config['required_count']<1:
            raise ValueError('fluid transfer needs a distinct fluid population and positive integer required_count')
    if kind in ('rigid_material_transfer','fluid_material_transfer'):
        for key in ('source_half_extents_m', 'target_half_extents_m'):
            value = np.asarray(config[key], dtype=float)
            if value.shape != (3,) or not np.isfinite(value).all() or np.any(value <= 0):
                raise ValueError(f'{key} must be a positive finite 3-vector')


class PhysicalRecognizer:
    def __init__(self, session):
        self.session, self.c = session, session.stage.recognition
        self.kind = self.c['kind']
        self.last_step = None
        self.ready = False
        self.evidence = None
        self.state = {}
        self.holds = {}
        self.current_contacts = {}
        self.hold_observation_steps = {}
        self.events = {}
        self.attempt_index = 0
        self.best_twist_interval = None
        self.metrics = {}
        self.eligibility = {}
        self.button_unpressed_sample = None
        self.material = {}
        self.material_bounds = {}
        self.fluid = {}
        self.flow_observer = None
        self.source_exit_observer = None
        if 'flow' in self.c:
            from task.atomic.flow import FlowObserver
            self.flow_observer = FlowObserver(self.c['flow'])
        if 'source_exit' in self.c:
            from task.atomic.flow import SourceExitObserver
            self.source_exit_observer = SourceExitObserver(self.c['source_exit'])
        lm = session.env.scene_manager.layout_manager
        if hasattr(lm, 'instance_type_by_env'):
            expected = ('Garment' if self.kind == 'cloth_landmark_fold' else
                        'Articulation' if self.kind in ('contact_joint_motion', 'button_press_cycle') else 'Rigid')
            name = lm.get_instance_name(env_idx=session.env_idx, label=self.c['label'])
            actual = lm.instance_type_by_env[session.env_idx].get(name)
            if not isinstance(actual, str) or actual.lower() != expected.lower():
                raise RuntimeError(f'{self.kind} expects a {expected} object; {self.c["label"]} is {actual}')
        self.fold_observer = None
        if self.kind == 'cloth_landmark_fold':
            from task.atomic.fold import ClothFoldObserver
            self.fold_observer = ClothFoldObserver(self.c, self._fold_state())
        if self.kind == 'rigid_material_transfer':
            if hasattr(lm, 'instance_type_by_env'):
                for label in self.c['material_labels']:
                    name = lm.get_instance_name(env_idx=session.env_idx, label=label)
                    if str(lm.instance_type_by_env[session.env_idx].get(name)).lower() != 'rigid':
                        raise RuntimeError('rigid material recognition cannot use fluid/cloth/cached articulated geometry')
            self.source_initial_frame = self.session._resolve(self.c['source_frame']).tolist()
            self.source_initial_rotation = _rotation(self.source_initial_frame[3:])
            for label in self.c['material_labels']:
                if any(self.c.get(k,{}).get('finite_material_bound') for k in ('flow','source_exit')):
                    from task.atomic.finite_material import capture_material_bound
                    self.material_bounds[label]=capture_material_bound(self.session,label)
                source = self._material_inside(label, 'source')
                target = self._material_inside(label, 'target')
                self.material[label] = {'initial_in_source': source, 'initial_in_target': target,
                    'eligible': source and not target, 'previous_in_source': source,
                    'exited_while_held_and_tilted': False, 'target_steps': 0}
        if self.kind=='fluid_material_transfer':
            fluid,source,target=self._fluid_state()
            self.fluid_mass=fluid['nominal_mass_kg']
            self.source_initial_rotation=_rotation(self.session._resolve(self.c['source_frame'])[3:])
            self.fluid_initial={'ids':fluid['ids'].tolist(),'positions':fluid['positions'].tolist(),'source':fluid['source'],
                'physics_step':session.env._atomic_contacts.steps,
                'region_frames':deepcopy(self.fluid_region_frames),
                'initial_in_source':source.tolist(),'initial_in_target':target.tolist()}
            for ident,s,t in zip(fluid['ids'],source,target):
                self.fluid[int(ident)]={'eligible':bool(s and not t),'previous_in_source':bool(s),
                    'exited_while_held_and_tilted':False,'target_steps':0}
            if sum(m['eligible'] for m in self.fluid.values())<self.c['required_count']:
                raise ValueError('fluid required_count exceeds the initial source-only cohort; calibrate interior volumes; '
                    f'initial_total={len(fluid["ids"])} source={int(source.sum())} target={int(target.sum())} '
                    f'source_only={sum(m["eligible"] for m in self.fluid.values())} '
                    f'source_frame={self.session._resolve(self.c["source_frame"]).tolist()} '
                    f'target_frame={self.session._resolve(self.c["target_frame"]).tolist()} '
                    f'particle_world_bounds_m={[fluid["positions"].min(0).tolist(), fluid["positions"].max(0).tolist()]}')
        if self.kind == 'button_press_cycle':
            self.contacts=getattr(session.env,'_atomic_contacts',None)
            if self.contacts is not None and not getattr(self.contacts,'errors',[]):
                joint,body,ratio=self._button_joint_state()
                if ratio > self.c['initial_ratio'] and not self._touching():
                    self.button_unpressed_sample={'physics_step':self.contacts.steps,'moving_body':body,
                        'joint_ratio':ratio,'joint_state':joint,'robot_touching':False,
                        'context':'stage_activation_snapshot'}

    def _hold(self, label, arm, fingers=2, body_path=None):
        self.hold_observation_steps[(label, arm, fingers)] = self.contacts.steps
        selector = {'kind': 'contact_points', 'label': label, 'arm': arm, 'min_finger_bodies': fingers}
        if body_path:
            selector['body_path'] = body_path
        try:
            _, source = self.contacts.resolve(selector, self.session.env_idx)
        except ContactUnavailable:
            self.holds.pop((label, arm, fingers), None)
            self.current_contacts.pop((label, arm, fingers), None)
            return None
        key = (label, arm, fingers)
        old = self.holds.get(key)
        count = old[1] + 1 if old and old[0] == source['resolved_arm'] else 1
        source = {**source, 'consecutive_contact_steps': count,
                  'contact_interval_start_step': self.contacts.steps - count + 1}
        self.holds[key] = (source['resolved_arm'], count)
        self.current_contacts[key] = source
        return source if count >= self.c['min_contact_steps'] else None

    def _current_hold(self, fingers=2):
        return self.current_contacts.get((self.c['label'], self.c['arm'], fingers))

    def _touching(self, arm='any', fingers=1):
        try:
            _, source = self.contacts.resolve({'label': self.c['label'], 'arm': arm,
                'min_finger_bodies': fingers}, self.session.env_idx)
            return source
        except ContactUnavailable:
            return None

    def _pair(self):
        try:
            measured, source = self.contacts.resolve_object_pair({'label': self.c['label'],
                'other_label': self.c['target_label']}, self.session.env_idx)
            return {**source, 'measured_contact_points': deepcopy(measured)}
        except ContactUnavailable:
            return None

    def _pose(self, label=None):
        return self.session._object_pose(label or self.c['label'])

    def _emit(self, **values):
        self.ready = True
        self.evidence = {'kind': self.kind, 'attempt_index': self.attempt_index, 'physics_step': self.contacts.steps,
            'policy_action_index': self.session._action_index(), **deepcopy(values)}
        self._event(COMPLETION[self.kind], **values)

    def _event(self, name, **values):
        if name not in self.events:
            self.events[name] = {'name': name, 'attempt_index': self.attempt_index, 'physics_step': self.contacts.steps,
                'policy_action_index': self.session._action_index(), **deepcopy(values)}

    def _reset_attempt(self, reason):
        """Keep interrupted physical windows separate from a later completion.

        Completed evidence is immutable. Source-qualified material transfers
        have per-particle histories rather than this single interaction window.
        """
        if self.kind=='contact_constrained_twist' and len(self.state.get('rotation_samples',[]))>=2:
            interval=self.twist_interval()
            if interval is not None and (self.best_twist_interval is None or
                    self.c['direction']*interval['signed_angle_rad']>self.c['direction']*self.best_twist_interval['signed_angle_rad']):
                self.best_twist_interval=interval
        if (self.events and not self.session.success and self.kind in {
                'held_tool_strike', 'grip_transfer', 'held_insertion',
                'held_multi_tip_insertion', 'supported_release', 'contact_constrained_twist'}):
            self.session.abort_recognition_attempt(self.events, reason, self.attempt_index, self.evidence)
            self.events.clear()
            self.evidence = None
            self.attempt_index += 1
        self.state.clear()

    def _diagnose(self, gates, **measurements):
        """Retain observed physical requirements without changing recognition.

        Counts span attempts, count distinct sampled physics steps, and do not
        imply independent sensor coverage. None means a requirement was not
        evaluated on this sample, rather than false or zero.
        """
        record_requirements(self.eligibility, self.contacts.steps, self.session._action_index(), gates, measurements)

    def _observed_hold_gate(self, arm=None, fingers=2):
        key=(self.c['label'],arm or self.c['arm'],fingers)
        if self.hold_observation_steps.get(key) != self.contacts.steps:
            return None
        source=self.current_contacts.get(key)
        return bool(source and source['consecutive_contact_steps'] >= self.c['min_contact_steps'])

    def _diagnose_remaining(self):
        """Read requirements already measured by the other physical adapters."""
        c,m=self.c,self.metrics
        hold=self._observed_hold_gate() if 'arm' in c else None
        if self.kind == 'supported_release':
            self._diagnose({'sustained_hold':hold,'transported_while_held':bool(self.state.get('transported')),
                'robot_separated':not bool(m['contacting_fingers']),'support_contact':bool(m['support_contacts']),
                'settling_interval_long_enough':self.state.get('settling',(None,0))[1] >= c['settle_steps']},
                transport_m=self.state.get('transport_m'),stable_steps=m.get('stable_steps'))
        elif self.kind == 'grip_transfer':
            self._diagnose({'giver_sustained_hold':self._observed_hold_gate(c['giver_arm']),
                'receiver_sustained_hold':self._observed_hold_gate(c['receiver_arm']),
                'giver_separated':not bool(self._touching(c['giver_arm'])),
                'overlap_long_enough':self.state.get('overlap',0) >= c['overlap_steps'],
                'receiver_only_long_enough':self.state.get('released_steps',0) >= c['receiver_steps']},
                phase=self.state.get('phase','giver'),overlap_steps=self.state.get('overlap',0),
                receiver_only_steps=self.state.get('released_steps',0))
        elif self.kind == 'held_insertion':
            depth=m['insertion_depth_m']
            self._diagnose({'sustained_hold':hold,'target_contact':bool(self._pair()),
                'entered_from_outside':bool(self.state.get('entered_from_outside')),
                'lateral_alignment':m['lateral_error_m'] <= c['lateral_tolerance_m'],
                'axis_alignment':m['axis_error_rad'] <= c['axis_tolerance_rad'],
                'insertion_depth':c['min_depth_m'] <= depth <= c['max_depth_m']},
                insertion_depth_m=depth,lateral_error_m=m['lateral_error_m'],axis_error_rad=m['axis_error_rad'])
        elif self.kind == 'held_multi_tip_insertion':
            pairs=m['tip_pairs']
            self._diagnose({'sustained_hold':hold,'target_contact':bool(self._pair()),
                'all_tips_observed_outside':bool(self.state.get('outside')) and all(bool(v) for v in self.state['outside']),
                'all_tip_centers_inside_apertures':all(p['projected_tip_inside_aperture'] for p in pairs),
                'all_axes_aligned':all(p['axis_error_rad'] <= c['axis_tolerance_rad'] for p in pairs),
                'all_depths_in_range':all(c['min_depth_m'] <= p['depth_m'] <= c['max_depth_m'] for p in pairs)},
                tip_depths_m=[p['depth_m'] for p in pairs],axis_errors_rad=[p['axis_error_rad'] for p in pairs])
        elif self.kind == 'contact_constrained_twist':
            angle=m['signed_angle_rad'];off=m['off_axis_rotation_rad']
            self._diagnose({'sustained_hold':hold,'constraint_contact':m['constraint_contact'],
                'pivot_radius':m['pivot_radius_m'] <= c['max_radius_m'],
                'pivot_depth':c['min_depth_m'] <= m['pivot_depth_m'] <= c['max_depth_m'],
                'rotation_travel':None if angle is None else c['direction']*angle >= c['min_angle_rad'],
                'off_axis_rotation':None if off is None else off <= c['max_off_axis_rad']},
                **{k:m[k] for k in ('pivot_radius_m','pivot_depth_m','signed_angle_rad','off_axis_rotation_rad')})
        elif self.kind in ('fluid_material_transfer','rigid_material_transfer'):
            counts=m['counts'] if self.kind == 'fluid_material_transfer' else m
            population=self.fluid if self.kind == 'fluid_material_transfer' else self.material
            self._diagnose({'sustained_hold':hold,
                'source_cohort_large_enough':counts['initially_eligible'] >= c['required_count'],
                'any_qualified_source_exit':any(v['exited_while_held_and_tilted'] for v in population.values()),
                'enough_settled_transfers':counts['transferred'] >= c['required_count']},
                initially_eligible_count=counts['initially_eligible'],transferred_count=counts['transferred'],
                source_exit_semantics='outward_aperture_passage' if self.source_exit_observer else 'core_departure')
        elif self.kind == 'cloth_landmark_fold':
            self._diagnose({'lift':m['relative_lift_peak_m'] >= c['min_relative_lift_m'],
                'closure':m['closure_m'] >= c['min_closure_m'],
                'region_distance':m['region_distance_m'] <= c['max_region_distance_m'],
                'new_bend':m['bend_change_rad'] >= c['min_bend_rad'],
                'landmark_layer_gap':c['min_layer_gap_m'] <= m['layer_gap_m'] <= c['max_layer_gap_m'],
                'crease_chord_length':m['crease_length_fraction'] >= c['min_crease_length_fraction'],
                'settling_interval_long_enough':m['stable_steps'] >= c['settle_steps']},
                **{k:m[k] for k in ('relative_lift_peak_m','closure_m','region_distance_m','bend_change_rad','layer_gap_m','crease_length_fraction','stable_steps')})
        elif self.kind == 'held_tool_strike':
            speed=m.get('toward_surface_speed_m_s');impulse=m.get('total_impulse_ns')
            self._diagnose({'sustained_hold':hold,'tool_target_contact':m.get('tool_target_contact'),
                'preimpact_velocity':None if speed is None else speed >= c['min_approach_speed_m_s'],
                'landmark_force_contact':None if impulse is None else impulse >= c['min_impulse_ns'],
                'retracted': 'retracted' in self.events},
                phase=self.state.get('phase','approach'),toward_surface_speed_m_s=speed,total_impulse_ns=impulse,
                rise_m=m.get('rise_m'),separated_steps=m.get('separated_steps'))

    def observe(self):
        self.contacts = getattr(self.session.env, '_atomic_contacts', None)
        if self.contacts is None:
            raise RuntimeError('physical action recognition requires initialized PhysX contacts')
        if getattr(self.contacts, 'errors', []):
            raise RuntimeError('PhysX contact reporting failed: ' + self.contacts.errors[-1])
        step = self.contacts.steps
        if step == self.last_step:
            return
        if self.last_step is not None and step != self.last_step + 1:
            self._reset_attempt('sampling_gap')
            self.holds.clear()
            self.current_contacts.clear()
            if self.fold_observer:
                self.fold_observer.previous = None
                self.fold_observer.settle_steps = 0
                self.fold_observer.peak_gap = 0.
                self.fold_observer.settle_anchor = None
            for label, m in self.material.items():
                m.update(exited_while_held_and_tilted=False, target_steps=0,
                         previous_in_source=self._material_inside(label, 'source'))
            if self.fluid:
                fluid,source,_=self._fluid_state()
                for ident,inside in zip(fluid['ids'],source):
                    self.fluid[int(ident)].update(exited_while_held_and_tilted=False,target_steps=0,previous_in_source=bool(inside))
        self.last_step, self.ready = step, False
        getattr(self, '_' + self.kind)()
        if self.eligibility.get('last_physics_step') != step:
            self._diagnose_remaining()
        if self.eligibility:
            self.metrics['eligibility'] = deepcopy(self.eligibility)
        if self.flow_observer:
            if self.kind == 'fluid_material_transfer':
                fluid, _, _ = self._fluid_state()
                positions = {str(i): p for i,p in zip(fluid['ids'],fluid['positions'])}
                provenance = {str(i): m for i,m in self.fluid.items() if m['eligible'] and m['exited_while_held_and_tilted']}
            else:
                positions = {label:self.session._resolve({'kind':'object_center_position','label':label}) for label in self.c['material_labels']}
                provenance = {label:m for label,m in self.material.items() if m['eligible'] and m['exited_while_held_and_tilted']}
            opening = self.session._resolve(self.c['flow']['opening'])
            self.flow_observer.observe(positions,opening,provenance,self.contacts.steps,
                self.session.env.dt,self.session._action_index(),self.material_bounds)

    def _fold_state(self):
        states={'sources':{}}
        for key in ('moving','target','moving_frame','stationary_frame','crease_a','crease_b'):
            value,source=self.session._resolve_with_source(self.c[key])
            states[key]=(value['position'] if isinstance(value,dict) else value.tolist())
            states['sources'][key]=source
        return states

    def _cloth_landmark_fold(self):
        ready=self.fold_observer.observe(self._fold_state())
        self.metrics=deepcopy(self.fold_observer.metrics)
        if ready:self._emit(**self.fold_observer.evidence)

    def _supported_release(self):
        pose = self._pose()
        hold = self._hold(self.c['label'], self.c['arm'])
        raw_hold = self._current_hold()
        touch = self._touching()
        # Observe support even while fingers are closed: a body can contact
        # its support and sleep before the last finger releases.
        support = self.contacts.support_evidence(self.c['label'], self.c['support_labels'], self.session.env_idx)
        self.metrics['support_seen_steps'] = self.metrics.get('support_seen_steps', 0) + int(bool(support['contacts']))
        self.metrics.update(physics_step=self.contacts.steps,
                            current_pose=pose.tolist(),
                            support_contacts=len(support['contacts']),
                            contacting_fingers=len(touch.get('finger_bodies', [])) if touch else 0,
                            transported_while_held=bool(self.state.get('transported')))
        if touch:
            self.state.pop('settling', None)
            self.state.pop('settling_samples', None)
            self.state.pop('separated_since_step', None)
            self.state.pop('separated_steps', None)
            if 'release' in self.events and not self.session.success:
                if raw_hold is None and 'settled' not in self.events:
                    # A one-jaw brush is not a new grasp. Keep the proven
                    # transport and first release, but restart all separation/
                    # settling duration. Two-jaw recontact still starts a new
                    # attempt; a completed historical placement cannot be reused.
                    recontacts = self.state.setdefault('post_release_recontacts', {'sampled_steps': 0})
                    recontacts['sampled_steps'] += 1
                    recontacts['last_physics_step'] = self.contacts.steps
                    recontacts['last_contact'] = deepcopy(touch)
                    self.metrics['phase'] = 'post_release_single_finger_recontact'
                    return
                self._reset_attempt('regrasp_after_release')
            if raw_hold:
                arm = raw_hold['resolved_arm']
                if self.state.get('arm') != arm:
                    self._reset_attempt('contacting_arm_changed')
                    self.state.update(arm=arm, anchor=pose.copy(), transported=False)
                moved = np.linalg.norm(pose[:3] - self.state['anchor'][:3])
                if hold and moved >= self.c['transport_threshold_m']:
                    self.state.update(transported=True, hold=deepcopy(hold), transport_m=float(moved))
                    self.metrics['phase'] = 'transported_held'
            elif self.state.get('transported') and touch['resolved_arm'] == self.state.get('arm'):
                # Opening a gripper commonly loses one jaw before the other.
                # Preserve already verified two-finger transport until the last
                # finger releases. One-finger motion cannot establish transport.
                self.metrics['phase'] = 'partial_release'
            else:
                # A one-finger push is not a prior grasp; require sustained hold again.
                self._reset_attempt('physical_interval_invalidated')
                self.metrics['phase'] = 'touch_without_verified_transport'
            return
        if not self.state.get('transported'):
            self._reset_attempt('physical_interval_invalidated')
            return
        self._event('release', held_contact=self.state['hold'], pose=pose.tolist())
        self.state.setdefault('separated_since_step', self.contacts.steps)
        self.state['separated_steps'] = self.state.get('separated_steps', 0) + 1
        self.metrics.update(phase='released', support_contacts=len(support['contacts']),
                            support_diagnostics=deepcopy({k: v for k, v in support.items() if k != 'contacts'}))
        old = self.state.get('settling')
        if not support['contacts']:
            self.state.pop('settling', None)
            self.state.pop('settling_samples', None)
            return
        stable = (old is not None and np.linalg.norm(pose[:3] - old[0][:3]) <= self.c['max_position_step_m']
                  and _angular_error(pose[3:], old[0][3:]) <= self.c['max_angle_step_rad']
                  and np.linalg.norm(pose[:3] - old[2][:3]) <= self.c['max_settle_displacement_m']
                  and _angular_error(pose[3:], old[2][3:]) <= self.c['max_settle_angle_rad'])
        count = old[1] + 1 if stable else 1
        anchor = old[2] if stable else pose.copy()
        self.state['settling'] = (pose.copy(), count, anchor)
        sample={'physics_step':self.contacts.steps,'pose':pose.tolist(),
            'dt_s':getattr(self.session.env,'dt',None),'robot_touching':False,
            'support':deepcopy(support)}
        if stable:
            self.state['settling_samples'].append(sample)
            del self.state['settling_samples'][:-self.c['settle_steps']]
        else:
            self.state['settling_samples']=[sample]
            self.state['settle_anchor_step']=self.contacts.steps
        self.metrics.update(phase='settling', stable_steps=count,
                            settle_displacement_m=float(np.linalg.norm(pose[:3] - anchor[:3])),
                            settle_angle_rad=_angular_error(pose[3:], anchor[3:]))
        if count >= self.c['settle_steps']:
            self._emit(held_contact=self.state['hold'], released=True, stable_steps=count,
                transport_m=self.state['transport_m'], support=support, pose=pose.tolist(),
                settle_displacement_m=float(np.linalg.norm(pose[:3] - anchor[:3])),
                settle_angle_rad=_angular_error(pose[3:], anchor[3:]),
                separated_since_step=self.state['separated_since_step'],
                separated_steps=self.state['separated_steps'], robot_touching=False,
                settling_samples=self.state['settling_samples'],settle_anchor_pose=anchor.tolist(),
                settle_anchor_step=self.state['settle_anchor_step'],
                post_release_recontacts=deepcopy(self.state.get('post_release_recontacts', {})))

    def _held_tool_push(self):
        hold = self._hold(self.c['label'], self.c['arm'])
        raw_hold = self._current_hold()
        pair = self._pair()
        support = self.contacts.support_evidence(self.c['target_label'], self.c['support_labels'], self.session.env_idx)
        gates = {'two_finger_contact': bool(raw_hold), 'sustained_hold': bool(hold),
            'tool_target_contact': bool(pair), 'target_support_contact': bool(support['contacts']),
            'contact_interval_long_enough': None, 'target_planar_motion': None,
            'tool_planar_motion': None, 'target_vertical_motion_within_bound': None}
        if not raw_hold or not pair or not support['contacts']:
            self._diagnose(gates, consecutive_contact_steps=0)
            self._reset_attempt('physical_interval_invalidated')
            return
        tool, target = self._pose(), self._pose(self.c['target_label'])
        if self.state.get('arm') != raw_hold['resolved_arm']:
            self.state.update(arm=raw_hold['resolved_arm'], tool=tool.copy(), target=target.copy(), count=0)
        self.state['count'] += 1
        dt, do = tool[:3] - self.state['tool'][:3], target[:3] - self.state['target'][:3]
        gates.update(contact_interval_long_enough=self.state['count'] >= self.c['min_contact_steps'],
            target_planar_motion=bool(np.linalg.norm(do[:2]) >= self.c['motion_threshold_m']),
            tool_planar_motion=bool(np.linalg.norm(dt[:2]) >= self.c['tool_motion_threshold_m']),
            target_vertical_motion_within_bound=bool(abs(do[2]) <= self.c['max_vertical_motion_m']))
        self._diagnose(gates, consecutive_contact_steps=self.state['count'],
            target_displacement_m=do.tolist(), tool_displacement_m=dt.tolist(),
            target_planar_displacement_m=float(np.linalg.norm(do[:2])),
            tool_planar_displacement_m=float(np.linalg.norm(dt[:2])),
            target_vertical_displacement_m=float(do[2]))
        if abs(do[2]) > self.c['max_vertical_motion_m']:
            self._reset_attempt('physical_interval_invalidated')
            return
        if (hold and self.state['count'] >= self.c['min_contact_steps'] and
                np.linalg.norm(do[:2]) >= self.c['motion_threshold_m'] and
                np.linalg.norm(dt[:2]) >= self.c['tool_motion_threshold_m']):
            self._emit(held_contact=hold, tool_target_contact=pair, support=support,
                target_displacement_m=do.tolist(), tool_displacement_m=dt.tolist(),
                consecutive_contact_steps=self.state['count'])

    def _held_tool_contact(self):
        hold = self._hold(self.c['label'], self.c['arm'])
        pair = self._pair()
        if not pair:
            self._diagnose({'sustained_hold': bool(hold), 'tool_target_contact': False,
                'new_encounter': False, 'declared_parts_contact': None, 'minimum_impulse': None})
            self.state['clear'] = True
            return
        # First force-bearing encounter after separation, not sustained resting contact.
        clear = self.state.pop('clear', False)
        roots = pair['object_roots']
        wanted = [roots[0] + '/' + self.c['tool_contact_suffix'],
                  roots[1] + '/' + self.c['target_contact_suffix']]
        def match(row, i, path):
            return any(p == path or p.startswith(path + '/') for p in (row[f'actor{i}'], row[f'collider{i}']))
        rows = [r for r in pair['contacts'] if any(match(r, i, wanted[0]) and match(r, 1-i, wanted[1]) for i in (0, 1))]
        impulse = sum(float(np.linalg.norm(r['impulse'])) for r in rows)
        self._diagnose({'sustained_hold': bool(hold), 'tool_target_contact': True,
            'new_encounter': clear, 'declared_parts_contact': bool(rows),
            'minimum_impulse': impulse >= self.c['min_impulse_ns']},
            declared_part_contact_count=len(rows), total_impulse_ns=impulse)
        if clear and hold and rows and impulse >= self.c['min_impulse_ns']:
            self._emit(held_contact=hold, tool_target_contacts=rows, total_impulse_ns=impulse)

    def _held_tool_landmark_contact(self):
        hold, pair = self._hold(self.c['label'], self.c['arm']), self._pair()
        if not pair:
            self._diagnose({'sustained_hold': bool(hold), 'tool_target_contact': False,
                'new_encounter': False, 'declared_landmarks_contact': None, 'minimum_impulse': None})
            self.state['clear'] = True
            return
        clear = self.state.pop('clear', False)
        if not clear or not hold:
            self._diagnose({'sustained_hold': bool(hold), 'tool_target_contact': True,
                'new_encounter': clear, 'declared_landmarks_contact': None, 'minimum_impulse': None})
            return
        evidence = self._landmark_contact(pair)
        self._diagnose({'sustained_hold': True, 'tool_target_contact': True, 'new_encounter': True,
            'declared_landmarks_contact': bool(evidence['tool_target_contacts']),
            'minimum_impulse': evidence['total_impulse_ns'] >= self.c['min_impulse_ns']},
            contact_count=len(evidence['tool_target_contacts']), total_impulse_ns=evidence['total_impulse_ns'],
            tool_landmark_distances_m=evidence['tool_landmark_distances_m'],
            target_landmark_distances_m=evidence['target_landmark_distances_m'])
        if evidence['tool_target_contacts'] and evidence['total_impulse_ns'] >= self.c['min_impulse_ns']:
            self._emit(held_contact=hold, **evidence)

    def _landmark_contact(self, pair):
        tool = self.session._resolve(self.c['tool_point'])[:3]
        target = self.session._resolve(self.c['target_point'])[:3]
        points = np.asarray(pair['measured_contact_points'].get('points', []), dtype=float)
        if points.shape != (len(pair['contacts']), 3) or not np.isfinite(points).all():
            raise RuntimeError('landmark contact requires synchronized per-contact environment-local positions')
        tool_distance = np.linalg.norm(points - tool, axis=1)
        target_distance = np.linalg.norm(points - target, axis=1)
        eligible = (tool_distance <= self.c['tool_radius_m']) & (target_distance <= self.c['target_radius_m'])
        identity=None
        if 'target_candidates' in self.c:
            from task.atomic.target_regions import region_membership
            frames=[self.session._resolve_with_source(selector) for selector in self.c['target_candidates']]
            poses=[np.asarray(pose).tolist() for pose,source in frames]
            index=self.c['target_candidates'].index(self.c['target_point'])
            membership=region_membership(points,poses,index,self.c['target_identity_margin_m'])
            eligible &= np.asarray(membership['eligible'],dtype=bool)
            identity={'kind':'nearest_landmark_region','candidate_selectors':deepcopy(self.c['target_candidates']),
                'candidate_poses':poses,'candidate_sources':[{**source,'physics_step':self.contacts.steps} for pose,source in frames],
                'target_index':index,'margin_m':self.c['target_identity_margin_m'],
                'physics_step':self.contacts.steps,'frame':'environment_local_world',
                'all_contact_points':points.tolist(),'all_contact_assignments':membership,
                **{key:np.asarray(values)[eligible].tolist() for key,values in membership.items() if key!='eligible'}}
        rows = [row for row, accept in zip(pair['contacts'], eligible) if accept]
        impulse = sum(float(np.linalg.norm(row['impulse'])) for row in rows)
        return {'tool_target_contacts':rows,'contact_points':points[eligible].tolist(),'total_impulse_ns':impulse,
                **({'target_identity':identity} if identity is not None else {}),
                'tool_landmark_position':tool.tolist(),'target_landmark_position':target.tolist(),
                'tool_landmark_distances_m':tool_distance[eligible].tolist(),
                'target_landmark_distances_m':target_distance[eligible].tolist()}

    def _held_tool_strike(self):
        self.metrics={'physics_step':self.contacts.steps,'phase':self.state.get('phase','approach'),
            'tool_target_contact':None,'toward_surface_speed_m_s':None,'total_impulse_ns':None}
        if self.state.get('phase') == 'completed':
            return
        dt=float(getattr(self.session.env,'dt',float('nan')))
        if not math.isfinite(dt) or dt<=0:
            raise RuntimeError('strike recognition requires finite positive simulation dt')
        hold=self._hold(self.c['label'],self.c['arm'])
        raw=self._current_hold()
        if not raw or self.state.get('arm',raw['resolved_arm'])!=raw['resolved_arm']:
            self._reset_attempt('physical_interval_invalidated')
            return
        self.state['arm']=raw['resolved_arm']
        tool=self.session._resolve(self.c['tool_point'])
        target=self.session._resolve(self.c['target_point'])
        relative=tool[:3]-target[:3]; rotation=_rotation(target[3:])
        pair=self._pair()
        self.metrics['tool_target_contact']=bool(pair)
        if self.state.get('phase')=='impact':
            if self.contacts.steps-self.state['impact_step']>self.c['max_retraction_steps']:
                self._reset_attempt('physical_interval_invalidated')
                return
            self.state['clear_steps']=0 if pair else self.state['clear_steps']+1
            rise=float((rotation.T@relative)[2]-self.state['impact_height'])
            self.metrics.update(rise_m=rise,separated_steps=self.state['clear_steps'])
            if hold and self.state['clear_steps']>=self.c['min_retraction_steps'] and rise>=self.c['min_retraction_m']:
                self._event('retracted',rise_m=rise,separated_steps=self.state['clear_steps'])
                self._emit(held_contact=hold,impact=deepcopy(self.state['impact']),rise_m=rise,
                    separated_steps=self.state['clear_steps'],elapsed_physics_steps=self.contacts.steps-self.state['impact_step'])
                self.state['phase']='completed'
            return
        history=self.state.setdefault('approach',[])
        if not pair:
            history.append({'physics_step':self.contacts.steps,'dt_s':dt,'tool_pose':tool.tolist(),
                'target_pose':target.tolist(),'relative_position':relative.tolist()})
            del history[:-2]
            return
        # Velocity comes from two separated pre-impact samples, not the pose
        # already stopped by the collision solver or a policy action command.
        previous=deepcopy(history); history.clear()
        if not hold or len(previous)!=2 or previous[-1]['physics_step']!=self.contacts.steps-1 or any(p['dt_s']!=dt for p in previous):
            return
        velocity=(np.asarray(previous[1]['relative_position'])-previous[0]['relative_position'])/dt
        normal=_rotation(previous[1]['target_pose'][3:])[:,2]
        speed=-float(velocity@normal)
        evidence=self._landmark_contact(pair)
        self.metrics.update(toward_surface_speed_m_s=speed,total_impulse_ns=evidence['total_impulse_ns'])
        if 'target_identity' in evidence:self.metrics['target_identity']=deepcopy(evidence['target_identity'])
        if speed<self.c['min_approach_speed_m_s'] or not evidence['tool_target_contacts'] or evidence['total_impulse_ns']<self.c['min_impulse_ns']:
            return
        impact={'held_contact':hold,'approach_samples':previous,'relative_velocity_m_s':velocity.tolist(),
                'toward_surface_speed_m_s':speed,**evidence}
        self.state.update(phase='impact',impact=deepcopy(impact),impact_step=self.contacts.steps,
                          impact_height=float((rotation.T@relative)[2]),clear_steps=0)
        self._event('impact',**impact)

    def _grip_transfer(self):
        pose = self._pose()
        old = self.state.get('pose')
        if old is not None and np.linalg.norm(pose[:3] - old[:3]) > self.c['max_position_step_m']:
            self._reset_attempt('physical_interval_invalidated')
        self.state['pose'] = pose.copy()
        giver = self._hold(self.c['label'], self.c['giver_arm'])
        receiver = self._hold(self.c['label'], self.c['receiver_arm'])
        phase = self.state.get('phase', 'giver')
        if phase == 'giver':
            if giver and not self._touching(self.c['receiver_arm']):
                self.state.update(phase='overlap', giver=deepcopy(giver), overlap=0)
                self._event('giver_hold', contact=giver)
        elif phase == 'overlap':
            if not giver:
                self._reset_attempt('physical_interval_invalidated')
            elif receiver:
                self.state['overlap'] += 1
                if self.state['overlap'] >= self.c['overlap_steps']:
                    self.state.update(phase='release', receiver=deepcopy(receiver), released_steps=0)
                    self._event('overlap', giver_contact=giver, receiver_contact=receiver)
            else:
                self.state['overlap'] = 0
        elif phase == 'release':
            if not receiver:
                self._reset_attempt('physical_interval_invalidated')
            elif self._touching(self.c['giver_arm']):
                self.state['released_steps'] = 0
            else:
                self.state['released_steps'] += 1
                if self.state['released_steps'] >= self.c['receiver_steps']:
                    self._emit(giver_contact=self.state['giver'], receiver_contact=receiver,
                        overlap_steps=self.state['overlap'], receiver_only_steps=self.state['released_steps'])

    def _held_insertion(self):
        hold = self._hold(self.c['label'], self.c['arm'])
        raw_hold = self._current_hold()
        tip, opening = self.session._resolve(self.c['tip']), self.session._resolve(self.c['opening'])
        rt, ro = _rotation(tip[3:]), _rotation(opening[3:])
        local = ro.T @ (tip[:3] - opening[:3])
        depth, lateral = -float(local[2]), float(np.linalg.norm(local[:2]))
        angle = float(np.arccos(np.clip(rt[:, 2] @ ro[:, 2], -1, 1)))
        self.metrics = {'physics_step': self.contacts.steps, 'insertion_depth_m': depth,
                        'lateral_error_m': lateral, 'axis_error_rad': angle,
                        'currently_held': bool(hold), 'opening_pose': opening.tolist(), 'tip_pose': tip.tolist(),
                        'entered_from_outside': bool(self.state.get('entered_from_outside'))}
        if not raw_hold or lateral > self.c['lateral_tolerance_m'] or angle > self.c['axis_tolerance_rad']:
            self._reset_attempt('physical_interval_invalidated')
            return
        if self.state.get('arm') != raw_hold['resolved_arm']:
            self._reset_attempt('physical_interval_invalidated')
        if depth > self.c['max_depth_m']:
            self._reset_attempt('physical_interval_invalidated')
        if depth <= -self.c['entry_clearance_m']:
            self.state.update(entered_from_outside=True, arm=raw_hold['resolved_arm'], initial_depth=depth)
        self.state['last_depth'] = depth
        if self.state.get('entered_from_outside') and depth >= 0:
            self._event('entry', depth_m=depth, opening_pose=opening.tolist(), tip_pose=tip.tolist())
        pair = self._pair()
        if (hold and self.state.get('entered_from_outside') and pair
                and self.c['min_depth_m'] <= depth <= self.c['max_depth_m']):
            self._emit(held_contact=hold, insertion_contact=pair, depth_m=depth,
                initial_depth_m=self.state['initial_depth'], lateral_error_m=lateral,
                axis_error_rad=angle, opening_pose=opening.tolist(), tip_pose=tip.tolist())

    def _held_multi_tip_insertion(self):
        from shapely.geometry import Point
        from task.atomic.fit import aperture_polygon
        hold = self._hold(self.c['label'], self.c['arm'])
        raw = self._current_hold()
        rows = []
        for pair in self.c['tip_pairs']:
            tip = self.session._resolve(pair['tip'])
            opening = self.session._resolve(pair['opening'])
            rt, ro = _rotation(tip[3:]), _rotation(opening[3:])
            local = ro.T @ (tip[:3]-opening[:3])
            point = Point(local[:2]); aperture = aperture_polygon(pair['aperture_profile'])
            rows.append({'tip_pose': tip.tolist(), 'opening_pose': opening.tolist(),
                'depth_m': -float(local[2]), 'projected_tip_xy_m': local[:2].tolist(),
                'tip_aperture_overrun_m': float(point.distance(aperture)),
                'projected_tip_inside_aperture': bool(aperture.covers(point)),
                'axis_error_rad': float(np.arccos(np.clip(rt[:,2]@ro[:,2],-1,1)))})
        self.metrics = {'physics_step': self.contacts.steps, 'tip_pairs': deepcopy(rows),
                        'currently_held': bool(hold),
                        'interpretation': 'all declared leading points in reviewed throat polygons; not whole-prong section fit'}
        if (not raw or any(not r['projected_tip_inside_aperture']
                or r['axis_error_rad'] > self.c['axis_tolerance_rad']
                or r['depth_m'] > self.c['max_depth_m'] for r in rows)):
            self._reset_attempt('physical_interval_invalidated')
            return
        if self.state.get('arm') != raw['resolved_arm']:
            self._reset_attempt('physical_interval_invalidated')
            self.state.update(arm=raw['resolved_arm'], outside=[None]*len(rows))
        for i, row in enumerate(rows):
            if row['depth_m'] <= -self.c['entry_clearance_m']:
                self.state['outside'][i] = deepcopy(row)
        entered = all(self.state['outside']) and all(r['depth_m'] >= 0 for r in rows)
        if entered:
            self._event('entry', tip_pairs=rows, outside_tip_pairs=self.state['outside'])
        contact = self._pair()
        if (hold and entered and contact
                and all(self.c['min_depth_m'] <= r['depth_m'] <= self.c['max_depth_m'] for r in rows)):
            self._emit(held_contact=hold, insertion_contact=contact, tip_pairs=rows,
                       outside_tip_pairs=self.state['outside'])

    def _contact_joint_motion(self):
        adapter = getattr(self.session.env, '_atomic_joint_state', None)
        info, body_path = (adapter(self.c['label'], self.c['joint_name'], self.session.env_idx)
                           if adapter else live_joint_state(self.session.env, self.c['label'],
                                self.c['joint_name'], self.session.env_idx, getattr(self, '_joint_body_path', None)))
        self._joint_body_path = body_path
        position = float(info['position'])
        if not math.isfinite(position):
            raise RuntimeError('nonfinite live joint position')
        hold = self._hold(self.c['label'], self.c['arm'], fingers=1, body_path=body_path)
        raw_hold = self._current_hold(fingers=1)
        if not raw_hold:
            self._diagnose({'moving_link_contact': False, 'sustained_contact': False, 'minimum_travel': None},
                moving_body=body_path, joint_position=position, signed_travel=None,
                unit='joint API units; see calibrated joint type')
            self._reset_attempt('physical_interval_invalidated')
            return
        if self.state.get('arm') != raw_hold['resolved_arm']:
            self.state.update(arm=raw_hold['resolved_arm'], initial=position)
        travel = self.c['direction'] * (position - self.state['initial'])
        self._diagnose({'moving_link_contact': True, 'sustained_contact': bool(hold),
            'minimum_travel': travel >= self.c['min_travel']}, moving_body=body_path,
            joint_position=position, initial_joint_position=self.state['initial'], signed_travel=travel,
            unit='joint API units; see calibrated joint type')
        if hold and travel >= self.c['min_travel']:
            self._emit(moving_link_contact=hold, moving_body=body_path, joint_name=self.c['joint_name'],
                initial_joint_position=self.state['initial'], joint_position=position, signed_travel=travel)

    def _button_joint_state(self):
        from task.atomic.bindings import joint_from_tag
        if not hasattr(self, '_button_joint'):
            self._button_joint = joint_from_tag(self.session.env, self.c['label'], self.c['joint_tag'], self.session.env_idx)
        adapter = getattr(self.session.env, '_atomic_joint_state', None)
        info, body = (adapter(self.c['label'], self._button_joint, self.session.env_idx) if adapter else
            live_joint_state(self.session.env, self.c['label'], self._button_joint, self.session.env_idx,
                             getattr(self, '_joint_body_path', None)))
        self._joint_body_path = body
        position, lower, upper = (float(info[k]) for k in ('position', 'lower', 'upper'))
        if not np.isfinite([position, lower, upper]).all() or upper <= lower:
            raise RuntimeError('button cycle requires finite live position and ordered physical joint limits')
        ratio = (position - lower) / (upper - lower)
        return {'position':position,'lower':lower,'upper':upper},body,ratio

    def _button_press_cycle(self):
        current_joint,body,ratio=self._button_joint_state()
        position,lower,upper=(current_joint[k] for k in ('position','lower','upper'))
        hold = self._hold(self.c['label'], self.c['arm'], fingers=1, body_path=body)
        raw = self._current_hold(fingers=1)
        touching = bool(self._touching())
        previous_unpressed=self.button_unpressed_sample
        self.button_unpressed_sample=({'physics_step':self.contacts.steps,'moving_body':body,
            'joint_ratio':ratio,'joint_state':deepcopy(current_joint),'robot_touching':False}
            if ratio > self.c['initial_ratio'] and not touching else None)
        preceding_unpressed=(previous_unpressed is not None
            and previous_unpressed['physics_step']==self.contacts.steps-1
            and previous_unpressed['moving_body']==body)
        self._diagnose({'moving_link_contact': bool(raw), 'sustained_contact': bool(hold),
            'initial_unpressed': ratio > self.c['initial_ratio'],
            'pressed': ratio < self.c['pressed_ratio'], 'released_position': ratio > self.c['released_ratio'],
            'robot_separated': not touching}, moving_body=body, joint_position=position,
            joint_lower=lower, joint_upper=upper, joint_ratio=ratio, phase=self.state.get('phase', 'unarmed'))
        if self.state.get('phase') == 'pressed':
            # Require complete robot release, not merely loss of the original finger.
            if not touching and ratio > self.c['released_ratio']:
                self._event('release', joint_ratio=ratio, moving_body=body,
                    joint_state=current_joint,robot_touching=False)
                self._emit(press_contact=self.state['press'], joint_name=self._button_joint,
                    moving_body=body, initial_ratio=self.state['initial'],
                    pressed_ratio=self.state['pressed'], released_ratio=ratio,
                    initial_unpressed_sample=self.state['initial_sample'],
                    arming_contact=self.state['arming_contact'],joint_state=current_joint,
                    robot_touching=False)
            return
        if not raw:
            self._reset_attempt('physical_interval_invalidated')
            return
        if self.state.get('arm') != raw['resolved_arm']:
            self._reset_attempt('physical_interval_invalidated')
        if ratio > self.c['initial_ratio'] or (preceding_unpressed and self.state.get('phase') != 'armed'):
            initial_sample=({'physics_step':self.contacts.steps,'moving_body':body,
                'joint_ratio':ratio,'joint_state':deepcopy(current_joint),'robot_touching':touching}
                if ratio > self.c['initial_ratio'] else previous_unpressed)
            self.state.update(phase='armed',arm=raw['resolved_arm'],initial=initial_sample['joint_ratio'],
                initial_sample=deepcopy(initial_sample),arming_contact=deepcopy(raw))
        if hold and self.state.get('phase') == 'armed' and ratio < self.c['pressed_ratio']:
            self.state.update(phase='pressed', press=deepcopy(hold), pressed=ratio)
            self._event('press', moving_link_contact=hold, moving_body=body,
                joint_name=self._button_joint, joint_ratio=ratio,joint_state=current_joint,
                initial_unpressed_sample=self.state['initial_sample'],arming_contact=self.state['arming_contact'])

    def _contact_constrained_twist(self):
        hold, pair = self._hold(self.c['label'], self.c['arm']), self._pair()
        raw_hold = self._current_hold()
        pose, pivot = self._pose(), self.session._resolve(self.c['pivot'])
        local = _rotation(pivot[3:]).T @ (pose[:3] - pivot[:3])
        axis = np.asarray(self.c['axis'], dtype=float)
        axis /= np.linalg.norm(axis)
        depth = -float(local @ axis)
        radius = float(np.linalg.norm(local - (local @ axis) * axis))
        self.metrics = {'physics_step': self.contacts.steps, 'pivot_depth_m': depth, 'pivot_radius_m': radius,
                        'currently_held': bool(hold), 'constraint_contact': bool(pair),
                        'signed_angle_rad': None, 'off_axis_rotation_rad': None}
        if not raw_hold or not pair or radius > self.c['max_radius_m'] or not self.c['min_depth_m'] <= depth <= self.c['max_depth_m']:
            self._reset_attempt('physical_interval_invalidated')
            return
        rotation = _rotation(pivot[3:]).T @ _rotation(pose[3:])
        if self.state.get('arm') != raw_hold['resolved_arm']:
            self._reset_attempt('arm_changed')
            self.state.update(arm=raw_hold['resolved_arm'], rotation=rotation.copy(), angle=0., off_axis=0.)
        delta = rotation @ self.state['rotation'].T
        # Rotation log for substeps below pi. Do not alias ambiguous large jumps.
        theta = float(np.arccos(np.clip((np.trace(delta) - 1) / 2, -1, 1)))
        if theta >= np.pi - 1e-4:
            self._reset_attempt('physical_interval_invalidated')
            return
        vector = np.array([delta[2, 1]-delta[1, 2], delta[0, 2]-delta[2, 0], delta[1, 0]-delta[0, 1]])
        vector *= .5 if theta < 1e-7 else theta / (2 * np.sin(theta))
        signed = float(vector @ axis)
        self.state['off_axis'] += float(np.linalg.norm(vector - signed * axis))
        self.metrics.update(signed_angle_rad=float(self.state['angle']+signed),
                            off_axis_rotation_rad=float(self.state['off_axis']))
        if self.state['off_axis'] > self.c['max_off_axis_rad']:
            self._reset_attempt('physical_interval_invalidated')
            return
        self.state['angle'] += signed
        self.state['rotation'] = rotation.copy()
        from task.atomic.twist_validation import rotation_sample
        history=self.state.setdefault('rotation_samples',[])
        if len(history)<16384:
            history.append(rotation_sample(self.contacts.steps,pose,pivot,raw_hold,pair))
            self.state['last_valid_angles']=(self.state['angle'],self.state['off_axis'])
        else:
            self.state['rotation_history_truncated']=True
        self.metrics.update(signed_angle_rad=float(self.state['angle']),
                            off_axis_rotation_rad=float(self.state['off_axis']))
        if hold and self.c['direction'] * self.state['angle'] >= self.c['min_angle_rad']:
            self._emit(held_contact=hold, constraint_contact=pair, signed_angle_rad=self.state['angle'],
                off_axis_rotation_rad=self.state['off_axis'], radius_m=radius, depth_m=depth,
                rotation_samples=history,rotation_history_truncated=self.state.get('rotation_history_truncated',False))

    def twist_interval(self):
        """Current or retained interrupted net rotation; never an action outcome."""
        if self.kind!='contact_constrained_twist':return None
        history=self.state.get('rotation_samples',[])
        if len(history)<2:return deepcopy(self.best_twist_interval)
        last=history[-1];hold=last['held_contact']
        if hold['consecutive_contact_steps']<self.c['min_contact_steps']:return deepcopy(self.best_twist_interval)
        pose,pivot=np.asarray(last['object_pose']),np.asarray(last['pivot_pose'])
        axis=np.asarray(self.c['axis'],dtype=float);axis/=np.linalg.norm(axis)
        local=_rotation(pivot[3:]).T@(pose[:3]-pivot[:3]);depth=-float(local@axis)
        angle,off_axis=self.state['last_valid_angles']
        interval={'physics_step':last['physics_step'],'attempt_index':self.attempt_index,
            'signed_angle_rad':angle,'off_axis_rotation_rad':off_axis,
            'radius_m':float(np.linalg.norm(local-(local@axis)*axis)),'depth_m':depth,
            'held_contact':deepcopy(hold),'rotation_samples':deepcopy(history),
            'constraint_contact':deepcopy(last['constraint_contact']),
            'rotation_history_truncated':self.state.get('rotation_history_truncated',False)}
        if self.best_twist_interval is not None and self.c['direction']*self.best_twist_interval['signed_angle_rad']>self.c['direction']*angle:
            return deepcopy(self.best_twist_interval)
        return interval

    def _fluid_state(self):
        from task.atomic.materials import material_state
        fluid=material_state(self.session.env,self.c['fluid_label'],'fluid',self.session.env_idx)
        if self.fluid and (set(fluid['ids'].tolist())!=set(self.fluid) or fluid['nominal_mass_kg']!=self.fluid_mass):
            raise RuntimeError('fluid particle identity/population or nominal mass changed during observation')
        masks=[];self.fluid_region_frames={}
        for which in ('source','target'):
            frame=self.session._resolve(self.c[which+'_frame'])
            self.fluid_region_frames[which]=frame.tolist()
            local=(fluid['positions']-frame[:3])@_rotation(frame[3:])
            masks.append(np.all(np.abs(local)<=np.asarray(self.c[which+'_half_extents_m']),axis=1))
        return fluid,*masks

    def _fluid_material_transfer(self):
        hold=self._hold(self.c['label'],self.c['arm'])
        frame=self.session._resolve(self.c['source_frame'])
        tilt=float(np.arccos(np.clip(_rotation(frame[3:])[:,2]@self.source_initial_rotation[:,2],-1,1)))
        fluid,source,target=self._fluid_state()
        mouth_exits = (self._source_mouth_exits(
            {str(i): p for i,p in zip(fluid['ids'], fluid['positions'])}, self.fluid)
            if self.source_exit_observer else {})
        counts={'source_only':int(np.sum(source & ~target)), 'target_only':int(np.sum(target & ~source)),
                'both_interiors':int(np.sum(source & target)), 'outside_both':int(np.sum(~source & ~target)),
                'initially_eligible':sum(m['eligible'] for m in self.fluid.values()),'transferred':0}
        transferred=[]
        for ident,s,t,position in zip(fluid['ids'],source,target,fluid['positions']):
            ident=int(ident);m=self.fluid[ident]
            self._record_source_candidate(ident,m,bool(s),hold,tilt,frame,mouth_exits)
            if s or (self.source_exit_observer and str(ident) in self.source_exit_observer.reentries):
                m.update(exited_while_held_and_tilted=False,target_steps=0)
            elif (m['eligible'] and not m['exited_while_held_and_tilted']
                  and (mouth_exits.get(str(ident), {}).get('result', {}).get('passed') is True
                       if self.source_exit_observer else m['previous_in_source'])
                  and hold and tilt>=self.c['min_tilt_rad']):
                m.update(exited_while_held_and_tilted=True,exit_physics_step=self.contacts.steps,
                         exit_position=position.tolist(),exit_tilt_rad=tilt,
                         exit_contact=deepcopy(hold),exit_source_frame=frame.tolist(),
                         initial_source_frame=self.fluid_initial['region_frames']['source'])
                if self.source_exit_observer:m['source_mouth_crossing']=deepcopy(mouth_exits[str(ident)])
                self._event('source_exit',particle_id=ident,held_contact=hold,tilt_rad=tilt,particle_position=position.tolist())
            if m['eligible'] and m['exited_while_held_and_tilted'] and t and not s:
                m['target_steps']+=1
                self._event('first_transfer',particle_id=ident,position=position.tolist(),source_exit=deepcopy(m))
            else:m['target_steps']=0
            if m['target_steps']>=self.c['settle_steps']:transferred.append(ident)
            m['previous_in_source']=bool(s)
        counts['transferred']=len(transferred)
        masses={key+'_nominal_mass_kg':value*self.fluid_mass for key,value in counts.items()}
        total=counts['source_only']+counts['target_only']+counts['both_interiors']+counts['outside_both']
        self.metrics={'counts':counts,**masses,'total_particle_count':len(self.fluid),
            'partition_count_error':total-len(self.fluid), 'transferred_particle_ids':transferred,
            'containment':'particle centers in explicitly calibrated interior boxes; not whole fluid volumes',
            'outside_semantics':'includes in-flight particles; no connected-component artifact filtering or automatic spill label'}
        if self.source_exit_observer:self.metrics['source_mouth_sampling']=self.source_exit_observer.summary()
        if len(transferred)>=self.c['required_count']:
            self._emit(metrics=self.metrics,particles=deepcopy(self.fluid),initial_state=self.fluid_initial,
                       current_state={'ids':fluid['ids'].tolist(),'positions':fluid['positions'].tolist(),'source':fluid['source']})

    def _material_inside(self, label, which):
        frame = self.session._resolve(self.c[which + '_frame'])
        surfaces = getattr(self.session.env, '_atomic_surfaces', None)
        if surfaces is None:
            raise RuntimeError('rigid material recognition requires live rigid surface geometry')
        geometry = surfaces.resolve(label, self.session.env_idx, self._pose(label))
        vertices = np.asarray(geometry['vertices'], dtype=float)
        if vertices.ndim != 2 or vertices.shape[1] != 3 or not len(vertices) or not np.isfinite(vertices).all():
            raise RuntimeError('material containment needs finite whole-object vertices')
        local = (vertices - frame[:3]) @ _rotation(frame[3:])
        return bool(np.all(np.abs(local) <= np.asarray(self.c[which + '_half_extents_m'])))

    def _rigid_material_transfer(self):
        hold = self._hold(self.c['label'], self.c['arm'])
        frame = self.session._resolve(self.c['source_frame'])
        tilt = float(np.arccos(np.clip(_rotation(frame[3:])[:, 2] @ self.source_initial_rotation[:, 2], -1, 1)))
        mouth_exits = (self._source_mouth_exits({label:self.session._resolve(
            {'kind':'object_center_position','label':label}) for label in self.material}, self.material)
            if self.source_exit_observer else {})
        counts = {'in_source': 0, 'in_target': 0, 'outside_both': 0, 'transferred': 0,
                  'initially_eligible': sum(m['eligible'] for m in self.material.values())}
        for label, m in self.material.items():
            inside_source, inside_target = self._material_inside(label, 'source'), self._material_inside(label, 'target')
            self._record_source_candidate(label,m,inside_source,hold,tilt,frame,mouth_exits)
            counts['in_source'] += int(inside_source)
            counts['in_target'] += int(inside_target)
            counts['outside_both'] += int(not inside_source and not inside_target)
            if inside_source or (self.source_exit_observer and label in self.source_exit_observer.reentries):
                m['exited_while_held_and_tilted'] = False
                m['target_steps'] = 0
            elif m['eligible'] and not m['exited_while_held_and_tilted']:
                if ((mouth_exits.get(label, {}).get('result', {}).get('passed') is True
                     if self.source_exit_observer else m['previous_in_source'])
                        and hold and tilt >= self.c['min_tilt_rad']):
                    m.update(exited_while_held_and_tilted=True, exit_physics_step=self.contacts.steps,
                             exit_contact=deepcopy(hold), exit_tilt_rad=tilt,
                             exit_source_frame=frame.tolist(),initial_source_frame=self.source_initial_frame)
                    if self.source_exit_observer:m['source_mouth_crossing']=deepcopy(mouth_exits[label])
                    self._event('source_exit', material_label=label, held_contact=hold, tilt_rad=tilt)
            if m['eligible'] and m['exited_while_held_and_tilted'] and inside_target and not inside_source:
                m['target_steps'] += 1
                self._event('first_transfer', material_label=label, source_exit=deepcopy(m))
            else:
                m['target_steps'] = 0
            counts['transferred'] += int(m['target_steps'] >= self.c['settle_steps'])
            m['previous_in_source'] = inside_source
        self.metrics = counts
        if self.source_exit_observer:self.metrics['source_mouth_sampling']=self.source_exit_observer.summary()
        if counts['transferred'] >= self.c['required_count']:
            self._emit(counts=counts, materials=self.material,
                       containment='whole rigid mesh in explicitly calibrated convex interior boxes')

    def _record_source_candidate(self, identifier, material, inside_source, hold, tilt, frame, candidates):
        ident=str(identifier)
        if self.source_exit_observer is None or ident not in candidates:return
        reentered=ident in self.source_exit_observer.reentries
        qualifies=bool(material['eligible'] and not inside_source and not reentered
            and not material['exited_while_held_and_tilted']
            and candidates[ident]['result']['passed'] is True and hold and tilt>=self.c['min_tilt_rad'])
        initial=(self.fluid_initial['region_frames']['source'] if self.kind=='fluid_material_transfer'
                 else self.source_initial_frame)
        self.source_exit_observer.annotate_candidate(ident,self.contacts.steps,{
            'context':'source_exit_candidate_qualification',
            'initial_cohort_eligible':bool(material['eligible']),
            'inside_source':bool(inside_source),'reentered_source':reentered,
            'already_qualified_before':bool(material['exited_while_held_and_tilted']),
            'held_contact':deepcopy(hold),'tilt_rad':tilt,
            'source_frame':np.asarray(frame).tolist(),'initial_source_frame':deepcopy(initial),
            'eligible_for_source_exit':qualifies},
            self._pose(identifier) if self.kind=='rigid_material_transfer' else None)

    def _source_mouth_exits(self, positions, provenance):
        if self.source_exit_observer is None:return {}
        opening, source = self.session._resolve_with_source(self.c['source_exit']['opening'])
        return self.source_exit_observer.observe(positions, opening,
            {str(i) for i,m in provenance.items() if m['eligible']}, self.contacts.steps,
            self.session.env.dt, self.session._action_index(), source, self.material_bounds)


def live_joint_state(env, label, joint_name, env_idx, resolved_body_path=None):
    """Read the articulation DOF and resolve its actual USD moving rigid body."""
    lm = env.scene_manager.layout_manager
    name = lm.get_instance_name(env_idx=env_idx, label=label)
    obj = lm.get_scene_object(env_idx=env_idx, inst_name=name)
    root = getattr(obj, 'usd_prim_path', None) or getattr(obj, 'prim_path', None)
    if not root or not hasattr(obj, 'get_joint_info'):
        raise RuntimeError(f'{label} does not expose a live articulation joint')
    if resolved_body_path:
        if not resolved_body_path.startswith(root + '/'):
            raise RuntimeError('cached joint body no longer belongs to this articulation')
        return obj.get_joint_info(joint_name), resolved_body_path
    import omni.usd
    from pxr import Usd, UsdPhysics
    stage = omni.usd.get_context().get_stage()
    matches = [p for p in Usd.PrimRange(stage.GetPrimAtPath(root), Usd.TraverseInstanceProxies())
               if p.IsA(UsdPhysics.Joint) and p.GetName() == joint_name]
    if len(matches) != 1:
        raise RuntimeError(f'joint {joint_name} must resolve uniquely under {root}')
    bodies = UsdPhysics.Joint(matches[0]).GetBody1Rel().GetTargets()
    if len(bodies) != 1 or not str(bodies[0]).startswith(root + '/'):
        raise RuntimeError('joint moving body must belong to the selected articulation')
    return obj.get_joint_info(joint_name), str(bodies[0])
