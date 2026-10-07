#!/usr/bin/env python3
"""Real pinned websocket/codec/JPEG/demo-runner proof with an infer-only model.

No simulator, GPU, checkpoint or policy quality claim. Install OpenCV and the
pinned protocol dependencies in the interpreter used for this explicit check.
"""
import argparse
import asyncio
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import threading
import time

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO), str(REPO/'XPolicyLab')]
from client_server.ws.model_client import WsModelClient
from client_server.ws.model_server import PolicyServer, PolicyServerConfig
from XPolicyLab.utils.process_data import encode_image_bit
from src.eval_client.checkpoint_client import CheckpointInferenceClient


def validate():
    rgb = np.empty((16,16,3), dtype=np.uint8); rgb[:] = [200,80,30]
    jpeg = encode_image_bit(rgb)
    received = []
    class Model:
        def reset(self): pass
        def infer(self, observation):
            received.append(observation)
            image = observation['vision']['front']['color']
            assert image.shape == (16,16,3) and image.dtype == np.uint8
            assert image[:,:,0].mean() > 150 and image[:,:,2].mean() < 60
            np.testing.assert_array_equal(observation['state']['left_arm_joint_state'], np.arange(6, dtype=np.float32))
            time.sleep(.4)  # synchronous model must not block protocol keepalive
            return {'actions': [
                {'left_arm_joint_state': np.arange(6, dtype=np.float32),
                 'right_arm_joint_state': np.arange(6, dtype=np.float32),
                 'left_ee_joint_state': np.array([.5], dtype=np.float32),
                 'right_ee_joint_state': np.array([.5], dtype=np.float32)} for _ in range(2)]}
    server = PolicyServer(Model(), PolicyServerConfig(host='127.0.0.1', port=0,
        ws_ping_interval_s=.1, ws_ping_timeout_s=.2))
    connections = []; original = server._handle_connection
    async def handle(ws):
        connections.append(time.monotonic()); await original(ws)
    server._handle_connection = handle
    loop = asyncio.new_event_loop(); thread = threading.Thread(target=loop.run_forever, daemon=True)
    thread.start(); raw = None
    try:
        asyncio.run_coroutine_threadsafe(server.start(), loop).result(timeout=5)
        raw = WsModelClient(url=server.url, evaluation_id='checkpoint-rpc-proof', trial_id='t',
            ws_ping_interval_s=.1, ws_ping_timeout_s=.2)
        client = CheckpointInferenceClient(raw)
        path = REPO/'XPolicyLab/policy/demo_policy/deploy.py'
        spec = importlib.util.spec_from_file_location('checkpoint_demo_runner', path)
        runner = importlib.util.module_from_spec(spec); spec.loader.exec_module(runner)
        class Env:
            step = 0
            def is_episode_end(self): return self.step >= 3
            def get_obs(self): return {'env_idx': 0, 'step': self.step,
                'instruction': 'native task; geometric append step '+str(self.step),
                'vision': {'front': {'color': jpeg}},
                'state': {'left_arm_joint_state': np.arange(6, dtype=np.float32)}}
            def take_action(self, action):
                np.testing.assert_array_equal(action['left_arm_joint_state'], np.arange(6, dtype=np.float32))
                assert action['left_ee_joint_state'].dtype == np.float32
                time.sleep(.35)  # caller blocks longer than heartbeat timeout
                self.step += 1
        env = Env(); runner.eval_one_episode(env, client)
        assert len(connections) == 1
        assert len(received) == 2 and [o['step'] for o in received] == [0,2]
        assert received[-1]['instruction'] == 'native task; geometric append step 2'
        return {'passed': True, 'physical_network_connections': len(connections),
            'model_inference_calls': len(received), 'executed_control_actions': env.step,
            'decoded_image_shape': [16,16,3], 'decoded_color_order': 'RGB',
            'native_action_array_dtype': 'float32', 'client': client.summary(),
            'scope': 'real pinned websocket/codec/JPEG and actual demo chunk runner; infer-only toy model; no GPU, checkpoint or simulator validation',
            'bridge_sha256': hashlib.sha256((REPO/'src/eval_client/checkpoint_client.py').read_bytes()).hexdigest(),
            'demo_runner_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    finally:
        if raw: raw.close()
        asyncio.run_coroutine_threadsafe(server.stop(), loop).result(timeout=5)
        loop.call_soon_threadsafe(loop.stop); thread.join(5); loop.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); result = validate()
    args.output.write_text(json.dumps(result, indent=2)+'\n'); print(json.dumps(result))
