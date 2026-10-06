"""Live, event-based evaluation of a single atomic stage in RoboDojo."""

from copy import deepcopy
import json

import numpy as np

from task.atomic.geometry import evaluate_geometry, GeometryUnavailable
from task.atomic.contacts import ContactUnavailable


def _state(value):
    return deepcopy(value) if isinstance(value, dict) else value.tolist()


def _array(value):
    if hasattr(value, "detach"):
        value = value.detach().cpu().numpy()
    return np.asarray(value, dtype=float).reshape(-1)


class AtomicSession:
    def __init__(self, env, stage, env_idx):
        self.env = env
        self.stage = stage
        self.env_idx = env_idx
        self.success = False
        self.results = {}
        self.closest_approach = {}
        self.measurement_failures = {}
        self.interaction_observed = False
        self.interaction_evidence = None
        self.goal_success = False
        self.current_hold_observed = False
        self.maintained_hold_failures = []
        self._maintained_hold_step = None
        self._recognition_last_step = None
        self._recognition_arm = None
        self._recognition_anchor = None
        self._recognition_contact_steps = 0
        self._recognition_current_displacement = np.zeros(3)
        self._held_lift_required = max([float(check['args']['z_threshold']) for check in stage.success_checks
                                       if stage.family == 'pick' and check['name'] == 'is_lift']
                                      + ([stage.recognition['motion_threshold_m']]
                                         if stage.family == 'pick' and stage.recognition else [0.]))
        self._physical_recognizer = None
        if stage.recognition and stage.recognition['kind'] != 'finger_contact_motion':
            from task.atomic.recognizers import PhysicalRecognizer
            self._physical_recognizer = PhysicalRecognizer(self)
        self._frozen_references = {}
        self._frozen_surfaces = {}
        self._event_evidence = {}
        self._precontact_samples = {}
        self._precontact_consumed = set()
        self.sample_index = 0
        self.finalized = False
        self._finalizing = False
        self.finalization_evidence = None
        self.initial_positions = {}
        if stage.recognition is not None:
            label = stage.recognition['label']
            self.initial_positions[label] = self._object_pose(label)[:3].copy()
        for check in stage.success_checks:
            if check['name'] == 'is_atomic_rise_since_activation':
                label = check['args']['label']
                self.initial_positions[label] = self._object_pose(label)[:3].copy()
        definitions = list(stage.geometry) + list(stage.trajectories)
        if stage.selection:
            definitions += stage.selection['conditions']
        for condition in definitions:
            event = condition.get("event", {"kind": "stage_success"})
            if event["kind"] in ("first_lift", "first_motion"):
                label = event["label"]
                self.initial_positions[label] = self._object_pose(label)[:3].copy()
            reference = condition.get('reference')
            if reference and reference.get('time') == 'stage_start':
                key = self._selector_key(reference)
                if key not in self._frozen_references:
                    live_selector = {**reference, 'time': 'live'}
                    value, source = self._resolve_with_source(live_selector)
                    source.update(time='stage_start', captured_policy_action_index=self._action_index())
                    root_pose = (self._object_pose(reference['label']).copy()
                                 if reference['kind'] in ('object_pose', 'object_center_pose') else None)
                    self._frozen_references[key] = (deepcopy(value), deepcopy(source), root_pose)
                if condition.get('relation_scope')=='objects' and key not in self._frozen_surfaces:
                    self._frozen_surfaces[key]=deepcopy(self._surface_for_selector({**reference,'time':'live'}))
        self._trajectory_observer = self._selection_observer = None
        if stage.trajectories:
            from task.atomic.trajectory import TrajectoryObserver
            self._trajectory_observer = TrajectoryObserver(self)
        if stage.selection:
            from task.atomic.selection import SelectionObserver
            self._selection_observer = SelectionObserver(self)

    def _action_index(self):
        return int(self.env.take_action_cnt[self.env_idx]) if hasattr(self.env, 'take_action_cnt') else None

    @staticmethod
    def _selector_key(selector):
        return json.dumps(selector, sort_keys=True, separators=(',', ':'))

    def _object_pose(self, label):
        position, orientation = self.env.scene_manager.layout_manager.get_instance_pose(
            env_idx=self.env_idx, label=label
        )
        if position is None or orientation is None:
            raise ValueError(f"object label {label!r} is unavailable in env {self.env_idx}")
        return np.concatenate((_array(position), _array(orientation)))

    def _resolve(self, selector):
        return self._resolve_with_source(selector)[0]

    def _resolve_with_source(self, selector):
        if selector.get('time') == 'stage_start':
            value, source, _ = self._frozen_references[self._selector_key(selector)]
            return deepcopy(value), deepcopy(source)
        source = {**selector, "frame": "environment_local_world"}
        kind = selector["kind"]
        if 'asset_model' in selector:
            metadata=self.env.scene_manager.layout_manager.get_instance_metadata(env_idx=self.env_idx,label=selector['label'])
            model=selector['asset_model']
            if metadata.get('model_name')!=model['name'] or int(metadata.get('model_id',-1))!=model['index']:
                raise RuntimeError('calibrated frame/mesh model differs from the reviewed asset')
            source['verified_asset_model']=dict(model)
        if 'asset_uuid' in selector:
            metadata=self.env.scene_manager.layout_manager.get_instance_metadata(env_idx=self.env_idx,label=selector['label'])
            if metadata.get('uuid') != selector['asset_uuid']:
                raise RuntimeError('calibrated frame/mesh asset identity differs from the reviewed asset')
            source['verified_asset_uuid']=metadata['uuid']
        if kind in ('cloth_points','cloth_landmark','cloth_patch_frame','cloth_patch_surface','cloth_tag_frame','cloth_line_frame','fluid_points'):
            from task.atomic.materials import resolve_material
            return resolve_material(self.env,selector,self.env_idx)
        if kind == 'calibrated_frame':
            lm = self.env.scene_manager.layout_manager
            name = lm.get_instance_name(env_idx=self.env_idx,label=selector['label'])
            if str(lm.instance_type_by_env[self.env_idx].get(name)).lower() not in ('rigid','geometry'):
                raise RuntimeError('calibrated root-local frame requires a rigid/static object, not a moving link or material proxy')
            root = self._object_pose(selector['label']); local = np.asarray(selector['local_pose'])
            from task.atomic.geometry import _rotation
            from task.atomic.landmarks import matrix_quaternion
            value = np.concatenate((root[:3]+_rotation(root[3:])@local[:3],
                matrix_quaternion(_rotation(root[3:])@_rotation(local[3:]))))
            return value, {**source,'root_pose':root.tolist(),
                'calibration_semantics':'explicit reviewed offset in scaled object-root metres; no automatic mouth/tip inference'}
        if kind in ('articulated_link_pose', 'joint_link_pose'):
            from task.atomic.landmarks import live_link_pose
            link = selector.get('link')
            if kind == 'joint_link_pose':
                from task.atomic.bindings import joint_from_tag
                from task.atomic.recognizers import live_joint_state
                joint = joint_from_tag(self.env, selector['label'], selector['joint_tag'], self.env_idx)
                _, path = live_joint_state(self.env, selector['label'], joint, self.env_idx)
                link = path.rsplit('/', 1)[-1]
            value, physical = live_link_pose(self.env, selector['label'], link, self.env_idx)
            return value, {**source, **physical}
        if kind in ("object_pose", "object_position"):
            pose = self._object_pose(selector["label"])
            source['landmark'] = 'object root frame origin, not geometric centre'
            return (pose if kind == "object_pose" else pose[:3]), source
        if kind in ('object_center_pose', 'object_center_position'):
            pose = self.env._atomic_surfaces.center_pose(selector['label'], self.env_idx,
                                                       self._object_pose(selector['label']))
            source['landmark'] = 'centre of live surface bounds in object-root axes; articulated child meshes follow PhysX link poses'
            return (pose if kind == 'object_center_pose' else pose[:3]), source
        if kind == 'contact_points':
            contacts = getattr(self.env, '_atomic_contacts', None)
            if contacts is None:
                raise RuntimeError('PhysX contacts were not initialized')
            return contacts.resolve(selector, self.env_idx)
        if kind == 'object_contact_points':
            contacts = getattr(self.env, '_atomic_contacts', None)
            if contacts is None:
                raise RuntimeError('PhysX contacts were not initialized')
            return contacts.resolve_object_pair(selector, self.env_idx)
        if kind == "robot_ee_pose":
            if selector['arm'] == 'contacting':
                contacts = self.env._atomic_contacts
                _, evidence = contacts.resolve({'kind': 'contact_points', 'label': selector['label'],
                    'arm': 'any', 'min_finger_bodies': selector.get('min_finger_bodies', 2)}, self.env_idx)
                robot = next((r for r in self.env.robot_manager.robot_list if r.arm_name == evidence['resolved_arm']), None)
                source['arm_contact_evidence'] = deepcopy(evidence)
            elif selector["arm"] == "nearest":
                target = self._object_pose(selector["label"])[:3]
                candidates = [r for r in self.env.robot_manager.robot_list if r.type == "target"]
                if not candidates:
                    raise ValueError("no target robot arm is available")
                robot = min(
                    candidates,
                    key=lambda r: np.linalg.norm(
                        _array(self.env.robot_manager.get_real_endpose(
                            r, env_idx_list=[self.env_idx], is_relative=True
                        )[self.env_idx])[:3] - target
                    ),
                )
            else:
                robot = next((r for r in self.env.robot_manager.robot_list if r.arm_name == selector["arm"]), None)
            if robot is None:
                raise ValueError(f"unknown robot arm {selector['arm']!r}")
            poses = self.env.robot_manager.get_real_endpose(robot, env_idx_list=[self.env_idx], is_relative=True)
            source.update({"resolved_arm": robot.arm_name,
                           "ee_link_name": getattr(robot, "ee_link_name", None)})
            return _array(poses[self.env_idx]), source
        if kind in ('functional_point', 'support_point'):
            lm = self.env.scene_manager.layout_manager
            inst_name = lm.get_instance_name(env_idx=self.env_idx, label=selector["label"])
            if inst_name is None:
                raise ValueError(f"unknown object label {selector['label']!r}")
            metadata = lm.get_instance_metadata(inst_name=inst_name, env_idx=self.env_idx)
            category = 'functional' if kind == 'functional_point' else 'support'
            item = metadata.get(selector.get('type', 'active'), {}).get(category, {}).get(selector['tag'], {})
            if item.get('base_link'):
                from task.atomic.landmarks import live_link_pose
                from task.atomic.geometry import _rotation
                link, link_source = live_link_pose(self.env, selector['label'], item['base_link'], self.env_idx)
                points = item.get('frame' if kind == 'functional_point' else 'center', [])
                index = selector.get('index', 0)
                if not points or index >= len(points):
                    raise ValueError(f'link landmark {selector["tag"]} is unavailable')
                local = _array(points[index])
                if local.shape != (7,) or not np.isfinite(local).all():
                    raise RuntimeError('articulated landmark annotation must be a finite pose')
                rotation = _rotation(link[3:]) @ _rotation(local[3:])
                from task.atomic.landmarks import matrix_quaternion
                value = np.concatenate((link[:3] + _rotation(link[3:]) @ local[:3], matrix_quaternion(rotation)))
                return value, {**source, 'live_link':link_source}
            resolver = lm.get_functional_points if kind == 'functional_point' else lm.get_support_points
            points = resolver(
                tag=selector["tag"], type=selector.get("type", "active"),
                config=lm.get_instance_metadata(inst_name=inst_name, env_idx=self.env_idx),
                ret="list", obj_name=inst_name, env_idx=self.env_idx,
            )
            if kind == 'support_point':
                points, radii = points
                source['support_radii_m'] = list(radii)
            index = int(selector.get("index", 0))
            if not points or index >= len(points):
                raise ValueError(f"functional point {selector['tag']!r} is unavailable")
            return _array(points[index]), source
        raise ValueError(f"unknown measurement kind {kind!r}")

    def _check_success(self):
        for check in self.stage.success_checks:
            if not self._predicate(check):
                return False
        return True

    def _observe_interaction(self):
        """Track a contact-held motion interval independently of geometry.

        Repeated action-boundary calls cannot count the same physics sample
        twice. Contact loss/arm changes reset the interval. Contacts acquired
        after ballistic motion cannot take credit for that earlier motion.
        """
        if self.stage.maintained_holds:
            contacts = getattr(self.env, '_atomic_contacts', None)
            if contacts is None:
                raise RuntimeError('maintained holds require initialized PhysX contacts')
            if contacts.steps != self._maintained_hold_step:
                # A skipped sample cannot certify a continuous constraint.
                if self._maintained_hold_step is not None and contacts.steps != self._maintained_hold_step + 1:
                    self.maintained_hold_failures.append({'physics_step': contacts.steps, 'reason': 'sampling_gap'})
                self._maintained_hold_step = contacts.steps
                for hold in self.stage.maintained_holds:
                    try:
                        contacts.resolve({'kind': 'contact_points', **hold}, self.env_idx)
                    except ContactUnavailable as error:
                        failure = {'hold': deepcopy(hold), 'physics_step': contacts.steps, 'reason': str(error)}
                        if not any(f.get('hold') == hold for f in self.maintained_hold_failures):
                            self.maintained_hold_failures.append(failure)
        recognition = self.stage.recognition
        if recognition is None:
            return
        if self._physical_recognizer is not None:
            self._physical_recognizer.observe()
            self.interaction_observed = self.interaction_observed or self._physical_recognizer.ready
            if self._physical_recognizer.ready:
                self.interaction_evidence = deepcopy(self._physical_recognizer.evidence)
            return
        contacts = getattr(self.env, '_atomic_contacts', None)
        if contacts is None:
            raise RuntimeError('physical action recognition requires initialized PhysX contacts')
        physics_step = contacts.steps
        if physics_step == self._recognition_last_step:
            return
        contiguous = self._recognition_last_step is not None and physics_step == self._recognition_last_step + 1
        self._recognition_last_step = physics_step
        selector = {'kind': 'contact_points', 'label': recognition['label'], 'arm': recognition['arm'],
                    'min_finger_bodies': 2 if self.stage.family == 'pick' else 1}
        try:
            measured, source = contacts.resolve(selector, self.env_idx)
            support = (contacts.support_evidence(recognition['label'], recognition['support_labels'], self.env_idx)
                       if self.stage.family == 'push' else None)
            if self.stage.family == 'push' and not support['contacts']:
                raise ContactUnavailable('push has no upward force-bearing named support at this physics step')
        except ContactUnavailable:
            self.current_hold_observed = False
            self._recognition_arm = self._recognition_anchor = None
            self._recognition_contact_steps = 0
            self._recognition_current_displacement = np.zeros(3)
            return
        current = self._object_pose(recognition['label'])[:3].copy()
        arm = source['resolved_arm']
        if not contiguous or arm != self._recognition_arm:
            self._recognition_anchor = current.copy()
            self._recognition_contact_steps = 1
            self._recognition_start_source = deepcopy(source)
        else:
            self._recognition_contact_steps += 1
        self._recognition_arm = arm
        self.current_hold_observed = self._recognition_contact_steps >= recognition['min_contact_steps']
        displacement = current - self._recognition_anchor
        self._recognition_current_displacement = displacement.copy()
        motion = float(displacement[2] if self.stage.family == 'pick' else np.linalg.norm(displacement[:2]))
        if self.current_hold_observed and motion >= recognition['motion_threshold_m']:
            self.interaction_observed = True
            self.interaction_evidence = {
                'kind': recognition['kind'], 'object': recognition['label'], 'arm': arm,
                'contact_start_position': self._recognition_anchor.tolist(), 'position': current.tolist(),
                'displacement_m': displacement.tolist(), 'motion_m': motion,
                'consecutive_contact_steps': self._recognition_contact_steps,
                'required_held_lift_m': self._held_lift_required if self.stage.family == 'pick' else None,
                'support_evidence': deepcopy(support),
                'first_contact_source': deepcopy(self._recognition_start_source),
                'contact_source': deepcopy(source), 'measured_contacts': deepcopy(measured),
                'physics_step': physics_step, 'policy_action_index': self._action_index(),
            }

    def _predicate(self, check):
        if check['name'] == 'is_atomic_rise_since_activation':
            args = check['args']
            return self._object_pose(args['label'])[2] - self.initial_positions[args['label']][2] >= args['threshold_m']
        if check['name'] == 'is_atomic_interaction':
            return bool(self._physical_recognizer and self._physical_recognizer.ready)
        if check['name'] in ('is_atomic_entry', 'is_atomic_inserted'):
            from task.atomic.geometry import _rotation
            args = check['args']
            tip = self._resolve({'kind': 'functional_point', 'label': args['label_A'],
                                 'tag': args.get('tip_tag', 'insert'), 'type': 'active'})
            lm = self.env.scene_manager.layout_manager
            metadata = lm.get_instance_metadata(env_idx=self.env_idx, label=args['label_B'])
            for tag in metadata.get('passive', {}).get('support', {}):
                if not tag.startswith('socket/'):
                    continue
                target = self._resolve({'kind': 'support_point', 'label': args['label_B'], 'tag': tag,
                                        'type': 'passive', 'index': 0})
                local = _rotation(target[3:]).T @ (tip[:3] - target[:3])
                angle = np.arccos(np.clip((_rotation(tip[3:])[:, 2] @ _rotation(target[3:])[:, 2]), -1, 1))
                depth = -local[2]
                if (np.linalg.norm(local[:2]) <= args.get('xy_tolerance', 0.012)
                        and args.get('min_depth', 0.0) <= depth <= args.get('max_depth', 0.025)
                        and angle <= np.deg2rad(args.get('angle_tolerance_deg', 30))):
                    return True
            return False
        return self.env.reward_manager.call_func_parser((check['name'], deepcopy(check['args'])), self.env_idx) >= 1

    def _event_fired(self, event, success_now):
        kind = event["kind"]
        if kind == 'attempt_end':
            if self._finalizing:
                self._event_evidence[self._selector_key(event)] = deepcopy(self.finalization_evidence)
            return self._finalizing
        if kind == "stage_success":
            return success_now
        if kind == 'recognition_event':
            recognizer = self._physical_recognizer
            evidence = recognizer.events.get(event['name']) if recognizer else None
            if not evidence or evidence['physics_step'] != recognizer.contacts.steps:
                return False
            self._event_evidence[self._selector_key(event)] = deepcopy(evidence)
            return True
        if kind == "first_predicate":
            values = (
                self._predicate(check)
                for check in event["checks"]
            )
            return all(values) if event.get("mode", "any") == "all" else any(values)
        if kind == 'first_contact':
            try:
                measured, source = self._resolve_with_source(event['measurement'])
            except ContactUnavailable:
                return False
            self._event_evidence[self._selector_key(event)] = {
                'measured_contacts': _state(measured), 'contact_source': deepcopy(source)}
            return True
        label = event["label"]
        current = self._object_pose(label)[:3]
        initial = self.initial_positions[label]
        threshold = float(event.get("threshold", 0.01))
        if threshold <= 0:
            raise ValueError("event threshold must be positive")
        if kind == "first_lift":
            return current[2] - initial[2] >= threshold
        if kind == "first_motion":
            return np.linalg.norm(current - initial) >= threshold
        raise ValueError(f"unknown event kind {kind!r}")

    def _sample(self, success_now):
        self.sample_index += 1
        for condition in self.stage.geometry:
            condition_id = condition["id"]
            if condition_id in self.results or condition_id in self.measurement_failures:
                continue
            event = condition.get("event", {"kind": "stage_success"})
            if self._finalizing != (event['kind'] == 'attempt_end'):
                continue
            before = event['kind'] == 'before_contact'
            historic = self._before_contact(condition) if before else None
            if before:
                if historic is None:
                    continue
            elif not self._event_fired(event, success_now):
                continue
            try:
                measured, measurement_source, reference, reference_source = (historic['states'] if before else self._resolve_condition(condition))
            except ContactUnavailable as error:
                self.measurement_failures[condition_id] = {
                    'event': deepcopy(event), 'event_observed': True,
                    'event_evidence': deepcopy(self._event_evidence.get(self._selector_key(event))),
                    'status': 'contact_not_observed_at_event', 'reason': str(error),
                    'policy_action_index': self._action_index(),
                }
                continue
            try:
                result = evaluate_geometry(condition, measured, reference)
            except GeometryUnavailable as error:
                self.measurement_failures[condition_id] = {
                    'event': deepcopy(event), 'event_observed': True,
                    'status': 'geometry_unavailable', 'reason': str(error),
                    'policy_action_index': self._action_index(),
                }
                continue
            self.results[condition_id] = {
                "slot": condition["slot"],
                "kind": condition["kind"],
                "event": event,
                'event_evidence': deepcopy(self._event_evidence.get(self._selector_key(event))),
                "sample_index": self.sample_index,
                'measurement_physics_step': historic['physics_step'] if before else getattr(getattr(self.env,'_atomic_contacts',None),'steps',None),
                "policy_action_index": historic['policy_action_index'] if before else (
                    int(self.env.take_action_cnt[self.env_idx])
                    if hasattr(self.env, "take_action_cnt") else None
                ),
                "measurement": condition["measurement"],
                "condition": deepcopy(condition),
                "measured_state": _state(measured),
                "reference_state": _state(reference) if reference is not None else None,
                "measurement_source": measurement_source,
                "reference_source": reference_source,
                "ee_contact_proxy": (
                    condition["measurement"]["kind"] == "robot_ee_pose"
                    and event["kind"] in ("first_lift", "first_motion")
                ),
                "result": result.as_dict(),
            }

    def _before_contact(self, condition):
        """Latch the preceding synchronized state when the first contact appears."""
        ident=condition['id']
        if ident in self._precontact_consumed:
            return None
        contacts=getattr(self.env,'_atomic_contacts',None)
        if contacts is None:
            raise RuntimeError('before_contact requires synchronized physical contact reports')
        event=condition['event']
        try:
            measured,source=self._resolve_with_source(event['measurement'])
        except ContactUnavailable:
            # Preserve complete point/frame and surface evidence for offline audit.
            self._precontact_samples[ident]={'physics_step':contacts.steps,
                'policy_action_index':self._action_index(),
                'states':deepcopy(self._resolve_condition(condition))}
            return None
        self._precontact_consumed.add(ident)
        sample=self._precontact_samples.get(ident)
        evidence={'contact_physics_step':contacts.steps,'measured_contacts':_state(measured),'contact_source':deepcopy(source)}
        self._event_evidence[self._selector_key(event)]=evidence
        if sample is None or sample['physics_step']!=contacts.steps-1:
            self.measurement_failures[ident]={'status':'preceding_sample_missing','event_observed':True,
                'event':deepcopy(event),'event_evidence':evidence,'policy_action_index':self._action_index()}
            return None
        evidence['preceding_physics_step']=sample['physics_step']
        return sample

    def _resolve_condition(self, condition):
        measured, source = self._resolve_with_source(condition['measurement'])
        reference, reference_source = self._resolve_with_source(condition['reference']) if condition.get('reference') else (None, None)
        if condition.get('relation_scope') == 'objects':
            # Attach surface evidence without changing the explicitly selected
            # landmark. A root-frame reference must not become a bounds centre.
            measured_pose, reference_pose = _array(measured), _array(reference)
            measured = {**self._surface_for_selector(condition['measurement']),
                        'position': measured_pose[:3].tolist(), 'orientation': measured_pose[3:].tolist()}
            reference_surface=(deepcopy(self._frozen_surfaces[self._selector_key(condition['reference'])])
                               if condition['reference'].get('time')=='stage_start' else self._surface_for_selector(condition['reference']))
            reference = {**reference_surface,
                         'position': reference_pose[:3].tolist(), 'orientation': reference_pose[3:].tolist()}
            source['geometry_representation'] = measured['geometry_representation']
            reference_source['geometry_representation'] = reference['geometry_representation']
            if condition['expected'] == 'on_top':
                from task.atomic.geometry import _rotation
                link_kinds = ('articulated_link_pose', 'joint_link_pose')
                object_link = condition['measurement']['kind'] in link_kinds
                support_link = condition['reference']['kind'] in link_kinds
                if object_link or support_link:
                    support_label = condition['reference']['label']
                    evidence = self.env._atomic_contacts.support_evidence(
                        condition['measurement']['label'], [support_label], self.env_idx,
                        _rotation(reference['orientation'])[:, 2],
                        object_body_path=measured['prim_path'] if object_link else None,
                        support_body_paths={support_label: reference['prim_path']} if support_link else None)
                    measured['support_contact'] = bool(evidence['contacts'])
                    measured['support_contact_evidence'] = deepcopy(evidence)
                else:
                    measured['support_contact'] = self.env._atomic_contacts.has_support_contact(
                        condition['measurement']['label'], condition['reference']['label'], self.env_idx,
                        _rotation(reference['orientation'])[:, 2])
        return measured, source, reference, reference_source

    def _surface_for_selector(self,selector):
        if selector['kind']=='cloth_patch_surface':
            from task.atomic.materials import resolve_patch_surface
            return resolve_patch_surface(self.env,selector,self.env_idx)
        if selector['kind'] in ('articulated_link_pose','joint_link_pose'):
            link=selector.get('link')
            if link is None:
                from task.atomic.bindings import joint_from_tag
                from task.atomic.recognizers import live_joint_state
                joint=joint_from_tag(self.env,selector['label'],selector['joint_tag'],self.env_idx)
                _,path=live_joint_state(self.env,selector['label'],joint,self.env_idx)
                link=path.rsplit('/',1)[-1]
            return self.env._atomic_surfaces.resolve_link(selector['label'],link,self.env_idx)
        return self.env._atomic_surfaces.resolve(selector['label'],self.env_idx,self._object_pose(selector['label']),
            **({'mesh_paths':selector['mesh_paths']} if 'mesh_paths' in selector else {}))

    def observe_events(self):
        """Capture first-lift/motion geometry at physics-step resolution."""
        self._observe_interaction()
        self._sample(success_now=False)

    def finalize(self, reason='episode_end'):
        """Sample final-state conditions once, without advancing recognition.

        The caller must invoke this before resetting the scene. This is the
        episode endpoint, including for a stage completed earlier; it is not
        a substitute for a missing grasp, release, strike or entry event.
        """
        if self.finalized:
            return
        self.finalization_evidence = {
            'context': reason, 'policy_action_index': self._action_index(),
            'physics_step': getattr(getattr(self.env, '_atomic_contacts', None), 'steps', None),
            'action_success_at_end': bool(self.success),
        }
        self._finalizing = True
        try:
            self._sample(success_now=False)
            if self._trajectory_observer:
                self._trajectory_observer.finalize()
        finally:
            self._finalizing = False
        self.finalized = True

    def step(self, diagnostics=True):
        """Latch success at a physical sample; optionally score chunk diagnostics."""
        self._observe_interaction()
        success_now = self._check_success()
        self.goal_success = success_now
        self._sample(success_now)
        if self._selection_observer:
            self._selection_observer.observe()
        # Diagnostic scores for failed attempts, separate from the required event.
        for condition in self.stage.geometry:
            if not diagnostics or not condition.get('track_closest', True):
                continue
            try:
                measured, source, reference, _ = self._resolve_condition(condition)
            except ContactUnavailable:
                continue
            try:
                result = evaluate_geometry(condition, measured, reference).as_dict()
            except GeometryUnavailable:
                continue
            old = self.closest_approach.get(condition["id"])
            if old is None or result["error"] < old["result"]["error"]:
                self.closest_approach[condition["id"]] = {
                    "condition": deepcopy(condition), "measured_state": _state(measured),
                    "reference_state": _state(reference) if reference is not None else None,
                    "measurement_source": source, "result": result,
                    "policy_action_index": int(self.env.take_action_cnt[self.env_idx]) if hasattr(self.env, "take_action_cnt") else None,
                    "measurement_context": "closest approach at policy action boundaries; not required-event adherence",
                    "ee_contact_proxy": condition["measurement"]["kind"] == "robot_ee_pose",
                }
        if self.stage.recognition is not None:
            success_now = success_now and (self._physical_recognizer.ready if self._physical_recognizer
                                          else self.interaction_observed)
            if self.stage.family == 'pick':
                success_now = (success_now and self.current_hold_observed
                               and self._recognition_current_displacement[2] >= self._held_lift_required)
        if self._trajectory_observer:
            self._trajectory_observer.observe(success_now and not self.maintained_hold_failures)
        self.success = self.success or (success_now and not self.maintained_hold_failures)
        return self.success

    def check_success_only(self):
        """Advance stage annotation without measuring geometric conditions."""
        self.success = self.success or self._check_success()
        return self.success

    def summary(self):
        passed = sum(item["result"]["passed"] for item in self.results.values())
        total = len(self.stage.geometry)
        observed = len(self.results)
        return {
            "stage_id": self.stage.id,
            "family": self.stage.family,
            "instruction": self.stage.instruction,
            "conditions": deepcopy(list(self.stage.geometry)),
            "coordinate_frame": "environment_local_world",
            "quaternion_order": "wxyz",
            "distance_unit": "metres",
            "angle_unit": "radians",
            "action_success": self.success,
            'required': self.stage.required,
            "geometry_pass_rate": passed / observed if observed else None,
            "geometry_coverage": observed / total if total else None,
            "geometry_observed": observed,
            "geometry_total": total,
            "geometry": self.results,
            "closest_approach": self.closest_approach,
            'measurement_failures': deepcopy(self.measurement_failures),
            'interaction_observed': self.interaction_observed,
            'recognition': deepcopy(self.stage.recognition),
            'recognition_status': (self.stage.recognition['kind'] if self._physical_recognizer
                                   else 'physical_contact_motion' if self.stage.recognition is not None
                                   else 'endpoint_checks_only'),
            'interaction_evidence': deepcopy(self.interaction_evidence),
            'physical_events': deepcopy(self._physical_recognizer.events) if self._physical_recognizer else {},
            'physical_metrics': deepcopy(getattr(self._physical_recognizer, 'metrics', {})),
            'material_flow': self._physical_recognizer.flow_observer.summary() if (
                self._physical_recognizer and self._physical_recognizer.flow_observer) else None,
            'trajectories': self._trajectory_observer.summary() if self._trajectory_observer else {},
            'selection': self._selection_observer.summary() if self._selection_observer else None,
            'current_hold_observed': self.current_hold_observed,
            'maintained_holds': deepcopy(list(self.stage.maintained_holds)),
            'maintained_hold_failures': deepcopy(self.maintained_hold_failures),
            'goal_success': self.goal_success,
            'finalization_evidence': deepcopy(self.finalization_evidence),
            'recognition_checks': deepcopy(list(self.stage.success_checks)),
            'initial_object_positions': {k: v.tolist() for k, v in self.initial_positions.items()},
        }
