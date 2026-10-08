# Atomic geometry benchmark prototype

This branch adds a separate evaluation mode on top of RoboDojo's existing full-task eval. Its [taxonomy](TAXONOMY.md) defines 11 manipulation families and five geometric modifier types. The [source-backed task map](TASK_MAP.md) audits all 54 task modules with concrete action examples and native predicate evidence. Eleven schema-loadable program files for ten tasks are included in `programs/`; four original programs were exercised by the live pilot. See [RUNTIME.md](RUNTIME.md) for the new dependency runtime and generic physical recognizers, which have offline coverage only. [Advanced runtime](ADVANCED_RUNTIME.md) covers selection, paths, choices, strikes and material state. The deposit-coin insertion landmark remains a gap.

Start with [conditioning and A/B instructions](CONDITIONING_AB.md), [all-family audit](ACTION_AUDIT.md), [completed pilot results](PILOT_RESULTS.md), and [agent workflow skills](../../.agents/skills/README.md).

Implementation details:

The [expanded eval matrix](EVAL_MATRIX.md) documents the 49-task partial-observer
screen, checkpoint mappings, bounded idle-GPU retries and aggregate validity.

1. [Geometric instrumentation and eval measurements](GEOMETRIC_MEASUREMENT.md):
   all selectors, five modifier checks, sampling events, paths and selection.
2. [Atomic action success checks](ATOMIC_SUCCESS.md): each family/recognizer,
   completion rules and endpoint-only program exceptions.
3. [Action recognition and segmentation](RECOGNITION_SEGMENTATION.md): activation,
   physical events, dependencies, repeats/choices, saved boundaries and restarts.

The [conditioning coverage matrix](CONDITIONING_AUDIT.md) audits every action slot
against all five factors, with implementation gaps and exact live evidence.

The [all-task segmentation investigation](SEGMENTATION.md) supplies candidate
plans for all 54 modules: object bindings, independent/ordered stages,
repetitions, choices, maintained holds, physical recognition boundaries and
restart state requirements. These source plans are not executable programs or
observed trace labels. Inspect one with
`python scripts/atomic/segmentation_plans.py --task press_by_number`.

## What runs today

- A program JSON defines named atomic stages, an instruction, existing RoboDojo success predicates, and geometric conditions on typed slots.
- Pick/push stages now also require an explicit `recognition` definition, separate
  from geometry. Contact-held motion must span distinct consecutive physics
  steps; a pick must achieve the full native lift within that held interval
  and still be held when its endpoint goal is satisfied. Push requires named
  upward force-bearing support and planar motion.
  Removing geometry cannot remove this requirement. The updated programs use
  two contact steps and a 2.5 cm pick / 1 cm push motion threshold. These new
  rules have local regression coverage; the published pilot used the earlier
  event-contact rule and is not live validation of the update.
- A reference selector can specify `"time": "stage_start"` to freeze its actual
  pose (and rigid footprint for object relations). This supports lift/goal
  offsets without a moving self-reference. `on_top` requires live support.
  Initial candidate selection uses a separate snapshot/contact observer; full
  simulator restoration remains unimplemented.
- `object_contact_points` with `label` and `other_label` measures actual
  force-bearing tool/object pairs. A `first_contact` event accepts a contact
  `measurement` selector and records the physical event evidence, even when
  the scored measurement is a separate object pose. Physical recognition comes
  from separate held-tool/contact/motion state machines. Held-tool contact/push,
  pre-impact speed/retraction and transfer state machines now exist offline;
  live active-part/path calibration, natural rebound and musical timing remain gaps.
- Geometry conditions report continuous error and pass/fail for a point, SE(3) pose, landmark-relative displacement, landmark-relative orientation, or spatial relation.
- `AtomicSession` measures events and physical completion at physics-step resolution,
  with additional checks after each policy action chunk. The result keeps **action
  success** and **geometry adherence** separate in `eval_result.details[*].atomic`.
  Fresh `stage_success` geometry uses the same qualified physical completion gate
  as action success; historical endpoint-only snapshots retain partial evidence.
  See [measurement semantics](GEOMETRIC_MEASUREMENT.md).
  `geometry_pass_rate` is null until a condition is observed; `geometry_coverage`
  reports how many conditions fired.
- A `first_predicate` event can capture geometry when any or all read-only RoboDojo predicates first become true at a physics step. The `pour_balls_into_vase` program uses this to measure cup placement when the first ball enters the vase.
- A normal evaluation can record policy action traces and automatically mark stage starts for an executable program. Atomic mode resets the original layout, replays the action prefix, verifies preceding stage predicates at the recorded boundaries, starts a fresh stage scoring window, and stops when the selected atomic success checks pass or its step limit expires.
- A variant JSON changes expected geometry, tolerances, references, event, and instruction while keeping the same stage success checks. Changing targets permits different-target steering trials. With/without-prompt A/B pairs instead keep all geometry and success checks identical.
- A recording program can include a top-level `instruction` for an uninterrupted full-task benchmark. The policy receives that task-wide instruction throughout the episode. `AtomicSequence` records stage boundaries and geometric events without terminating the episode or replacing RoboDojo's native reward/cleanup checks. Results are stored in `details[*].atomic_sequence`.
- Each observed score saves its full condition, raw measurement and landmark state, resolved robot arm/link, and policy action index. Units and quaternion order are explicit in the atomic summary. The collector preserves `eval_report.json` and writes `atomic-score-audit.json`, which recomputes the scores from this raw evidence. Earlier runs without these fields are marked `missing_raw_evidence`.

## Program format

See [`deposit_coin.json`](programs/deposit_coin.json) for a two-stage example. Each stage has an `id`, `family`, `instruction`, `success_checks`, and `geometry`. A geometry entry has an `id`, `slot`, one of the five `kind` values, an `expected` value, `tolerance`, `measurement`, optional `reference`, and an `event`. All poses are environment-local with scalar-first quaternions. `relative_displacement` is expressed in the reference object's frame. Spatial directional relations use x right, y forward, z up in that frame. Values must be selected from feasible geometry for the task and calibrated against the chosen object asset.

The included grasp and push examples now use **force-bearing PhysX finger/object contact points** at first lift/motion. Grasps require two distinct finger bodies of the same arm. Each contact is scored; its centroid cannot hide incorrect contacts. Missing contact evidence is recorded explicitly, without an end-effector fallback. See the [instrumentation audit](INSTRUMENTATION_AUDIT.md) for the geometry, event, and action-recognition definitions.

## Four-task paired pilot

`scripts/atomic/generate_paired_suite.py --output-dir /path/to/suite` generates eight
fresh full-task cases: native and explicitly geometrically conditioned prompts
for general pickup, push T, pour balls, and plug in charger. A top-level
`geometric_instruction` appends constraints to the native object-resolved task
instruction. Scoring targets are identical within each pair. Results retain
`policy_prompt_history`, contact instrumentation health, raw geometric evidence,
atomic success, and native full-task success.

## End-to-end single-task suite

`scripts/atomic/generate_suite.py --output-dir /path/to/suite` generates 21 full-task cases for `pour_balls_into_vase`: a baseline plus two settings for each of five modifier types on each of `pick_cup` and `pour_balls`. This is an exploratory different-target sweep; use `generate_ab_suite.py` or the four-task pair generator for controlled with/without-prompt comparisons. Each conditioned case changes one action's geometric condition and appends the matching request to the task-wide policy instruction. The original seven-ball transfer, upright-cup, and arm-return criteria remain the full-task success condition. The captured layout-zero trace observed the pick boundary at action 45; it did not complete the full pour. The suite reruns the complete task from the beginning and does not replay that trace or infer an unobserved place action.

All candidate targets and instructions are saved in `suite.json` and per-case program files. Position and pose values explicitly use the named cup/vase frame. Candidate targets require live feasibility calibration; a poor policy score does not invalidate the integration run. A case requesting an orientation still uses the same atomic success predicate as its baseline.

Conditions with `track_closest:true` can record `closest_approach` at policy action boundaries. Audited paired programs and generated exploratory cases disable it to keep event evidence and storage focused. It is **not** substituted for event adherence or included in the event pass rate. Unreached stages and unobserved events remain explicit.

Prepare/review the suite using an existing one-episode i4 source plan:

```bash
python scripts/atomic/run_suite.py \
  --suite /path/to/suite/suite.json \
  --base-run /path/to/existing-capture-run \
  --credentials-file /path/to/credentials \
  --name rb-pour-e2e \
  --max-concurrent 4 \
  --gpu-memory-ledger /path/to/gpu-memory-observations.jsonl \
  --dry-run
```

Remove `--dry-run` to submit up to four independent one-GPU trials concurrently, collect each episode, verify raw-state score reproduction, and update `benchmark_results.json` / `.md`. The controller resumes submitted plans and stops further submissions after two collection/infrastructure failures so a broken simulator does not consume the whole matrix. Failed task/action predicates remain valid benchmark results. GPU admission and neighbor-owner evidence are collected for every affected placement; concurrent ledger writers use file locks.

The standalone capture helper accepts `--program /path/to/full-task.program.json` for a single full-task case. Existing annotation programs without a task-wide instruction preserve the policy's original task instruction while now retaining atomic geometry scores.

## Steerability pilot

`variants/pick_cup_positive_x.json` and `variants/pick_cup_negative_x.json` request **every force-bearing finger contact** in +4 cm and -4 cm local-x bands relative to the cup mesh-bounds centre. Both explicitly score `axes:[0]` with a 3 cm tolerance and leave other contact coordinates unrestricted; the positive 1–7 cm and negative -7–-1 cm bands do not overlap. Run both as `pick_cup` stage trials on the same layout/checkpoint. At the first 2.5 cm cup lift, compare each result against its requested target and the opposite target. The stage instruction replaces the observation's `instruction`, which the demo policy adapter sends to the server and the Cosmos observation composer uses as `prompt`.

These are uncalibrated candidates. Inspect cup geometry and actual opposing contacts to determine whether either band is physically feasible. The base cup program scores z, so switching to these x variants requires new simulator trials. Offline opposite-target scoring is valid between runs using the same x measurement/axis definitions. One paired episode checks integration, not statistical steerability. A missing lift event yields zero coverage and no geometric score.

To audit a collected trial against its original target and the opposite target:

```bash
python scripts/atomic/audit_scores.py \
  --report /path/to/run/eval_report.json \
  --variant task/atomic/programs/variants/pick_cup_negative_x.json \
  --output /path/to/run/opposite-target-scores.json
```

Rescoring an outcome does not test policy response to the new instruction; that requires the second simulator trial. Offline rescoring permits only target/tolerance changes. Changing the measurement, landmark, or event requires a fresh run.

For automatic opposite-target scoring after a Lepton trial, pass the opposite variant path to the monitor's `--counterfactual-variant` flag. It writes `opposite-target-scores.json` after the regular trace and score audit are collected.

## Record, annotate, run

Run a normal RoboDojo evaluation with the usual policy server and append `--atomic_record_dir /path/to/traces --atomic_record_spec task/atomic/programs/deposit_coin.json` to `scripts/eval_policy.sh`. This writes one JSON trace per episode, recording stage activation/completion at synchronized physics substeps. Only whole-action starts enter the replayable `stage_starts` map; precise `stage_boundaries` also records mid-chunk starts. See RUNTIME.md for graph and replay limits. For a task without an executable program, use `--atomic_record_dir` alone and annotate a successful trace manually; for `deposit_coin`, for example:

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

The index `37` means replay actions `0..36`, then ask the policy to perform `insert_coin`. The trace's `layout_id` must match the saved RoboDojo layout. Any concrete root without dependencies can run without a trace. For a later linear stage, supply all three arguments to the normal eval launcher:

```text
--atomic_spec task/atomic/programs/deposit_coin.json
--atomic_stage insert_coin
--atomic_trace /path/to/annotated_trace.json
```

To vary a geometric target, add `--atomic_variant /path/to/variant.json`. The example [`push_T_right_contact.json`](programs/variants/push_T_right_contact.json) changes the requested finger-contact region and atomic instruction. The launcher forwards these flags to `src/eval_client/main.py` and forces one environment and one trial in atomic mode.

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

- The map is complete as an inventory, but only the five listed programs have explicit stage definitions; four have live pilot evidence and not all stages were reached. Each remaining task needs grounded labels, independent stage predicates, and action-boundary annotations. Some tasks require auxiliary states, such as an opponent move or a held stabilizing object.
- Recorded action prefixes are replayed through the simulator. Determinism and state fidelity, especially for garments and fluids, must be checked in Isaac Sim. This workspace has no Isaac Sim, NVIDIA driver, or `Assets`, so only schema, math, and mock session tests run here.
- Direct grasp/push geometry uses PhysX manifold contacts. Tool contact and articulated-contact frame definitions need grounded body selectors before their taxonomy templates become executable. Historical results marked `ee_contact_proxy: true` retain their original interpretation.
- Geometric variants must remain physically feasible. A final-pose variant that conflicts with a stage's fixed success predicate is invalid; choose a success predicate that represents the action independently of the changed geometry.

Run the local tests with `python3 -m unittest discover -s tests -p 'test_atomic_benchmark.py' -v`.
