"""Tool strokes require real holds/motion, but no preceding vertical pickup."""
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
import numpy as np
from task.atomic.sequence import AtomicSequence
from task.atomic.spec import AtomicProgram
from test_atomic_physical_runtime import World

PROGRAM=Path(__file__).resolve().parents[1]/'task/atomic/programs/align_blocks.json'


class ToolPushRootTests(unittest.TestCase):
    def world(self):
        w=World()
        w.env._atomic_surfaces=NS(center_pose=lambda label,env_idx,pose:pose.copy())
        original=w.contacts.resolve_object_pair
        def pair(selector,env_idx):
            _,source=original(selector,env_idx)
            return {'position':[0,0,0],'points':[[0,0,0]]},source
        w.contacts.resolve_object_pair=pair
        for i in range(3):w.poses[f'cube{i}']=np.asarray([.05*i,0,0,1,0,0,0],dtype=float)
        p=AtomicProgram.load(PROGRAM);seq=AtomicSequence(w.env,p,0)
        return w,p,seq

    def tick(self,w,seq):
        w.contacts.steps+=1;seq.observe_events();seq.step(w.contacts.steps)

    def test_supported_held_stroke_is_observed_without_any_tool_lift(self):
        w,p,seq=self.world()
        self.assertFalse(p.stages[0].required)
        self.assertEqual(set(seq.sessions),{'pick_target','tool_push_cube0','tool_push_cube1','tool_push_cube2'})
        w.hold(label='target');w.contacts.pairs=True
        self.tick(w,seq);self.tick(w,seq)
        w.poses['target'][0]+=.01;w.poses['cube0'][0]+=.01
        self.tick(w,seq)
        self.assertIn('tool_push_cube0',seq.completed)
        self.assertNotIn('pick_target',seq.completed)
        self.assertEqual(w.poses['target'][2],0)
        self.assertTrue(seq.completed['tool_push_cube0']['action_success'])

    def test_direct_finger_block_motion_cannot_become_tool_motion(self):
        w,p,seq=self.world();w.hold(label='cube0');w.contacts.pairs=True
        self.tick(w,seq);w.poses['target'][0]+=.02;w.poses['cube0'][0]+=.02
        self.tick(w,seq);self.tick(w,seq)
        self.assertNotIn('tool_push_cube0',seq.completed)
        self.assertFalse(seq.sessions['tool_push_cube0'].interaction_observed)


if __name__=='__main__':unittest.main()
