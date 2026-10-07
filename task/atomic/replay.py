"""Validate and replay recorded policy actions up to an atomic stage."""


def validate_start_boundary(program, selected_stage, trace):
    """Permit any concrete root at the initial scene, or a verified linear prefix."""
    if program.repeat_counts or program.gates or program.choices or program.label_templates:
        raise ValueError('prefix replay requires an expanded linear program without scene gates or choices')
    stage_ids = [stage.id for stage in program.stages]
    selected_index = stage_ids.index(selected_stage.id)
    dependencies = program.dependencies()
    if trace is None:
        if dependencies[selected_stage.id]:
            raise ValueError('a recorded trace is required for a stage with preceding dependencies')
        return {'mode': 'initial_scene', 'action_index': 0, 'stage_id': selected_stage.id,
                'state_restoration': False}
    if trace.task_name != program.task_name:
        raise ValueError('atomic trace task_name does not match program')
    physical = trace.stage_boundaries.get(selected_stage.id, {})
    partial = physical.get('at_action_boundary') is False
    if selected_stage.id not in trace.stage_starts and not partial:
        raise ValueError(f'trace has no boundary for stage {selected_stage.id!r}')
    if not partial and not dependencies[selected_stage.id] and trace.stage_starts[selected_stage.id] == 0:
        return {'mode': 'initial_scene', 'action_index': 0, 'stage_id': selected_stage.id,
                'state_restoration': False}
    linear = {s.id: ([] if i == 0 else [program.stages[i - 1].id])
              for i, s in enumerate(program.stages)}
    if dependencies != linear:
        raise ValueError('prefix replay currently requires a linear program; graph starts need state restoration')
    if trace.stage_starts.get(stage_ids[0]) != 0:
        raise ValueError('trace must start its first atomic stage at action 0')
    starts = [trace.stage_starts.get(stage_id) for stage_id in stage_ids[:selected_index + 1]]
    if partial:
        action_index = physical.get('action_index')
        physics_step = physical.get('physics_step')
        if (selected_index == 0 or type(action_index) is not int or not 1 <= action_index <= len(trace.actions)
                or type(physics_step) is not int):
            raise ValueError('substep boundary needs a preceding stage and a valid action/physics index')
        timing = trace.control_timing
        dt, count = timing.get('physics_dt'), timing.get('control_substeps')
        import math
        if (type(dt) not in (int, float) or not math.isfinite(dt) or dt <= 0
                or type(count) is not int or count <= 0):
            raise ValueError('substep replay needs recorded positive physics_dt and control_substeps')
        if len(trace.action_physics_spans) != len(trace.actions):
            raise ValueError('substep replay needs physics spans for every recorded action')
        previous_end = None
        for span in trace.action_physics_spans[:action_index]:
            first, last = (span.get('start'), span.get('end')) if isinstance(span, dict) else (None, None)
            if (type(first) is not int or type(last) is not int or last - first != count
                    or (previous_end is not None and first != previous_end)):
                raise ValueError('substep replay needs contiguous spans matching control_substeps')
            previous_end = last
        preceding = starts[:-1]
        if (any(type(start) is not int for start in preceding)
                or any(b <= a for a, b in zip(preceding, preceding[1:]))
                or preceding[-1] >= action_index):
            raise ValueError('substep replay needs whole-action strictly increasing preceding boundaries')
        span = trace.action_physics_spans[action_index - 1]
        if not span['start'] < physics_step <= span['end']:
            raise ValueError('substep boundary must lie inside its recorded control action')
        return {'mode': 'linear_substep_prefix', 'action_index': action_index,
                'stage_id': selected_stage.id, 'physics_substeps': physics_step - span['start'],
                'recorded_physics_step': physics_step, 'state_restoration': False,
                'scope': 'joint-control prefix ending at a synchronized physics boundary; not a simulator snapshot'}
    if any(start is None for start in starts) or any(later <= earlier for earlier,later in zip(starts,starts[1:])):
        raise ValueError('trace stage boundaries must be present and strictly increasing')
    return {'mode': 'linear_prefix', 'action_index': starts[-1], 'stage_id': selected_stage.id,
            'state_restoration': False, 'scope': 'whole-action prefix replay, not a full simulator snapshot'}


def replay_prefix(program, selected_stage, trace, take_action, stage_succeeded, take_partial_action=None):
    """Replay actions and verify each preceding stage at its recorded boundary.

    ``take_action`` and ``stage_succeeded`` are callbacks so the boundary logic
    can be tested without importing Isaac Sim.
    """
    boundary = validate_start_boundary(program, selected_stage, trace)
    if boundary['mode'] == 'initial_scene':
        return 0
    if boundary['mode'] == 'linear_substep_prefix' and take_partial_action is None:
        raise ValueError('substep replay requires a physics-boundary action callback')
    stage_ids = [stage.id for stage in program.stages]
    selected_index = stage_ids.index(selected_stage.id)
    starts = [trace.stage_starts.get(stage_id) for stage_id in stage_ids[:selected_index + 1]]
    selected_start = boundary['action_index']
    for action_index, action in enumerate(trace.actions[:selected_start], start=1):
        if boundary['mode'] == 'linear_substep_prefix' and action_index == selected_start:
            take_partial_action(action, boundary['physics_substeps'])
        else:
            take_action(action)
        for stage_index in range(selected_index):
            next_start = selected_start if stage_index == selected_index - 1 else starts[stage_index + 1]
            if action_index == next_start:
                stage = program.stages[stage_index]
                if not stage_succeeded(stage):
                    raise ValueError(
                        f"replay diverged: stage {stage.id!r} failed at action {action_index}"
                    )
    return selected_start


class SubstepReplayStop:
    """Observe synchronized steps; the command loop stops after the callback."""
    def __init__(self, contacts, physics_substeps):
        self.start = contacts.steps
        self.target = self.start + physics_substeps
        self.last = self.start
        self.reached = False
        self.error = None

    def observe(self, contacts):
        current = contacts.steps
        if current != self.last + 1 or current > self.target:
            self.error = 'substep replay physics sampling diverged from recorded timing'
            self.reached = True
            return
        self.last = current
        self.reached = current == self.target


def validate_substep_runtime(env, trace):
    """Reject command sources whose unexecuted state cannot be retained yet."""
    if env.num_envs != 1 or getattr(env, 'interact', False) or getattr(env, 'support_arm_action', None):
        raise ValueError('substep replay currently needs one environment without scripted support-arm controls')
    if getattr(env, '_atomic_contacts', None) is None:
        raise ValueError('substep replay requires synchronized physics contact sampling')
    import math
    if (not math.isclose(env.dt, trace.control_timing['physics_dt'], rel_tol=0, abs_tol=1e-12)
            or int(env.obs_manager.collect_interval) != trace.control_timing['control_substeps']):
        raise ValueError('substep replay simulator dt/control cadence differs from the recorded trace')
    if any(env.get_action_type(action) != 'joint' for action in trace.actions):
        raise ValueError('substep replay currently supports recorded joint actions only')


class PrefixReplayObserver:
    """Retain prefix recognition history, activating only at recorded boundaries.

    Geometry targets are not success gates. Their observers are omitted here;
    native checks, physical recognizers and maintained holds stay unchanged.
    """
    def __init__(self, env, program, selected_stage, env_idx=0):
        self.env, self.program, self.env_idx = env, program, env_idx
        self.limit = [s.id for s in program.stages].index(selected_stage.id)
        self.index = 0;self.evidence = [];self.current = None
        if self.limit:self._activate()

    def _activate(self):
        from dataclasses import replace
        from task.atomic.session import AtomicSession
        stage=replace(self.program.stages[self.index],geometry=(),trajectories=(),selection=None)
        self.current=AtomicSession(self.env,stage,self.env_idx)

    def observe_physics(self):
        if self.current is not None:
            self.current.check_success_only()

    def stage_succeeded(self, stage):
        if self.current is None or self.current.stage.id!=stage.id:
            raise ValueError('prefix observer stage order differs from recorded boundaries')
        self.current.check_success_only()
        success=self.current._qualified_success(self.current.goal_success)
        row=self.current.summary();row['prefix_boundary_verified']=bool(success)
        self.evidence.append(row)
        if success:
            self.index+=1;self.current=None
            if self.index<self.limit:self._activate()
        return success
