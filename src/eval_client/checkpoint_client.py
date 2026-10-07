"""Explicit bridge from RoboDojo's chunk runner to an infer-only checkpoint.

The pinned XPolicyLab client forwards arbitrary method calls to the model.
RoboDojo's demo runner uses update_obs/get_action, while Cosmos exposes infer.
Cache observations locally and make one inference request per requested chunk.
The pinned protocol, codec, background loop and reconnect logic stay intact.
"""
from collections.abc import Mapping
from copy import deepcopy


class CheckpointInferenceClient:
    def __init__(self, client):
        if not callable(getattr(getattr(client, '_client', None), 'infer', None)):
            raise ValueError('checkpoint_infer requires the pinned inference protocol client')
        self.client = client
        self.observation = None
        self.batch = None
        self.observation_updates = 0
        self.inference_requests = 0

    def __getattr__(self, name):
        return getattr(self.client, name)

    @staticmethod
    def _actions(result):
        if not isinstance(result, Mapping) or 'actions' not in result:
            raise ValueError('checkpoint inference response must contain native actions')
        actions = result['actions']
        if not isinstance(actions, (list, tuple)) or not actions or not all(isinstance(a, Mapping) for a in actions):
            raise ValueError('checkpoint inference must return a nonempty native action chunk')
        return actions

    def call(self, func_name=None, obs=None, **kwargs):
        if kwargs:
            raise TypeError('checkpoint client only accepts func_name and obs')
        if func_name == 'reset':
            self.observation = self.batch = None
            self.observation_updates = self.inference_requests = 0
            return self.client.call(func_name, obs)
        if func_name == 'update_obs':
            if not isinstance(obs, Mapping):
                raise TypeError('update_obs requires a native observation mapping')
            self.observation = deepcopy(obs)
            self.observation_updates += 1
            return None
        if func_name == 'update_obs_batch':
            if not isinstance(obs, list) or not all(isinstance(o, Mapping) for o in obs):
                raise TypeError('update_obs_batch requires native observation mappings')
            indices = [o.get('env_idx') for o in obs]
            if any(type(i) is not int or i < 0 for i in indices) or len(set(indices)) != len(indices):
                raise ValueError('batch observations require unique nonnegative integer env_idx')
            self.batch = dict(zip(indices, deepcopy(obs)))
            self.observation_updates += 1
            return None
        if func_name == 'get_action':
            if obs is not None:
                raise TypeError('get_action takes no observation payload')
            if self.observation is None:
                raise ValueError('get_action requires an observation since reset')
            raw = self.client
            response = raw._run(raw._client.infer(self.observation,
                trial_id=raw.trial_id, action_case_id=raw.action_case_id,
                repeat_index=raw.repeat_index, step=raw._step))
            actions = self._actions(response.payload)
            raw._step += 1
            self.inference_requests += 1
            return actions
        if func_name == 'get_action_batch':
            if (not isinstance(obs, list) or any(type(i) is not int or i < 0 for i in obs)
                    or len(set(obs)) != len(obs)):
                raise ValueError('get_action_batch requires unique environment indices')
            if not obs:
                return []
            if self.batch is None or any(i not in self.batch for i in obs):
                raise ValueError('get_action_batch requires matching observations since reset')
            raw = self.client
            response = raw._run(raw._client.call('infer_batch', [self.batch[i] for i in obs],
                trial_id=raw.trial_id, action_case_id=raw.action_case_id,
                repeat_index=raw.repeat_index, step=raw._step))
            results = response.payload.get('result')
            if not isinstance(results, list) or len(results) != len(obs):
                raise ValueError('checkpoint batch result must preserve the requested environment count')
            actions = [self._actions(result) for result in results]
            if len({len(chunk) for chunk in actions}) != 1:
                raise ValueError('checkpoint batch chunks must have the same length')
            raw._step += 1
            self.inference_requests += 1
            return actions
        if func_name in ('prepare_case', 'trial_end'):
            return self.client.call(func_name, obs)
        raise ValueError(f'unsupported checkpoint runner method {func_name!r}')

    def summary(self):
        return {'api': 'checkpoint_infer', 'observation_updates': self.observation_updates,
                'inference_requests': self.inference_requests,
                'cadence': 'one inference request per action chunk; intermediate observations cached locally'}


def configure_policy_client(client, api=None, policy_name=None):
    if api in (None, '', 'native'):
        return client
    if api != 'checkpoint_infer' or policy_name != 'demo_policy':
        raise ValueError('checkpoint_infer is supported only with the RoboDojo demo chunk runner')
    return CheckpointInferenceClient(client)
