"""Observed requirement counters, separate from success and geometric scores."""
from copy import deepcopy


def record_requirements(d, step, action_index, gates, measurements):
    """Record distinct sampled steps. None means not evaluated, not false."""
    if d.get('last_physics_step') == step:
        return
    d.setdefault('sampled_steps', 0)
    d.setdefault('first_physics_step', step)
    d.setdefault('gate_counts', {})
    d.setdefault('sampling_discontinuities', 0)
    if 'last_physics_step' in d and step != d['last_physics_step'] + 1:
        d['sampling_discontinuities'] += 1
    d['sampled_steps'] += 1
    d['last_physics_step'] = step
    for name, value in gates.items():
        counts = d['gate_counts'].setdefault(name, {'true': 0, 'false': 0, 'not_evaluated': 0})
        counts['not_evaluated' if value is None else 'true' if value else 'false'] += 1
    d['current'] = {'physics_step': step, 'policy_action_index': action_index,
                    'gates': deepcopy(gates), 'measurements': deepcopy(measurements)}
    d['scope'] = 'observed physical requirements; absence alone does not establish policy failure'
