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


SCHEMAS = {
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
    'contact_joint_motion': ('actuate', {'label', 'arm', 'min_contact_steps', 'joint_name',
        'min_travel', 'direction'}),
    'contact_constrained_twist': ('twist', {'label', 'arm', 'min_contact_steps', 'target_label',
        'pivot', 'axis', 'direction', 'min_angle_rad', 'max_off_axis_rad', 'max_radius_m',
        'min_depth_m', 'max_depth_m'}),
    'rigid_material_transfer': ('pour', {'label', 'arm', 'min_contact_steps', 'target_label',
        'source_frame', 'target_frame', 'source_half_extents_m', 'target_half_extents_m',
        'material_labels', 'required_count', 'min_tilt_rad', 'settle_steps'}),
}

TRANSITIONS = {
    'supported_release': {'release', 'settled'}, 'held_tool_push': {'stroke'},
    'held_tool_contact': {'contact'}, 'grip_transfer': {'giver_hold', 'overlap', 'receiver_only'},
    'held_insertion': {'entry', 'inserted'}, 'contact_joint_motion': {'motion'},
    'contact_constrained_twist': {'rotation'},
    'rigid_material_transfer': {'source_exit', 'first_transfer', 'transfer_complete'},
}
COMPLETION = {'supported_release': 'settled', 'held_tool_push': 'stroke', 'held_tool_contact': 'contact',
              'grip_transfer': 'receiver_only', 'held_insertion': 'inserted',
              'contact_joint_motion': 'motion', 'contact_constrained_twist': 'rotation'}
COMPLETION['rigid_material_transfer'] = 'transfer_complete'


def validate_recognition(config, family, validate_selector):
    kind = config.get('kind')
    if kind not in SCHEMAS or SCHEMAS[kind][0] != family:
        raise ValueError(f'unsupported physical recognizer {kind!r} for {family}')
    fields = SCHEMAS[kind][1] | {'kind'}
    if set(config) != fields:
        raise ValueError(f'{kind} requires exactly {sorted(fields)}')
    for key in fields & {'label', 'arm', 'giver_arm', 'receiver_arm', 'target_label', 'joint_name'}:
        if not isinstance(config[key], str) or not config[key]:
            raise ValueError(f'{kind}.{key} must be a nonempty name')
    for key in fields & {'min_contact_steps', 'settle_steps', 'overlap_steps', 'receiver_steps'}:
        if type(config[key]) is not int or config[key] < 2:
            raise ValueError(f'{kind}.{key} must be at least two distinct physics steps')
    numeric = fields - {'kind', 'label', 'arm', 'giver_arm', 'receiver_arm', 'target_label',
        'joint_name', 'support_labels', 'tip', 'opening', 'pivot', 'axis', 'direction',
        'tool_contact_suffix', 'target_contact_suffix', 'min_contact_steps', 'settle_steps',
        'overlap_steps', 'receiver_steps', 'source_frame', 'target_frame', 'source_half_extents_m',
        'target_half_extents_m', 'material_labels', 'required_count'}
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
    if kind == 'grip_transfer':
        if config['giver_arm'] == config['receiver_arm'] or {config['giver_arm'], config['receiver_arm']} & {'any', 'nearest'}:
            raise ValueError('handover requires two distinct explicit arms')
    for key in fields & {'tip', 'opening', 'pivot', 'source_frame', 'target_frame'}:
        validate_selector(config[key], key)
        if config[key]['kind'] not in ('functional_point', 'support_point', 'object_pose', 'object_center_pose') or config[key].get('time', 'live') != 'live':
            raise ValueError(f'{key} must select a live oriented object landmark')
        expected_label = config['label'] if key in ('tip', 'source_frame') else config['target_label']
        if config[key]['label'] != expected_label:
            raise ValueError(f'{key} must belong to {expected_label}')
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
        self.events = {}
        self.material = {}
        lm = session.env.scene_manager.layout_manager
        if hasattr(lm, 'instance_type_by_env'):
            expected = 'Articulation' if self.kind == 'contact_joint_motion' else 'Rigid'
            name = lm.get_instance_name(env_idx=session.env_idx, label=self.c['label'])
            actual = lm.instance_type_by_env[session.env_idx].get(name)
            if actual != expected:
                raise RuntimeError(f'{self.kind} expects a {expected} object; {self.c["label"]} is {actual}')
        if self.kind == 'rigid_material_transfer':
            if hasattr(lm, 'instance_type_by_env'):
                for label in self.c['material_labels']:
                    name = lm.get_instance_name(env_idx=session.env_idx, label=label)
                    if lm.instance_type_by_env[session.env_idx].get(name) != 'Rigid':
                        raise RuntimeError('rigid material recognition cannot use fluid/cloth/cached articulated geometry')
            self.source_initial_rotation = _rotation(self.session._resolve(self.c['source_frame'])[3:])
            for label in self.c['material_labels']:
                source = self._material_inside(label, 'source')
                target = self._material_inside(label, 'target')
                self.material[label] = {'initial_in_source': source, 'initial_in_target': target,
                    'eligible': source and not target, 'previous_in_source': source,
                    'exited_while_held_and_tilted': False, 'target_steps': 0}

    def _hold(self, label, arm, fingers=2, body_path=None):
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
            _, source = self.contacts.resolve_object_pair({'label': self.c['label'],
                'other_label': self.c['target_label']}, self.session.env_idx)
            return source
        except ContactUnavailable:
            return None

    def _pose(self, label=None):
        return self.session._object_pose(label or self.c['label'])

    def _emit(self, **values):
        self.ready = True
        self.evidence = {'kind': self.kind, 'physics_step': self.contacts.steps,
            'policy_action_index': self.session._action_index(), **deepcopy(values)}
        self._event(COMPLETION[self.kind], **values)

    def _event(self, name, **values):
        if name not in self.events:
            self.events[name] = {'name': name, 'physics_step': self.contacts.steps,
                'policy_action_index': self.session._action_index(), **deepcopy(values)}

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
            self.state.clear()
            self.holds.clear()
            self.current_contacts.clear()
            for label, m in self.material.items():
                m.update(exited_while_held_and_tilted=False, target_steps=0,
                         previous_in_source=self._material_inside(label, 'source'))
        self.last_step, self.ready = step, False
        getattr(self, '_' + self.kind)()

    def _supported_release(self):
        pose = self._pose()
        hold = self._hold(self.c['label'], self.c['arm'])
        raw_hold = self._current_hold()
        touch = self._touching()
        if touch:
            self.state.pop('settling', None)
            if raw_hold:
                arm = raw_hold['resolved_arm']
                if self.state.get('arm') != arm:
                    self.state.update(arm=arm, anchor=pose.copy(), transported=False)
                moved = np.linalg.norm(pose[:3] - self.state['anchor'][:3])
                if hold and moved >= self.c['transport_threshold_m']:
                    self.state.update(transported=True, hold=deepcopy(hold), transport_m=float(moved))
            else:
                # A one-finger push is not a prior grasp; require sustained hold again.
                self.state.clear()
            return
        if not self.state.get('transported'):
            self.state.clear()
            return
        self._event('release', held_contact=self.state['hold'], pose=pose.tolist())
        support = self.contacts.support_evidence(self.c['label'], self.c['support_labels'], self.session.env_idx)
        old = self.state.get('settling')
        if not support['contacts']:
            self.state.pop('settling', None)
            return
        stable = (old is not None and np.linalg.norm(pose[:3] - old[0][:3]) <= self.c['max_position_step_m']
                  and _angular_error(pose[3:], old[0][3:]) <= self.c['max_angle_step_rad']
                  and np.linalg.norm(pose[:3] - old[2][:3]) <= self.c['max_settle_displacement_m']
                  and _angular_error(pose[3:], old[2][3:]) <= self.c['max_settle_angle_rad'])
        count = old[1] + 1 if stable else 1
        anchor = old[2] if stable else pose.copy()
        self.state['settling'] = (pose.copy(), count, anchor)
        if count >= self.c['settle_steps']:
            self._emit(held_contact=self.state['hold'], released=True, stable_steps=count,
                transport_m=self.state['transport_m'], support=support, pose=pose.tolist(),
                settle_displacement_m=float(np.linalg.norm(pose[:3] - anchor[:3])),
                settle_angle_rad=_angular_error(pose[3:], anchor[3:]))

    def _held_tool_push(self):
        hold = self._hold(self.c['label'], self.c['arm'])
        raw_hold = self._current_hold()
        pair = self._pair()
        support = self.contacts.support_evidence(self.c['target_label'], self.c['support_labels'], self.session.env_idx)
        if not raw_hold or not pair or not support['contacts']:
            self.state.clear()
            return
        tool, target = self._pose(), self._pose(self.c['target_label'])
        if self.state.get('arm') != raw_hold['resolved_arm']:
            self.state.update(arm=raw_hold['resolved_arm'], tool=tool.copy(), target=target.copy(), count=0)
        self.state['count'] += 1
        dt, do = tool[:3] - self.state['tool'][:3], target[:3] - self.state['target'][:3]
        if abs(do[2]) > self.c['max_vertical_motion_m']:
            self.state.clear()
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
            self.state['clear'] = True
            return
        # First force-bearing encounter after separation, not sustained resting contact.
        clear = self.state.pop('clear', False)
        if not clear or not hold:
            return
        roots = pair['object_roots']
        wanted = [roots[0] + '/' + self.c['tool_contact_suffix'],
                  roots[1] + '/' + self.c['target_contact_suffix']]
        def match(row, i, path):
            return any(p == path or p.startswith(path + '/') for p in (row[f'actor{i}'], row[f'collider{i}']))
        rows = [r for r in pair['contacts'] if any(match(r, i, wanted[0]) and match(r, 1-i, wanted[1]) for i in (0, 1))]
        impulse = sum(float(np.linalg.norm(r['impulse'])) for r in rows)
        if rows and impulse >= self.c['min_impulse_ns']:
            self._emit(held_contact=hold, tool_target_contacts=rows, total_impulse_ns=impulse)

    def _grip_transfer(self):
        pose = self._pose()
        old = self.state.get('pose')
        if old is not None and np.linalg.norm(pose[:3] - old[:3]) > self.c['max_position_step_m']:
            self.state.clear()
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
                self.state.clear()
            elif receiver:
                self.state['overlap'] += 1
                if self.state['overlap'] >= self.c['overlap_steps']:
                    self.state.update(phase='release', receiver=deepcopy(receiver), released_steps=0)
                    self._event('overlap', giver_contact=giver, receiver_contact=receiver)
            else:
                self.state['overlap'] = 0
        elif phase == 'release':
            if not receiver:
                self.state.clear()
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
        if not raw_hold or lateral > self.c['lateral_tolerance_m'] or angle > self.c['axis_tolerance_rad']:
            self.state.clear()
            return
        if self.state.get('arm') != raw_hold['resolved_arm']:
            self.state.clear()
        if depth > self.c['max_depth_m'] or depth < self.state.get('last_depth', depth) - 1e-6:
            self.state.clear()
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
            self.state.clear()
            return
        if self.state.get('arm') != raw_hold['resolved_arm']:
            self.state.update(arm=raw_hold['resolved_arm'], initial=position)
        travel = self.c['direction'] * (position - self.state['initial'])
        if hold and travel >= self.c['min_travel']:
            self._emit(moving_link_contact=hold, moving_body=body_path, joint_name=self.c['joint_name'],
                initial_joint_position=self.state['initial'], joint_position=position, signed_travel=travel)

    def _contact_constrained_twist(self):
        hold, pair = self._hold(self.c['label'], self.c['arm']), self._pair()
        raw_hold = self._current_hold()
        pose, pivot = self._pose(), self.session._resolve(self.c['pivot'])
        local = _rotation(pivot[3:]).T @ (pose[:3] - pivot[:3])
        axis = np.asarray(self.c['axis'], dtype=float)
        axis /= np.linalg.norm(axis)
        depth = -float(local @ axis)
        radius = float(np.linalg.norm(local - (local @ axis) * axis))
        if not raw_hold or not pair or radius > self.c['max_radius_m'] or not self.c['min_depth_m'] <= depth <= self.c['max_depth_m']:
            self.state.clear()
            return
        rotation = _rotation(pivot[3:]).T @ _rotation(pose[3:])
        if self.state.get('arm') != raw_hold['resolved_arm']:
            self.state.update(arm=raw_hold['resolved_arm'], rotation=rotation.copy(), angle=0., off_axis=0.)
        delta = rotation @ self.state['rotation'].T
        # Rotation log for substeps below pi. Do not alias ambiguous large jumps.
        theta = float(np.arccos(np.clip((np.trace(delta) - 1) / 2, -1, 1)))
        if theta >= np.pi - 1e-4:
            self.state.clear()
            return
        vector = np.array([delta[2, 1]-delta[1, 2], delta[0, 2]-delta[2, 0], delta[1, 0]-delta[0, 1]])
        vector *= .5 if theta < 1e-7 else theta / (2 * np.sin(theta))
        signed = float(vector @ axis)
        self.state['off_axis'] += float(np.linalg.norm(vector - signed * axis))
        if self.state['off_axis'] > self.c['max_off_axis_rad']:
            self.state.clear()
            return
        self.state['angle'] += signed
        self.state['rotation'] = rotation.copy()
        if hold and self.c['direction'] * self.state['angle'] >= self.c['min_angle_rad']:
            self._emit(held_contact=hold, constraint_contact=pair, signed_angle_rad=self.state['angle'],
                off_axis_rotation_rad=self.state['off_axis'], radius_m=radius, depth_m=depth)

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
        counts = {'in_source': 0, 'in_target': 0, 'outside_both': 0, 'transferred': 0,
                  'initially_eligible': sum(m['eligible'] for m in self.material.values())}
        for label, m in self.material.items():
            inside_source, inside_target = self._material_inside(label, 'source'), self._material_inside(label, 'target')
            counts['in_source'] += int(inside_source)
            counts['in_target'] += int(inside_target)
            counts['outside_both'] += int(not inside_source and not inside_target)
            if inside_source:
                m['exited_while_held_and_tilted'] = False
                m['target_steps'] = 0
            elif m['eligible'] and not m['exited_while_held_and_tilted']:
                if m['previous_in_source'] and hold and tilt >= self.c['min_tilt_rad']:
                    m.update(exited_while_held_and_tilted=True, exit_physics_step=self.contacts.steps,
                             exit_contact=deepcopy(hold), exit_tilt_rad=tilt)
                    self._event('source_exit', material_label=label, held_contact=hold, tilt_rad=tilt)
            if m['eligible'] and m['exited_while_held_and_tilted'] and inside_target and not inside_source:
                m['target_steps'] += 1
                self._event('first_transfer', material_label=label, source_exit=deepcopy(m))
            else:
                m['target_steps'] = 0
            counts['transferred'] += int(m['target_steps'] >= self.c['settle_steps'])
            m['previous_in_source'] = inside_source
        self.metrics = counts
        if counts['transferred'] >= self.c['required_count']:
            self._emit(counts=counts, materials=self.material,
                       containment='whole rigid mesh in explicitly calibrated convex interior boxes')


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
