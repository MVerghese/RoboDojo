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
    if selected_stage.id not in trace.stage_starts:
        raise ValueError(f'trace has no boundary for stage {selected_stage.id!r}')
    if not dependencies[selected_stage.id] and trace.stage_starts[selected_stage.id] == 0:
        return {'mode': 'initial_scene', 'action_index': 0, 'stage_id': selected_stage.id,
                'state_restoration': False}
    linear = {s.id: ([] if i == 0 else [program.stages[i - 1].id])
              for i, s in enumerate(program.stages)}
    if dependencies != linear:
        raise ValueError('prefix replay currently requires a linear program; graph starts need state restoration')
    if trace.stage_starts.get(stage_ids[0]) != 0:
        raise ValueError('trace must start its first atomic stage at action 0')
    starts = [trace.stage_starts.get(stage_id) for stage_id in stage_ids[:selected_index + 1]]
    if any(start is None for start in starts) or any(later <= earlier for earlier,later in zip(starts,starts[1:])):
        raise ValueError('trace stage boundaries must be present and strictly increasing')
    return {'mode': 'linear_prefix', 'action_index': starts[-1], 'stage_id': selected_stage.id,
            'state_restoration': False, 'scope': 'whole-action prefix replay, not a full simulator snapshot'}


def replay_prefix(program, selected_stage, trace, take_action, stage_succeeded):
    """Replay actions and verify each preceding stage at its recorded boundary.

    ``take_action`` and ``stage_succeeded`` are callbacks so the boundary logic
    can be tested without importing Isaac Sim.
    """
    boundary = validate_start_boundary(program, selected_stage, trace)
    if boundary['mode'] == 'initial_scene':
        return 0
    stage_ids = [stage.id for stage in program.stages]
    selected_index = stage_ids.index(selected_stage.id)
    starts = [trace.stage_starts.get(stage_id) for stage_id in stage_ids[:selected_index + 1]]
    selected_start = starts[-1]
    for action_index, action in enumerate(trace.actions[:selected_start], start=1):
        take_action(action)
        for stage_index in range(selected_index):
            if action_index == starts[stage_index + 1]:
                stage = program.stages[stage_index]
                if not stage_succeeded(stage):
                    raise ValueError(
                        f"replay diverged: stage {stage.id!r} failed at action {action_index}"
                    )
    return selected_start
