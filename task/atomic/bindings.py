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
    counts, evidence, names = {}, deepcopy(program.binding_evidence or {}), {}
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
    gate_ids = {g.id for g in program.gates} | {c.id for c in program.choices}
    def last(ident):
        return ident if ident in gate_ids else names[ident][-1]
    for stage in program.stages:
        for i, ident in enumerate(names[stage.id]):
            stages.append(replace(stage, id=ident, recognition=deepcopy(stage.recognition),
                                  geometry=deepcopy(stage.geometry), maintained_holds=deepcopy(stage.maintained_holds),
                                  trajectories=deepcopy(stage.trajectories), selection=deepcopy(stage.selection)))
            deps[ident] = ([names[stage.id][i-1]] if i else [last(p) for p in old_deps[stage.id]])
    for gate in program.gates:
        deps[gate.id] = [last(p) for p in old_deps[gate.id]]
    choices=[]
    for choice in program.choices:
        deps[choice.id]=[last(p) for p in old_deps[choice.id]]
        choices.append(replace(choice,branches=tuple(tuple(n for ident in branch for n in names[ident]) for branch in choice.branches)))
    expanded = AtomicProgram(program.task_name, tuple(stages), program.instruction,
        program.geometric_instruction, deps, None, program.gates, evidence, tuple(choices))
    return expanded


def expand_label_templates(program, env, env_idx):
    """Instantiate reviewed prefix observers from actual layout labels.

    Each instance is independent; external dependencies on the template expand
    to all instances. This does not resolve language or game roles.
    """
    if not program.label_templates:
        return program
    lm = env.scene_manager.layout_manager
    names, definitions = {}, {}
    evidence = deepcopy(program.binding_evidence or {})
    def substitute(value, token, label):
        if isinstance(value, str):
            return label if value == token else value
        if isinstance(value, dict):
            return {k: substitute(v, token, label) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return type(value)(substitute(v, token, label) for v in value)
        return deepcopy(value)
    for stage in program.stages:
        binding = program.label_templates.get(stage.id)
        if binding is None:
            names[stage.id] = [stage.id]
            definitions[stage.id] = [stage]
            continue
        labels = list(lm.get_labels_by_prefix(prefix=binding['prefix'], env_idx=env_idx))
        if any(not isinstance(label, str) or not label for label in labels):
            raise ValueError('object-label template requires nonempty string labels')
        labels.sort()
        if (len(labels) != len(set(labels)) or not binding['min'] <= len(labels) <= binding['max']
                or any(not isinstance(label, str) or not label for label in labels)):
            raise ValueError('object-label template count/identity does not match reviewed bounds')
        for label in labels:
            name = lm.get_instance_name(env_idx=env_idx, label=label)
            if lm.instance_type_by_env[env_idx].get(name) != binding['category']:
                raise ValueError(f'{label} is not the required {binding["category"]} category')
        instances = []
        for i, label in enumerate(labels, start=1):
            values = {key: substitute(getattr(stage, key), binding['placeholder'], label)
                      for key in ('success_checks', 'geometry', 'recognition', 'maintained_holds', 'trajectories', 'selection')}
            if values == {key: getattr(stage, key) for key in values}:
                raise ValueError('label template placeholder was not used in its stage')
            instances.append(replace(stage, id=f'{stage.id}__label_{i}', **values))
        names[stage.id] = [s.id for s in instances]
        definitions[stage.id] = instances
        evidence[stage.id] = {**deepcopy(binding), 'labels': labels,
                              'instances': dict(zip(names[stage.id], labels))}
    deps = {}
    for ident, parents in program.dependencies().items():
        expanded_parents = [n for p in parents for n in names.get(p, [p])]
        for name in names.get(ident, [ident]):
            deps[name] = expanded_parents.copy()
    return replace(program, stages=tuple(s for stage in program.stages for s in definitions[stage.id]),
                   stage_dependencies=deps, label_templates=None, binding_evidence=evidence)
