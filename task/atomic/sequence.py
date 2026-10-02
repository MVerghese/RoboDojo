"""Observe atomic manipulation stages throughout an uninterrupted full-task trial."""

from copy import deepcopy

from task.atomic.session import AtomicSession


class AtomicSequence:
    def __init__(self, env, program, env_idx):
        self.env, self.program, self.env_idx = env, program, env_idx
        self.index = 0
        self.completed = {}
        self.stage_starts = {program.stages[0].id: 0}
        self.session = AtomicSession(env, program.stages[0], env_idx)

    def observe_events(self):
        if self.session is not None:
            self.session.observe_events()

    def step(self, action_count):
        if self.session is None or not self.session.step():
            return
        stage = self.program.stages[self.index]
        self.completed[stage.id] = {
            **self.session.summary(), "reached": True,
            "start_action": self.stage_starts[stage.id], "end_action": action_count,
        }
        self.index += 1
        if self.index < len(self.program.stages):
            stage = self.program.stages[self.index]
            self.stage_starts[stage.id] = action_count
            self.session = AtomicSession(self.env, stage, self.env_idx)
        else:
            self.session = None

    def summary(self):
        rows = []
        for index, stage in enumerate(self.program.stages):
            if stage.id in self.completed:
                row = self.completed[stage.id]
            elif index == self.index and self.session is not None:
                row = {**self.session.summary(), "reached": True,
                       "start_action": self.stage_starts[stage.id], "end_action": None}
            else:
                row = {"stage_id": stage.id, "family": stage.family, "instruction": stage.instruction,
                       "conditions": deepcopy(list(stage.geometry)), "reached": False,
                       'recognition': deepcopy(stage.recognition), 'recognition_status': 'not_started',
                       "action_success": False, "geometry_pass_rate": None,
                       "geometry_coverage": 0.0 if stage.geometry else None,
                       "geometry_observed": 0, "geometry_total": len(stage.geometry),
                       "geometry": {}, "start_action": None, "end_action": None}
            rows.append(deepcopy(row))
        return {"task_name": self.program.task_name, "instruction": self.program.instruction,
                'geometric_instruction': self.program.geometric_instruction,
                "stage_starts": deepcopy(self.stage_starts), "stages": rows}
