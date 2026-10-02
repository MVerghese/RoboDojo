"""Concurrent dependency-driven stages observed at physics-substep resolution."""
from copy import deepcopy

from task.atomic.session import AtomicSession


class AtomicSequence:
    def __init__(self, env, program, env_idx):
        self.env, self.program, self.env_idx = env, program, env_idx
        self.completed = {}
        self.sessions = {}
        self.stage_starts = {}  # Only whole-action, prefix-replayable boundaries.
        self.stage_boundaries = {}
        self._dependencies = program.dependencies()
        self._activate(0, at_action_boundary=True)

    @property
    def index(self):
        return next((i for i, s in enumerate(self.program.stages) if s.id not in self.completed), len(self.program.stages))

    @property
    def session(self):
        # Compatibility for clients inspecting an ordered program.
        return next((self.sessions[s.id] for s in self.program.stages if s.id in self.sessions), None)

    def _physics_step(self):
        contacts = getattr(self.env, '_atomic_contacts', None)
        return contacts.steps if contacts is not None else None

    def _activate(self, action_count, at_action_boundary):
        for stage in self.program.stages:
            if stage.id in self.completed or stage.id in self.sessions:
                continue
            if not set(self._dependencies[stage.id]) <= self.completed.keys():
                continue
            self.sessions[stage.id] = AtomicSession(self.env, stage, self.env_idx)
            self.stage_boundaries[stage.id] = {
                'action_index': action_count, 'physics_step': self._physics_step(),
                'at_action_boundary': at_action_boundary,
                'prefix_replay_supported': at_action_boundary,
            }
            if at_action_boundary:
                self.stage_starts[stage.id] = action_count

    def _advance(self, action_count, at_action_boundary):
        done = []
        # Sample every previously enabled node before enabling successors. One
        # event cannot complete a stage and its successor in the same substep.
        for stage_id, session in list(self.sessions.items()):
            if not session.step(diagnostics=at_action_boundary):
                continue
            start = self.stage_boundaries[stage_id]
            self.completed[stage_id] = {
                **session.summary(), 'reached': True, 'start_action': start['action_index'],
                'end_action': action_count, 'start_boundary': deepcopy(start),
                'end_boundary': {'action_index': action_count, 'physics_step': self._physics_step(),
                                 'at_action_boundary': at_action_boundary},
            }
            done.append(stage_id)
        for stage_id in done:
            del self.sessions[stage_id]
        if done:
            self._activate(action_count, at_action_boundary)

    def observe_events(self):
        for session in list(self.sessions.values()):
            session.observe_events()
        count = int(self.env.take_action_cnt[self.env_idx]) if hasattr(self.env, 'take_action_cnt') else 0
        self._advance(count, at_action_boundary=False)

    def step(self, action_count):
        self._advance(action_count, at_action_boundary=True)

    def summary(self):
        rows = []
        for stage in self.program.stages:
            if stage.id in self.completed:
                row = self.completed[stage.id]
            elif stage.id in self.sessions:
                start = self.stage_boundaries[stage.id]
                row = {**self.sessions[stage.id].summary(), 'reached': True,
                       'start_action': start['action_index'], 'end_action': None,
                       'start_boundary': deepcopy(start), 'end_boundary': None}
            else:
                row = {'stage_id': stage.id, 'family': stage.family, 'instruction': stage.instruction,
                       'conditions': deepcopy(list(stage.geometry)), 'reached': False,
                       'recognition': deepcopy(stage.recognition), 'recognition_status': 'not_started',
                       'action_success': False, 'geometry_pass_rate': None,
                       'geometry_coverage': 0.0 if stage.geometry else None,
                       'geometry_observed': 0, 'geometry_total': len(stage.geometry),
                       'geometry': {}, 'start_action': None, 'end_action': None,
                       'start_boundary': None, 'end_boundary': None}
            rows.append(deepcopy(row))
        return {'task_name': self.program.task_name, 'instruction': self.program.instruction,
                'geometric_instruction': self.program.geometric_instruction,
                'stage_dependencies': deepcopy(self._dependencies),
                'active_stages': sorted(self.sessions),
                'stage_starts': deepcopy(self.stage_starts),
                'stage_boundaries': deepcopy(self.stage_boundaries), 'stages': rows}
