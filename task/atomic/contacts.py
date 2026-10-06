"""PhysX contact positions, scoped to a named object and actual finger bodies.

No nearest-link fallback is used. A missing contact is missing evidence.
"""
import numpy as np


class ContactUnavailable(RuntimeError):
    pass


class PhysXContacts:
    def __init__(self, env):
        import carb
        import omni.usd
        from omni.physx import get_physx_simulation_interface
        from pxr import PhysicsSchemaTools, Usd, UsdPhysics
        self.env = env
        # SimulationContext disables this by default. Contact sensors explicitly
        # re-enable it too; subscribing alone otherwise produces zero reports.
        carb.settings.get_settings().set_bool('/physics/disableContactProcessing', False)
        self._decode = PhysicsSchemaTools.intToSdfPath
        self.rows = []
        self.steps = 0
        self.reports = 0
        self.errors = []
        self._support_cache = {}
        self._lost_pairs = set()
        self.event_types = {}
        self.pair_diagnostics = {}
        self.report_pair_diagnostics = {}
        self.enabled_body_paths = []
        self.enable_errors = []
        self.skipped_nested_body_paths = []
        self.material_states = {}
        from omni.physx.bindings._physx import ContactEventType
        self._contact_event_lost = ContactEventType.CONTACT_LOST
        self.fingers = {}
        stage = omni.usd.get_context().get_stage()
        enabled = self.enable_scene_contacts()
        # Resolve finger rigid bodies from the robot's gripper joints, not link-name guesses.
        for robot_index, robot in enumerate(env.robot_manager.robot_list):
            if robot.type != 'target':
                continue
            for env_idx in range(env.num_envs):
                root = f'/World/envs/env_{env_idx}/robot{robot_index}'
                prim = stage.GetPrimAtPath(root)
                if not prim.IsValid():
                    raise RuntimeError(f'contact instrumentation cannot find robot root {root}')
                joint_names = set(robot.gripper_joints_name)
                for child in Usd.PrimRange(prim, Usd.TraverseInstanceProxies()):
                    if child.IsA(UsdPhysics.Joint) and child.GetName() in joint_names:
                        for body in UsdPhysics.Joint(child).GetBody1Rel().GetTargets():
                            self.fingers[str(body)] = (env_idx, robot.arm_name)
        if not self.fingers:
            raise RuntimeError('contact instrumentation resolved no finger rigid bodies')
        self.subscription = get_physx_simulation_interface().subscribe_contact_report_events(self._report)
        print(f'[atomic contacts] enabled {enabled} bodies; fingers {self.fingers}', flush=True)

    def enable_object_contacts(self, prim_path):
        """Install on a newly spawned subtree before its tensor initialization."""
        import omni.usd
        stage = omni.usd.get_context().get_stage()
        root = stage.GetPrimAtPath(prim_path)
        if not root.IsValid():
            raise RuntimeError('contact enablement cannot find spawned subtree ' + prim_path)
        return self._enable_contact_subtree(root)

    def enable_scene_contacts(self):
        """Idempotent scene audit; newly spawned bodies are enabled before warmup.

        Late API authoring can rebuild collider shapes and invalidate already
        initialized PhysX tensor views. SceneManager enables each newly spawned
        subtree before obj.initialize(); this later audit must reuse those APIs.
        """
        import omni.usd
        stage = omni.usd.get_context().get_stage()
        paths = self._enable_contact_subtree(stage.GetPseudoRoot())
        self.enabled_body_paths = paths
        print(f'[atomic contacts] scene bodies enabled: {len(paths)}', flush=True)
        return len(paths)

    def _enable_contact_subtree(self, root):
        from pxr import PhysxSchema, Usd, UsdGeom, UsdPhysics
        paths = []
        for prim in Usd.PrimRange(root, Usd.TraverseInstanceProxies()):
            if not prim.HasAPI(UsdPhysics.RigidBodyAPI):continue
            # A visual/collision child without a transform reset belongs to
            # its enabled ancestor body. Do not add an independent reporting
            # body to an invalid nested hierarchy (notably the baked spheres).
            current = prim
            nested = False
            while current.IsValid():
                transform = UsdGeom.Xformable(current)
                if transform and transform.GetResetXformStack():
                    break
                current = current.GetParent()
                if current.IsValid() and current.HasAPI(UsdPhysics.RigidBodyAPI):
                    if UsdPhysics.RigidBodyAPI(current).GetRigidBodyEnabledAttr().Get() is not False:
                        nested = True
                        break
            if nested:
                path = str(prim.GetPath())
                if path not in self.skipped_nested_body_paths:
                    self.skipped_nested_body_paths.append(path)
                continue
            try:
                if not prim.HasAPI(PhysxSchema.PhysxContactReportAPI):
                    PhysxSchema.PhysxContactReportAPI.Apply(prim).CreateThresholdAttr(0.0)
                else:
                    threshold = PhysxSchema.PhysxContactReportAPI(prim).GetThresholdAttr()
                    if threshold.Get() != 0.0:
                        threshold.Set(0.0)
                paths.append(str(prim.GetPath()))
            except Exception as error:
                self.enable_errors.append({'body':str(prim.GetPath()),'error':str(error)})
        if self.enable_errors:raise RuntimeError('contact report API could not be enabled: '+str(self.enable_errors[:4]))
        return paths

    def begin_step(self):
        self.rows = []
        if hasattr(self,'material_states'): self.material_states.clear()
        self.steps += 1

    def reset_scene_evidence(self):
        """A reloaded body path must never inherit another episode's contact."""
        self.rows = []
        self._support_cache.clear()
        self._lost_pairs.clear()
        self.material_states.clear()
        self.pair_diagnostics.clear()
        self.report_pair_diagnostics.clear()
        self.event_types.clear()
        self.errors.clear()
        self.enable_errors.clear()
        self.steps = 0
        self.reports = 0

    def _report(self, headers, data):
        self.reports += 1
        try:
            for header in headers:
                a = str(self._decode(header.actor0))
                b = str(self._decode(header.actor1))
                c0 = str(self._decode(header.collider0))
                c1 = str(self._decode(header.collider1))
                kind = getattr(header, 'type', None)
                if not hasattr(self, '_lost_pairs'): self._lost_pairs = set()
                if not hasattr(self, 'event_types'): self.event_types = {}
                name = str(kind)
                self.event_types[name] = self.event_types.get(name, 0) + 1
                pair = tuple(sorted(((a, c0), (b, c1))))
                lifecycle = kind is not None and getattr(self, '_contact_event_lost', None) is not None
                if lifecycle and kind == self._contact_event_lost:
                    self._lost_pairs.add(pair)
                    continue
                if lifecycle: self._lost_pairs.discard(pair)
                if not hasattr(self, 'report_pair_diagnostics'): self.report_pair_diagnostics = {}
                key = '|'.join((a,b,c0,c1))
                if key not in self.report_pair_diagnostics and len(self.report_pair_diagnostics) < 96:
                    self.report_pair_diagnostics[key] = {'headers':0, 'points':0, 'force_points':0,
                        'zero_impulse_points':0, 'latest_physics_step':self.steps}
                diagnostic = self.report_pair_diagnostics.get(key)
                if diagnostic:
                    diagnostic['headers'] += 1
                    diagnostic['points'] += header.num_contact_data
                    diagnostic['latest_physics_step'] = self.steps
                for contact in data[header.contact_data_offset:header.contact_data_offset + header.num_contact_data]:
                    impulse = np.asarray(contact.impulse, dtype=float)
                    position = np.asarray(contact.position, dtype=float)
                    normal = np.asarray(contact.normal, dtype=float)
                    if any(value.shape != (3,) or not np.isfinite(value).all() for value in (impulse, position, normal)):
                        raise ValueError('contact position, normal and impulse must be finite 3-vectors')
                    if np.linalg.norm(impulse) <= 1e-9:
                        if diagnostic: diagnostic['zero_impulse_points'] += 1
                        continue
                    if diagnostic: diagnostic['force_points'] += 1
                    if not np.isclose(np.linalg.norm(normal), 1., atol=1e-3):
                        raise ValueError('force-bearing contact normal must be a unit vector')
                    self.rows.append({'actor0': a, 'actor1': b, 'collider0': c0, 'collider1': c1,
                                      'position_world': position.tolist(), 'normal_world': normal.tolist(),
                                      'impulse': impulse.tolist(), 'lifecycle_supported': lifecycle,
                                      'force_report_physics_step': self.steps})
        except Exception as error:
            self.errors.append(f'{type(error).__name__}: {error}')
            if len(self.errors) == 1:
                print('[atomic contacts] report error:', self.errors[-1], flush=True)

    def resolve(self, selector, env_idx):
        if self.errors:
            raise RuntimeError('PhysX contact reporting failed: ' + self.errors[-1])
        lm = self.env.scene_manager.layout_manager
        name = lm.get_instance_name(env_idx, selector['label'])
        obj = lm.get_scene_object(env_idx, name)
        root = getattr(obj, 'usd_prim_path', None) or getattr(obj, 'prim_path', None)
        if not root:
            raise RuntimeError(f'no rigid prim path for {selector["label"]}')
        body_path = selector.get('body_path')
        if selector.get('joint_tag'):
            from task.atomic.bindings import joint_from_tag
            from task.atomic.recognizers import live_joint_state
            joint = joint_from_tag(self.env, selector['label'], selector['joint_tag'], env_idx)
            _, body_path = live_joint_state(self.env, selector['label'], joint, env_idx)
        if body_path and not (body_path == root or body_path.startswith(root + '/')):
            raise ValueError('moving contact body must belong to the selected object')
        def inside(path):
            return path == root or path.startswith(root + '/')
        selected = []
        for row in self.rows:
            for index, other in ((0, 1), (1, 0)):
                body = row[f'actor{index}']
                finger = self.fingers.get(body)
                if (finger and finger[0] == env_idx
                        and (inside(row[f'actor{other}']) or inside(row[f'collider{other}']))):
                    if body_path and not any(p == body_path or p.startswith(body_path + '/')
                                             for p in (row[f'actor{other}'], row[f'collider{other}'])):
                        continue
                    if selector.get('arm', 'any') not in ('any', 'nearest', finger[1]):
                        continue
                    selected.append({**row, 'finger_body': body, 'arm': finger[1]})
        if not selected:
            raise ContactUnavailable('no force-bearing finger/object contacts at this physics step')
        # Choose among qualifying arms first. Many points from one finger must
        # not hide a valid two-finger grasp by the other arm.
        arms = {row['arm'] for row in selected}
        eligible = [arm for arm in arms if len({row['finger_body'] for row in selected if row['arm'] == arm})
                    >= selector.get('min_finger_bodies', 1)]
        if not eligible:
            raise ContactUnavailable('insufficient distinct contacting finger bodies')
        arm = max(sorted(eligible), key=lambda arm: sum(row['arm'] == arm for row in selected))
        selected = [row for row in selected if row['arm'] == arm]
        fingers = set(row['finger_body'] for row in selected)
        origin = self.env.sim.scene.env_origins[env_idx]
        if hasattr(origin, 'detach'):
            origin = origin.detach().cpu().numpy()
        points = np.asarray([row['position_world'] for row in selected], dtype=float) - np.asarray(origin)
        return {'position': points.mean(axis=0).tolist(), 'points': points.tolist()}, {
            **selector, 'frame': 'environment_local_world', 'resolved_arm': arm,
            'finger_bodies': sorted(fingers), 'contacts': selected,
            'aggregation': 'maximum per-contact error; centroid is diagnostic only',
            'physics_step': self.steps, 'contact_reports': self.reports,
        }

    def summary(self):
        return {'backend': 'PhysX contact reports', 'steps': self.steps, 'reports': self.reports,
                'event_types': dict(getattr(self, 'event_types', {})),
                'support_pair_diagnostics': dict(getattr(self, 'pair_diagnostics', {})),
                'report_pair_diagnostics': dict(getattr(self, 'report_pair_diagnostics', {})),
                'enabled_body_paths': list(getattr(self, 'enabled_body_paths', [])),
                'skipped_nested_body_paths': list(getattr(self, 'skipped_nested_body_paths', [])),
                'enable_errors': list(getattr(self, 'enable_errors', [])),
                'health_status': ('callback_error' if self.errors else
                                  'observed_reports' if self.reports else 'awaiting_contact_evidence'),
                'resolved_finger_bodies': self.fingers, 'errors': self.errors}

    def resolve_object_pair(self, selector, env_idx):
        """Force-bearing points between two named physical object subtrees.

        Tool/target contact is a different pair from finger/tool grasp. Retain
        actors and colliders so an adapter can identify the actual touched part.
        This sampler alone does not establish a held tool or a strike/sweep.
        """
        if self.errors:
            raise RuntimeError('PhysX contact reporting failed: ' + self.errors[-1])
        lm = self.env.scene_manager.layout_manager
        roots = []
        for label in (selector['label'], selector['other_label']):
            name = lm.get_instance_name(env_idx, label)
            if name is None:
                raise ValueError(f'unknown contact object {label!r}')
            obj = lm.get_scene_object(env_idx, name)
            root = getattr(obj, 'usd_prim_path', None) or getattr(obj, 'prim_path', None)
            if not root:
                raise RuntimeError(f'no physical prim path for {label}')
            roots.append(root)
        if roots[0] == roots[1]:
            raise ValueError('object contact requires distinct physical object roots')
        def matches(row, index, root):
            return any(path == root or path.startswith(root + '/') for path in
                       (row[f'actor{index}'], row[f'collider{index}']))
        selected = [row for row in self.rows if
                    (matches(row, 0, roots[0]) and matches(row, 1, roots[1])) or
                    (matches(row, 1, roots[0]) and matches(row, 0, roots[1]))]
        if not selected:
            raise ContactUnavailable('no force-bearing object/object contacts at this physics step')
        origin = self.env.sim.scene.env_origins[env_idx]
        if hasattr(origin, 'detach'):
            origin = origin.detach().cpu().numpy()
        points = np.asarray([row['position_world'] for row in selected], dtype=float) - np.asarray(origin)
        return {'position': points.mean(axis=0).tolist(), 'points': points.tolist()}, {
            **selector, 'frame': 'environment_local_world', 'object_roots': roots,
            'contacts': selected, 'physics_step': self.steps, 'contact_reports': self.reports,
            'aggregation': 'maximum per-contact error; centroid is diagnostic only',
        }

    def has_support_contact(self, label_a, label_b, env_idx, normal_axis=(0, 0, 1),
                            object_body_path=None, support_body_paths=None):
        return bool(self.support_evidence(label_a, [label_b], env_idx, normal_axis,
                    object_body_path=object_body_path, support_body_paths=support_body_paths)['contacts'])

    def support_evidence(self, label, support_labels, env_idx, normal_axis=(0, 0, 1),
                         object_body_path=None, support_body_paths=None):
        """Signed force-bearing contacts with named supports, including scene table.

        PxContactPairPoint.normal points from shape 1 toward shape 0. Flip it
        when the supported object is actor/collider 1; abs(dot) accepts downward
        forces and is not evidence of load-bearing support.
        """
        if self.errors:
            raise RuntimeError('PhysX contact reporting failed: ' + self.errors[-1])
        lm = self.env.scene_manager.layout_manager
        obj = lm.get_scene_object(env_idx, lm.get_instance_name(env_idx, label))
        root = getattr(obj, 'usd_prim_path', None) or getattr(obj, 'prim_path', None)
        supports = {}
        for support_label in support_labels:
            if support_label == '@table':
                obj = self.env.scene_manager._tables[env_idx]
            else:
                obj = lm.get_scene_object(env_idx, lm.get_instance_name(env_idx, support_label))
            supports[support_label] = getattr(obj, 'usd_prim_path', None) or getattr(obj, 'prim_path', None)
        if not root or any(not value for value in supports.values()):
            raise RuntimeError('support contact requires resolved object prim paths')
        support_body_paths = support_body_paths or {}
        if set(support_body_paths) - set(supports):
            raise ValueError('support body scopes must name a selected support')
        def scoped_path(parent, body):
            if body is None:
                return parent
            if not isinstance(body, str) or not (body == parent or body.startswith(parent + '/')):
                raise ValueError('support contact body must belong to its selected object')
            return body
        object_scope = scoped_path(root, object_body_path)
        support_scopes = {name: scoped_path(path, support_body_paths.get(name))
                          for name, path in supports.items()}
        axis = np.asarray(normal_axis, dtype=float)
        if axis.shape != (3,) or not np.isfinite(axis).all() or np.linalg.norm(axis) == 0:
            raise ValueError('support axis must be a finite nonzero 3-vector')
        axis /= np.linalg.norm(axis)
        def matches(row, index, root):
            return any(p == root or p.startswith(root + '/') for p in
                       (row[f'actor{index}'], row[f'collider{index}']))
        selected = []
        candidates = []
        for row in self.rows:
            for index, other in ((0, 1), (1, 0)):
                if not matches(row, index, object_scope):
                    continue
                normal = np.asarray(row['normal_world']) * (1 if index == 0 else -1)
                impulse = np.asarray(row['impulse']) * (1 if index == 0 else -1)
                for support_label, support_root in support_scopes.items():
                    if matches(row, other, support_root):
                        normal_dot, impulse_dot = float(normal @ axis), float(impulse @ axis)
                        candidates.append({'support_label': support_label,
                                           'normal_axis_dot': normal_dot, 'axial_impulse_ns': impulse_dot})
                        if normal_dot > .5 and impulse_dot > 1e-9:
                            selected.append({**row, 'support_label': support_label,
                                             'normal_on_object_world': normal.tolist(),
                                             'impulse_on_object_world': impulse.tolist()})
        if not hasattr(self, 'pair_diagnostics'): self.pair_diagnostics = {}
        if len(self.pair_diagnostics) < 64 or label in self.pair_diagnostics:
            old = self.pair_diagnostics.setdefault(label, {'candidate_steps': 0, 'force_support_steps': 0})
            old['candidate_steps'] += int(bool(candidates))
            old['force_support_steps'] += int(bool(selected))
            if candidates: old['latest_candidates'] = candidates[:16]
        # PhysX may stop reporting impulses once bodies sleep. Preserve a
        # previously force-bearing support pair only with an available contact
        # lifecycle, no LOST event, and unchanged *both* object/support poses.
        # This history is never used for grasp/tool contact measurements.
        if not hasattr(self, '_support_cache'): self._support_cache = {}
        cache_key = (env_idx, label, tuple(sorted(support_labels)), tuple(axis))
        poses = None
        def articulated(item):
            if item == '@table': return False
            instance = lm.get_instance_name(env_idx, item)
            category = getattr(lm, 'instance_type_by_env', [{}])[env_idx].get(instance)
            return category == 'articulation'
        if (object_body_path is None and not support_body_paths
                and not any(articulated(item) for item in [label]+list(support_labels))):
            try:
                def pose_for(item):
                    if item == '@table':
                        position, orientation = self.env.scene_manager._tables[env_idx].get_world_pose()
                    else:
                        position, orientation = lm.get_instance_pose(env_idx=env_idx, label=item)
                    values = []
                    for value in (position, orientation):
                        if hasattr(value, 'detach'): value = value.detach().cpu().numpy()
                        values.extend(np.asarray(value, dtype=float).reshape(-1))
                    value = np.asarray(values)
                    if value.shape != (7,) or not np.isfinite(value).all(): raise ValueError('invalid support pose')
                    return value
                poses = {item: pose_for(item) for item in [label]+list(support_labels)}
            except (AttributeError, TypeError, ValueError):
                poses = None
        persistent = False
        if selected:
            eligible = [r for r in selected if r.get('lifecycle_supported')]
            if poses is not None and eligible:
                self._support_cache[cache_key] = {'poses': poses, 'contacts': eligible, 'physics_step': self.steps}
        elif candidates:
            self._support_cache.pop(cache_key, None)
        elif poses is not None:
            cached = self._support_cache.get(cache_key)
            if cached and all(np.allclose(poses[k], cached['poses'][k], rtol=0, atol=1e-7) for k in poses):
                valid = [row for row in cached['contacts'] if tuple(sorted(
                    ((row['actor0'],row['collider0']),(row['actor1'],row['collider1'])))) not in getattr(self,'_lost_pairs',set())]
                if valid:
                    selected = [{**row, 'support_evidence_kind':'persistent_unchanged_contact',
                                 'last_force_report_physics_step':cached['physics_step']} for row in valid]
                    persistent = True
            else:
                self._support_cache.pop(cache_key, None)
        return {'object': label, 'object_root': root, 'support_roots': supports,
                'object_contact_scope': object_scope, 'support_contact_scopes': support_scopes,
                'normal_axis_world': axis.tolist(), 'physics_step': self.steps, 'contacts': selected,
                'candidate_contact_diagnostics': candidates,
                'support_evidence_kind': 'persistent_unchanged_contact' if persistent else 'current_force_report',
                'normal_convention': 'shape1 to shape0, reversed for supported object in slot1'}

    def close(self):
        self.subscription = None
