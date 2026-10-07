"""Exercise the actual demo runner against an infer-only checkpoint contract."""
import asyncio
from copy import deepcopy
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest

import numpy as np

from src.eval_client.checkpoint_client import CheckpointInferenceClient, configure_policy_client


class Protocol:
    def __init__(self):
        self.requests = []

    async def infer(self, obs, **metadata):
        self.requests.append(('infer', deepcopy(obs), metadata))
        return SimpleNamespace(payload={'actions': [{'target': obs['step']}] * 2})

    async def call(self, method, obs, **metadata):
        self.requests.append((method, deepcopy(obs), metadata))
        return SimpleNamespace(payload={'result': [{'actions': [{'env_idx': o['env_idx']}]} for o in obs]})


class RawClient:
    def __init__(self):
        self._client = Protocol(); self._step = 0
        self.trial_id = 'trial'; self.action_case_id = 'case'; self.repeat_index = 0
        self.calls = []

    def _run(self, coro):
        return asyncio.run(coro)

    def call(self, method, obs=None):
        self.calls.append((method, obs))
        if method == 'reset': self._step = 0


class CheckpointClientTests(unittest.TestCase):
    def test_actual_demo_runner_uses_one_inference_per_chunk_and_keeps_latest_prompt(self):
        path = Path(__file__).resolve().parents[1]/'XPolicyLab/policy/demo_policy/deploy.py'
        spec = importlib.util.spec_from_file_location('checkpoint_demo_runner', path)
        runner = importlib.util.module_from_spec(spec); spec.loader.exec_module(runner)
        class Env:
            step = 0
            def is_episode_end(self): return self.step >= 3
            def get_obs(self): return {'step': self.step, 'instruction': 'native task; geometry at '+str(self.step),
                'state': np.arange(14, dtype=np.float32), 'vision': {'camera': b'encoded-image'}}
            def take_action(self, action): self.step += 1
        raw = RawClient(); client = CheckpointInferenceClient(raw); env = Env()
        runner.eval_one_episode(env, client)
        self.assertEqual(env.step, 3)
        self.assertEqual(raw.calls, [('reset', None)])
        self.assertEqual([r[1]['step'] for r in raw._client.requests], [0, 2])
        self.assertEqual([r[2]['step'] for r in raw._client.requests], [0, 1])
        self.assertEqual(raw._client.requests[-1][1]['instruction'], 'native task; geometry at 2')
        np.testing.assert_array_equal(raw._client.requests[0][1]['state'], np.arange(14))
        self.assertEqual(client.summary()['inference_requests'], 2)

    def test_observation_cache_is_local_immutable_and_cleared_on_reset(self):
        raw = RawClient(); client = CheckpointInferenceClient(raw)
        with self.assertRaisesRegex(ValueError, 'since reset'): client.call('get_action')
        obs = {'step': 4, 'state': np.array([1.])}; client.call('update_obs', obs)
        obs['state'][0] = 99
        self.assertEqual(raw._client.requests, [])
        client.call('get_action')
        self.assertEqual(raw._client.requests[0][1]['state'][0], 1.)
        client.call('reset')
        with self.assertRaisesRegex(ValueError, 'since reset'): client.call('get_action')

    def test_batch_preserves_sparse_environment_identity_and_order(self):
        raw = RawClient(); client = CheckpointInferenceClient(raw)
        client.call('update_obs_batch', [{'env_idx': 8}, {'env_idx': 3}])
        self.assertEqual(client.call('get_action_batch', [3, 8]), [[{'env_idx': 3}], [{'env_idx': 8}]])
        self.assertEqual(raw._client.requests[0][0], 'infer_batch')
        self.assertEqual(client.call('get_action_batch', []), [])
        self.assertEqual(len(raw._client.requests), 1)
        with self.assertRaisesRegex(ValueError, 'matching observations'): client.call('get_action_batch', [7])
        with self.assertRaisesRegex(ValueError, 'unique'): client.call('update_obs_batch', [{'env_idx': 3}]*2)

    def test_wrong_api_runner_and_malformed_chunks_fail_explicitly(self):
        raw = RawClient()
        self.assertIs(configure_policy_client(raw), raw)
        with self.assertRaisesRegex(ValueError, 'demo chunk'): configure_policy_client(raw, 'checkpoint_infer', 'other')
        with self.assertRaises(ValueError): configure_policy_client(raw, 'typo', 'demo_policy')
        for result in ({}, {'actions': []}, {'actions': np.zeros((2,14))}, {'actions': [1]}):
            with self.assertRaises(ValueError): CheckpointInferenceClient._actions(result)


if __name__ == '__main__':
    unittest.main()
