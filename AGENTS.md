# Working on the atomic geometry benchmark

This fork's work is on `benchmark/atomic-geometry`.

- Start with `task/atomic/CONDITIONING_AB.md` for running/conditioning and
  `task/atomic/ACTION_AUDIT.md` for the implemented-versus-missing boundary.
- `task/atomic/TASK_MAP.md` is generated from `task_catalog.json`; update curated
  entries after inspecting native source, then run
  `python scripts/atomic/task_catalog.py --refresh` and `--check`.
- Repository workflows are in `.agents/skills/`. Use the applicable skill for
  action audits, pair design or execution/collection.
- `task/atomic/CONDITIONING_AUDIT.md` and `conditioning_audit.json` record every
  taxonomy slot/factor cell. After reviewing changed conditioning source or
  taxonomy, run `python scripts/atomic/conditioning_audit.py --refresh` and `--check`.
- Simulator task imports require Isaac Sim. Host checks use AST source reads,
  program loading and `python -m unittest discover -s tests -p 'test_atomic*.py'`.
  Add new runtime files to Git before testing overlay completeness/packaging.
- Keep bulky rollout evidence, credentials and operational job specs outside
  Git. A source audit, schema test or pipeline completion does not establish
  observed action recognition or policy steerability.
