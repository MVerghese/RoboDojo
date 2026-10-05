---
name: robodojo-run-benchmark
description: Prepare, run, resume and report RoboDojo atomic geometry suites through the existing imaginaire4 Lepton workflow. Use for overlay packaging, idle GPU admission, collection and evidence-based A/B reporting.
---

# Run and report a RoboDojo benchmark

Read `task/atomic/CONDITIONING_AB.md` sections 4–7 for launch commands and
`task/atomic/README.md` for trace recording/stage replay. Resolve environment
paths and existing run state before creating a new suite or duplicate job.

## Prepare and execute

- Use the imaginaire4 workflow interpreter and a compatible one-task,
  one-episode, seed-0 dry-run base plan. Keep image, checkpoint, inference
  settings and reservation fixed across the comparison. The current suite
  controller only selects reserved L40S nodes; H200 random tasks need another
  launch path.
- Add new first-party runtime files to Git before overlay packaging. The overlay
  packages tracked files from the checkout, which can include uncommitted edits;
  preserve actual archive hashes and review packaged inputs.
- Put raw results on storage with capacity for hundreds-of-MB mesh reports.
  Source archives reused across filesystems are symlinked and must remain present.
- Run `run_suite.py --dry-run`, inspect patched specs, program/overlay hashes and
  pair controls. Dry-run reads the scheduler and needs login; it does not submit.
- Submit only within the user's authorized execution scope. Preserve strict
  reservation and the 512 MiB/two-sample/no-existing-process admission guard.
  Use one controller under a suite-local `flock` and keep its process alive.

## Resume and investigate

- Resume with the same suite, code and run name; submitted bundles are immutable.
  Do not regenerate programs underneath submitted plans.
- A user-authorized priority change uses `--priority-class` for future
  submissions and retains the exact amended spec separately from frozen inputs.
  Lepton permits only `stopped` updates on existing jobs. Replace queued jobs
  under fresh names after stopping and archiving their original records; reuse
  the exact overlay/source/program and preserve inference controls. The runner
  supports a 1–128 submission window, counting queued and executing jobs together;
  select the limit from the user's authorized scope.
- Check job state, controller/monitor logs, collection status and admission
  before classifying a failed case. The controller stops new submissions after
  two infrastructure/collection failures. Preserve failed attempts; retries use
  fresh job names and identical experimental inputs after fixing the cause.
- Existing-memory incidents have memory/neighbor ledgers. Neighbor owners are
  investigation contacts, not confirmed owners of a GPU process; the scheduler
  does not expose UUID/process-to-job assignments. Do not message users unless
  the user authorizes it.

Expanded eval-set runs use `generate_eval_matrix.py` and `EVAL_MATRIX.md`.
The runner retries GPU admission rejections at most twice with exact frozen
inputs and archived evidence. Other failures retain the two-case stop budget.
Archived jobs are terminal. Quiet startup scenes await contact evidence; real
reports and no callback errors are still required for verified A/B comparisons.

## Report

Use `benchmark_results.json`, paired `REPORT.md`, immutable run plans and raw
`eval_report.json`. Verify delivered prompt append, actual layout, runtime and
checkpoint equality, contact health and offline score reproduction. Generic
reports do not independently certify runtime equality across archives.

Separate infrastructure outcome, native task success, atomic recognition,
geometric errors and coverage. A pipeline proof flag does not mean task success
or complete family coverage. Missing contact at a declared event leaves the
interaction unverified; a final goal pass cannot repair it. Publish compact
metrics/provenance, retain raw evidence outside Git, and exclude credentials and
operational job specs from commits.
