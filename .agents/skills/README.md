# Agent workflows for this fork

These repository skills capture the benchmark's non-obvious invariants and route
to maintained documentation. Each directory contains a `SKILL.md` entrypoint:

| Skill | Use |
| --- | --- |
| [robodojo-atomic-audit](robodojo-atomic-audit/SKILL.md) | Source-backed action/measurement audits and new recognizers |
| [robodojo-condition-ab](robodojo-condition-ab/SKILL.md) | Geometric definitions, prompts and matched experiment design |
| [robodojo-run-benchmark](robodojo-run-benchmark/SKILL.md) | Lepton preparation, execution, resume, collection and reporting |

Example requests: “Use `$robodojo-atomic-audit` to audit xylophone strikes”,
“Use `$robodojo-condition-ab` to create a matched pouring pair”, and
“Use `$robodojo-run-benchmark` to collect and report this authorized suite”.
An agent can read these files directly; environments using a separate skill
directory can install/copy the desired directories there. Paths in skill bodies
are relative to the RoboDojo checkout root, not the skill directory.
