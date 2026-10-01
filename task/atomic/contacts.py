"""PhysX contact positions, scoped to a named object and actual finger bodies.

No nearest-link fallback is used. A missing contact is missing evidence.
"""
from collections import Counter
import numpy as np


class ContactUnavailable(RuntimeError):
    pass


class PhysXContacts:
    def __init__(self, env):
        import omni.usd
        from omni.physx import get_physx_simulation_interface
        from pxr import PhysxSchema, PhysicsSchemaTools, Usd, UsdPhysics
        self.env = env
        self._decode = PhysicsSchemaTools.intToSdfPath
        self.rows = []
        self.steps = 0
        self.reports = 0
        self.errors = []
        self.fingers = {}
        stage = omni.usd.get_context().get_stage()
        enabled = 0
        for prim in stage.Traverse():
            if prim.HasAPI(UsdPhysics.RigidBodyAPI):
                PhysxSchema.PhysxContactReportAPI.Apply(prim).CreateThresholdAttr(0.0)
                enabled += 1
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

    def begin_step(self):
        self.rows = []
        self.steps += 1

    def _report(self, headers, data):
        self.reports += 1
        try:
            for header in headers:
                a = str(self._decode(header.actor0))
                b = str(self._decode(header.actor1))
                c0 = str(self._decode(header.collider0))
                c1 = str(self._decode(header.collider1))
                for contact in data[header.contact_data_offset:header.contact_data_offset + header.num_contact_data]:
                    impulse = np.asarray(contact.impulse, dtype=float)
                    if not np.isfinite(impulse).all() or np.linalg.norm(impulse) <= 1e-9:
                        continue
                    self.rows.append({'actor0': a, 'actor1': b, 'collider0': c0, 'collider1': c1,
                                      'position_world': list(contact.position), 'normal_world': list(contact.normal),
                                      'impulse': impulse.tolist()})
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
        def inside(path):
            return path == root or path.startswith(root + '/')
        selected = []
        for row in self.rows:
            for index, other in ((0, 1), (1, 0)):
                body = row[f'actor{index}']
                finger = self.fingers.get(body)
                if finger and finger[0] == env_idx and inside(row[f'actor{other}']):
                    if selector.get('arm', 'any') not in ('any', 'nearest', finger[1]):
                        continue
                    selected.append({**row, 'finger_body': body, 'arm': finger[1]})
        if not selected:
            raise ContactUnavailable('no force-bearing finger/object contacts at this physics step')
        counts = Counter(row['arm'] for row in selected)
        # Choose the contacting arm, then require both fingers for a grasp.
        arm = max(counts, key=counts.get)
        selected = [row for row in selected if row['arm'] == arm]
        fingers = set(row['finger_body'] for row in selected)
        if len(fingers) < selector.get('min_finger_bodies', 1):
            raise ContactUnavailable('insufficient distinct contacting finger bodies')
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
                'resolved_finger_bodies': self.fingers, 'errors': self.errors}

    def has_support_contact(self, label_a, label_b, env_idx, normal_axis=(0, 0, 1)):
        lm = self.env.scene_manager.layout_manager
        roots = []
        for label in (label_a, label_b):
            obj = lm.get_scene_object(env_idx, lm.get_instance_name(env_idx, label))
            roots.append(getattr(obj, 'usd_prim_path', None) or getattr(obj, 'prim_path', None))
        def matches(row, index, root):
            return any(p == root or p.startswith(root + '/') for p in
                       (row[f'actor{index}'], row[f'collider{index}']))
        return any(abs(np.asarray(row['normal_world']) @ np.asarray(normal_axis)) > 0.5 and
                   ((matches(row, 0, roots[0]) and matches(row, 1, roots[1])) or
                    (matches(row, 1, roots[0]) and matches(row, 0, roots[1]))) for row in self.rows)

    def close(self):
        self.subscription = None
