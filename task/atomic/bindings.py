"""Resolve explicit repeat counts and annotated joint identities from a layout."""
from copy import deepcopy
from dataclasses import replace


def joint_from_tag(env, label, tag, env_idx):
    metadata = env.scene_manager.layout_manager.get_instance_metadata(env_idx=env_idx, label=label)
    item = (metadata or {}).get('passive', {}).get('functional', {}).get(tag)
    joints = item.get('parent_joint') if item else None
    if isinstance(joints, str):
        joints = [joints]
    if not isinstance(joints, (list, tuple)) or len(joints) != 1 or not isinstance(joints[0], str):
        raise ValueError(f'{label}:{tag} must annotate exactly one moving control joint')
    return joints[0]


def expand_repeats(program, env, env_idx):
    """Expand reviewed stage templates using numeric asset model IDs, not labels.

    Each parent dependency becomes the last instance of its repeated stage.
    Counts are bounded explicitly. No instruction prose is interpreted.
    """
    if not program.repeat_counts:
        return program
    from task.atomic.spec import AtomicProgram
    counts, evidence, names = {}, {}, {}
    lm = env.scene_manager.layout_manager
    for stage in program.stages:
        binding = program.repeat_counts.get(stage.id)
        if binding:
            metadata = lm.get_instance_metadata(env_idx=env_idx, label=binding['label'])
            raw = (metadata or {}).get('model_id')
            if isinstance(raw, str) and raw.isdecimal():
                raw = int(raw)
            if type(raw) is not int or not binding['min'] <= raw <= binding['max']:
                raise ValueError(f'repeat count for {stage.id} is not a bounded numeric model_id: {raw!r}')
            count = raw
            evidence[stage.id] = {'label': binding['label'], 'model_id': raw, 'count': count}
        else:
            count = 1
        counts[stage.id] = count
        names[stage.id] = ([f'{stage.id}__{i+1}' for i in range(count)] if binding else [stage.id])
    stages, deps = [], {}
    old_deps = program.dependencies()
    gate_ids = {g.id for g in program.gates}
    def last(ident):
        return ident if ident in gate_ids else names[ident][-1]
    for stage in program.stages:
        for i, ident in enumerate(names[stage.id]):
            stages.append(replace(stage, id=ident, recognition=deepcopy(stage.recognition),
                                  geometry=deepcopy(stage.geometry), maintained_holds=deepcopy(stage.maintained_holds)))
            deps[ident] = ([names[stage.id][i-1]] if i else [last(p) for p in old_deps[stage.id]])
    for gate in program.gates:
        deps[gate.id] = [last(p) for p in old_deps[gate.id]]
    expanded = AtomicProgram(program.task_name, tuple(stages), program.instruction,
        program.geometric_instruction, deps, None, program.gates, evidence)
    return expanded
