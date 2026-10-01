from isaaclab.envs.direct_rl_env import DirectRLEnv


class CustomDirectRLEnv(DirectRLEnv):
    def sim_step(self, render: bool = True):
        is_rendering = self.sim.has_gui() or self.sim.has_rtx_sensors()

        for _ in range(self.cfg.decimation):
            contacts = getattr(self, 'atomic_contact_buffer', None)
            if contacts is not None:
                contacts.begin_step()
            self._sim_step_counter += 1
            self.scene.write_data_to_sim()
            self.sim.step(render=False)
            if (
                self.cfg.sim.render_interval > 0
                and self._sim_step_counter % self.cfg.sim.render_interval == 0
                and is_rendering
                and render
            ):
                self.sim.render()
            self.scene.update(dt=self.physics_dt)
            observer = getattr(self, 'atomic_physics_observer', None)
            if observer is not None:
                observer()

        self.episode_length_buf += 1
        self.common_step_counter += 1

        if self.cfg.events:
            if "interval" in self.event_manager.available_modes:
                self.event_manager.apply(mode="interval", dt=self.step_dt)

        return self.extras
