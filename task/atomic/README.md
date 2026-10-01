# Atomic geometry benchmark prototype

This branch adds a separate evaluation mode on top of RoboDojo's existing full-task eval. Its [taxonomy](TAXONOMY.md) defines 11 manipulation families and five geometric modifier types. The [task map](TASK_MAP.md) sketches how all 54 task modules decompose. Five executable programs are included in `programs/`.

## What runs today

- A program JSON defines named atomic stages, an instruction, existing RoboDojo success predicates, and geometric conditions on typed slots.
- Geometry conditions report continuous error and pass/fail for a point, SE(3) pose, landmark-relative displacement, landmark-relative orientation, or spatial relation.
- `AtomicSession` measures first object lift/motion at physics-step resolution and stage success after each policy action chunk. The result keeps **action success** and **geometry adherence** separate in `eval_result.details[*].atomic`. `geometry_pass_rate` is null until a condition is observed; `geometry_coverage` reports how many conditions fired.
- A `first_predicate` event can capture geometry when any or all read-only RoboDojo predicates first become true at a physics step. The `pour_balls_into_vase` program uses this to measure cup placement when the first ball enters the vase.
- A normal evaluation can record policy action traces and automatically mark stage starts for an executable program. Atomic mode resets the original layout, replays the action prefix, verifies preceding stage predicates at the recorded boundaries, starts a fresh stage scoring window, and stops when the selected atomic success checks pass or its step limit expires.
- A variant JSON changes expected geometry, tolerances, references, event, and instruction while keeping the same stage success checks. This permits paired counterfactual trials.

## Program format

See [`deposit_coin.json`](programs/deposit_coin.json) for a two-stage example. Each stage has an `id`, `family`, `instruction`, `success_checks`, and `geometry`. A geometry entry has an `id`, `slot`, one of the five `kind` values, an `expected` value, `tolerance`, `measurement`, optional `reference`, and an `event`. All poses are environment-local with scalar-first quaternions. `relative_displacement` is expressed in the reference object's frame. Spatial directional relations use x right, y forward, z up in that frame. Values must be selected from feasible geometry for the task and calibrated against the chosen object asset.

The included grasp and push examples measure the **nearest robot end-effector link pose as a proxy** at first lift/motion. They do not claim to recover the exact finger-object contact patch. A benchmark cell requiring exact contact needs PhysX contact reporting and a contact-point resolver.

## Record, annotate, run

Run a normal RoboDojo evaluation with the usual policy server and append `--atomic_record_dir /path/to/traces --atomic_record_spec task/atomic/programs/deposit_coin.json` to `scripts/eval_policy.sh`. This writes one JSON trace per episode, marking stage starts when each predicate first succeeds at a policy action boundary. For a task without an executable program, use `--atomic_record_dir` alone and annotate a successful trace manually; for `deposit_coin`, for example:

When launching through `scripts/robodojo.sh client`, set `ATOMIC_RECORD_DIR` and `ATOMIC_RECORD_SPEC` in the simulator environment. The client forwards them to `eval_policy.sh`. The Lepton trace capture helper is `scripts/atomic/submit_trace.py`; it overlays this fork onto the existing RoboDojo image and writes traces into the result archive.

The overlay includes all Git-tracked first-party runtime files in `env`, `env_cfg`, `src`, `task`, `utils`, and `scripts` so the evaluator and its dependencies come from the same checkout. Add new runtime files to Git before packaging. Assets and submodule installations come from the image. Safe startup imports are checked before initializing the policy; local submission tests verify that runtime Python imports are included in the archive.

The startup check also validates the evaluator's WebSocket client options against the installed XPolicyLab constructor without connecting to a server. Images with older clients omit the two default keepalive options they do not accept. Custom keepalive values require a client that supports them and fail explicitly on older images.

For a capture requiring an idle GPU, add `--max-initial-gpu-memory-mib 512` to both the dry-run and actual `submit_trace.py` invocation. Before policy loading, the job checks memory twice, rejects existing compute processes, and allows up to 512 MiB for driver/display overhead. It publishes `gpu_admission.json` immediately. A rejected placement exits with code 78 and publishes a failed evaluation report and diagnostic archive without loading the policy.

The monitor saves admission measurements to `<run-dir>/gpu_admission.json` and appends each measured placement to `<run-dir-parent>/gpu-memory-observations.jsonl`. Adjacent `.summary.json` and `.md` files count affected placements and distinct GPU UUIDs. Use `--gpu-memory-ledger` to choose another persistent log. Repeated monitor observations are deduplicated by job, replica, and GPU UUID.

When admission detects existing GPU memory or compute processes, the monitor also snapshots the node's workloads and looks up neighboring job owners/creators, replica IDs, allocated GPU counts, and requested privileged mode. It saves `<run-dir>/gpu_node_neighbors.json` and a cumulative `gpu-node-neighbors.jsonl` / `.md` contact report beside the memory ledger. Incident and snapshot times show the collection delay. Only the three GPU scope environment variables are retained from job specs; commands and other environment values are excluded. Missing scope variables do not establish missing runtime isolation. The scheduler API does not expose GPU UUID assignments or process-to-job mappings, so neighboring users are contacts for investigation, rather than confirmed owners of the unexpected allocation. Keep the monitor running to capture neighbors while the incident is current.

After submission, `scripts/atomic/monitor_trace.py --run-dir <run-dir> --credentials-file <credentials>` polls the Lepton job every 30 seconds for up to 24 hours. It logs state changes to `<run-dir>/monitor.jsonl` and invokes the trace collector after termination. The monitor is a running process and must remain alive until collection finishes. Submission verifies that the configured checkpoint's `model/.metadata` is accessible before uploading or creating a GPU job.

```json
"stage_starts": {"pick_coin": 0, "insert_coin": 37}
```

The index `37` means replay actions `0..36`, then ask the policy to perform `insert_coin`. The trace's `layout_id` must match the saved RoboDojo layout. The first stage can run without a trace. For a later stage, supply all three arguments to the normal eval launcher:

```text
--atomic_spec task/atomic/programs/deposit_coin.json
--atomic_stage insert_coin
--atomic_trace /path/to/annotated_trace.json
```

To vary a geometric target, add `--atomic_variant /path/to/variant.json`. The example [`push_T_right_contact.json`](programs/variants/push_T_right_contact.json) changes the requested end-effector contact offset and atomic instruction. The launcher forwards these flags to `src/eval_client/main.py` and forces one environment and one trial in atomic mode.

For `scripts/robodojo.sh client`, use the corresponding `--atomic-spec`, `--atomic-stage`, `--atomic-trace`, and `--atomic-variant` flags. In a Lepton pod these can instead be set with `ATOMIC_SPEC`, `ATOMIC_STAGE`, `ATOMIC_TRACE`, and `ATOMIC_VARIANT`; all paths must exist inside the pod. Atomic settings require one `--task`. A full-task annotation program (`ATOMIC_RECORD_SPEC`) cannot be combined with atomic evaluation, but `ATOMIC_RECORD_DIR` alone can record the selected stage.

To submit a later-stage Lepton evaluation, first prepare a fresh one-episode i4 dry-run plan for the program's task. Then package the program and captured trace into its overlay:

```bash
python scripts/atomic/submit_stage.py \
  --run-dir /path/to/fresh-run \
  --program task/atomic/programs/pour_balls_into_vase.json \
  --stage pour_balls \
  --trace /path/to/captured-trace.json \
  --reservation cosmos-rollout-luemzvvo \
  --dry-run
```

Add `--variant /path/to/variant.json` for a conditioned trial. Review the patched job spec and overlay, then omit `--dry-run` and supply `--credentials-file`. The helper rejects mismatched tasks and missing or unordered prefix boundaries, stages all inputs inside the pod, and records their SHA256 values in `atomic_settings.json` and the submitted run plan. Replay success and geometric adherence still require validation in Isaac Sim.

Stage jobs also record the selected stage's action trace for collection by the monitor. Add `--max-initial-gpu-memory-mib 512` to require the same idle-GPU check as a full-task capture.

Stage recording currently requires predicates that are meaningful relative to the full episode start. A later-stage `is_moved` check relative to that baseline can fire before the intended action; such tasks need a stage-local predicate or a manual boundary. Successful full-task traces remain necessary to produce later-stage start states.

## Existing Lustre demonstrations

The cluster has a 112 GB simulated RoboDojo LeRobot dataset at `/lustre/fsw/portfolios/cosmos/projects/cosmos_base_training/cosmos3_action_datasets/robodojo_20260907/robodojo_sim_joint/arx_x5`. Its metadata lists 3,500 episodes, 35 tasks, 25 fps joint actions, and three video streams. These demonstrations are useful for inspecting motion and choosing geometric targets. Their episode records contain task text and frame ranges but no RoboDojo saved-layout ID or simulator object state, so they cannot directly serve as deterministic start-state traces for this eval harness. The trace recorder above produces the needed layout-linked action prefix.

## Remaining work and validation needs

- The map is complete as an inventory, but only the five listed programs are executable. Each remaining task needs grounded labels, independent stage predicates, and action-boundary annotations. Some tasks require auxiliary states, such as an opponent move or a held stabilizing object.
- Recorded action prefixes are replayed through the simulator. Determinism and state fidelity, especially for garments and fluids, must be checked in Isaac Sim. This workspace has no Isaac Sim, NVIDIA driver, or `Assets`, so only schema, math, and mock session tests run here.
- Exact grasp and tool-contact geometry requires simulator contact points; the current end-effector link estimate is a named proxy in each result (`ee_contact_proxy: true`).
- Geometric variants must remain physically feasible. A final-pose variant that conflicts with a stage's fixed success predicate is invalid; choose a success predicate that represents the action independently of the changed geometry.

Run the local tests with `python3 -m unittest discover -s tests -p 'test_atomic_benchmark.py' -v`.
