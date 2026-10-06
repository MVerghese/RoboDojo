"""Concurrent dependency-driven stages observed at physics-substep resolution."""
from copy import deepcopy

from task.atomic.session import AtomicSession


class AtomicSequence:
    def __init__(self, env, program, env_idx):
        program = program.bind(env, env_idx)
        self.env, self.program, self.env_idx = env, program, env_idx
        self.completed = {}
        self.sessions = {}
        self._finished_sessions = {}
        self.gate_sessions = {}
        self._not_selected = {}
        self._choice_states = {}
        self.stage_starts = {}  # Only whole-action, prefix-replayable boundaries.
        self.stage_boundaries = {}
        self._dependencies = program.dependencies()
        self._activate(0, at_action_boundary=True)
        from task.atomic.calibration import snapshot_scene
        self.calibration = snapshot_scene(self.session) if self.session else {'status': 'no_active_action', 'objects': {}}

    @property
    def index(self):
        return next((i for i, s in enumerate(self.program.stages) if s.id not in self.completed and s.id not in self._not_selected), len(self.program.stages))

    @property
    def session(self):
        # Compatibility for clients inspecting an ordered program.
        return next((self.sessions[s.id] for s in self.program.stages if s.id in self.sessions), None)

    def _physics_step(self):
        contacts = getattr(self.env, '_atomic_contacts', None)
        return contacts.steps if contacts is not None else None

    def _activate(self, action_count, at_action_boundary):
        for stage in self.program.stages:
            if stage.id in self.completed or stage.id in self.sessions or stage.id in self._not_selected:
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
        for gate in self.program.gates:
            if gate.id in self.completed or gate.id in self.gate_sessions:
                continue
            if not set(self._dependencies[gate.id]) <= self.completed.keys():
                continue
            # Reuse only the read-only predicate resolver. Gate rows are kept
            # separate and never reported as robot atomic actions.
            from task.atomic.spec import AtomicStage
            definition = AtomicStage(gate.id, 'place', 'Observe scene event', gate.checks, ())
            self.gate_sessions[gate.id] = AtomicSession(self.env, definition, self.env_idx)

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
            self._finished_sessions[stage_id] = self.sessions[stage_id]
            del self.sessions[stage_id]
        for gate_id, session in list(self.gate_sessions.items()):
            if session._check_success():
                self.completed[gate_id] = {'gate_id':gate_id, 'observed':True,
                    'action_index':action_count, 'physics_step':self._physics_step(),
                    'checks':deepcopy(list(session.stage.success_checks))}
                del self.gate_sessions[gate_id]
                done.append(gate_id)
        if done:
            self._resolve_choices(action_count,at_action_boundary)
            self._activate(action_count, at_action_boundary)

    def _resolve_choices(self,action_count,at_action_boundary):
        for choice in self.program.choices:
            if choice.id in self.completed or self._choice_states.get(choice.id,{}).get('status')=='ambiguous_completion':
                continue
            observed=[i for i,branch in enumerate(choice.branches) if set(branch)<=self.completed.keys()]
            if len(observed)<choice.required:
                continue
            evidence={'choice_id':choice.id,'required_branches':choice.required,'completed_branches':observed,
                      'action_index':action_count,'physics_step':self._physics_step()}
            if len(observed)>choice.required:
                self._choice_states[choice.id]={**evidence,'status':'ambiguous_completion'}
                continue
            evidence['status']='resolved'
            self.completed[choice.id]=evidence
            self._choice_states[choice.id]=evidence
            for index,branch in enumerate(choice.branches):
                if index in observed:
                    continue
                for ident in branch:
                    session=self.sessions.pop(ident,None)
                    self._not_selected[ident]={'choice_id':choice.id,'branch_index':index,
                        'attempt':session.summary() if session else None}

    def observe_events(self):
        for session in list(self.sessions.values()):
            session.observe_events()
        count = int(self.env.take_action_cnt[self.env_idx]) if hasattr(self.env, 'take_action_cnt') else 0
        self._advance(count, at_action_boundary=False)

    def step(self, action_count):
        self._advance(action_count, at_action_boundary=True)

    def finalize(self, reason='episode_end'):
        """Measure endpoints for every started stage before scene reset."""
        for session in list(self.sessions.values()) + list(self._finished_sessions.values()):
            session.finalize(reason)
        for ident, session in self._finished_sessions.items():
            # Preserve the original completion boundary; final-state scores
            # describe episode end rather than that earlier action boundary.
            self.completed[ident].update(session.summary())

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
                       'required': stage.required,
                       'geometry_coverage': 0.0 if stage.geometry else None,
                       'geometry_observed': 0, 'geometry_total': len(stage.geometry),
                       'geometry': {}, 'start_action': None, 'end_action': None,
                       'start_boundary': None, 'end_boundary': None}
            if stage.id in self._not_selected:
                skipped=self._not_selected[stage.id]
                if skipped['attempt'] is not None and stage.id not in self.completed:
                    row={**skipped['attempt'],'reached':True,'start_action':self.stage_boundaries[stage.id]['action_index'],
                         'end_action':None,'start_boundary':deepcopy(self.stage_boundaries[stage.id]),'end_boundary':None}
                row={**row,'required':False,'choice_status':'not_selected','choice_id':skipped['choice_id'],
                     'choice_branch':skipped['branch_index']}
            rows.append(deepcopy(row))
        return {'task_name': self.program.task_name, 'instruction': self.program.instruction,
                'scene_calibration': deepcopy(self.calibration),
                'geometric_instruction': self.program.geometric_instruction,
                'stage_dependencies': deepcopy(self._dependencies),
                'active_stages': sorted(self.sessions),
                'active_gates': sorted(self.gate_sessions),
                'gates': [deepcopy(self.completed.get(g.id, {'gate_id':g.id,'observed':False}))
                          for g in self.program.gates],
                'binding_evidence': deepcopy(self.program.binding_evidence),
                'choices': [deepcopy(self._choice_states.get(c.id,{'choice_id':c.id,'status':'pending','required_branches':c.required})) for c in self.program.choices],
                'stage_starts': deepcopy(self.stage_starts),
                'stage_boundaries': deepcopy(self.stage_boundaries), 'stages': rows}
