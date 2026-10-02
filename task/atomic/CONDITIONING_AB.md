# Condition a policy and run A/B tests

Branch: `benchmark/atomic-geometry` in [MVerghese/RoboDojo](https://github.com/MVerghese/RoboDojo/tree/benchmark/atomic-geometry).

The benchmark reports **native task success**, **recognized atomic action
success**, **geometric adherence at the specified event**, and **event coverage**
separately. Begin with the audited four-task pilot; extending to another task
requires the measurement/event work in [ACTION_AUDIT.md](ACTION_AUDIT.md) and its
source-backed [catalogue entry](TASK_MAP.md).

## 1. What the policy receives

In a **full-task run**, an annotation program observes atomic stages while the
policy receives a single task-wide instruction throughout the episode:

```json
{
  "task_name": "pour_balls_into_vase",
  "geometric_instruction": "At the first 2.5 cm lift, grasp the cup with every force-bearing finger contact 0.5 to 3.5 cm above the centre of its mesh bounds along its local z axis. Other contact coordinates are unrestricted.",
  "stages": ["...use actual stage objects from programs/pour_balls_into_vase.json..."]
}
```

This is an illustration of the top-level field, not a loadable program. Use the
complete JSON files in `programs/` or the generators below.

- Omit `instruction` to retain RoboDojo's native, object-resolved task text.
- `geometric_instruction` appends a space and this text to that task text.
- A top-level `instruction` replaces the native text. If deliberately used, keep
  it identical in both arms and ensure it contains no conditioning in the baseline.
- In **selected-stage mode**, the policy instead receives that stage's
  `instruction`; a stage variant replaces it with the variant's `instruction`.
  It is not automatic per-action prompting inside a full-task episode.
- These are **text constraints**, not simulator-enforced trajectories or a
  numeric policy input channel. The Cosmos adapter maps observation `instruction`
  to policy `prompt`. For another policy adapter, verify this mapping.

The authoritative delivered text is `details[*].policy_prompt_history` in
`eval_report.json`. A scoring target alone does not condition the policy.

## 2. Define exactly what the geometry means

Use the [per-slot modifier matrices](TAXONOMY.md) and
[implemented checker audit](INSTRUMENTATION_AUDIT.md). A geometric condition names:

```json
{
  "id": "cup_grasp_offset",
  "slot": "grasp_region",
  "kind": "relative_displacement",
  "measurement": {"kind": "contact_points", "label": "cup", "arm": "any", "min_finger_bodies": 2},
  "reference": {"kind": "object_center_pose", "label": "cup"},
  "event": {"kind": "first_lift", "label": "cup", "threshold": 0.025},
  "expected": [0, 0, 0.02],
  "axes": [2],
  "tolerance": 0.015,
  "track_closest": false
}
```

This measures **every force-bearing finger contact** at the first 2.5 cm lift,
relative to the cup's live mesh-bounds-centre frame. Only local z is scored:
2 cm ±1.5 cm, i.e. 0.5–3.5 cm. Other coordinates are unrestricted. The worst
contact determines pass; the contact centroid is a diagnostic. Two finger bodies
must belong to the same arm. Missing contacts have no score/pass.

Positions are metres, rotations radians and quaternions `[w,x,y,z]`. A point
without a reference is environment-local; with a reference, its coordinates are
in that reference frame. `object_pose` is the root, `object_center_pose` the
mesh-bounds centre, and `functional_point`/`support_point` annotated landmarks.
Do not call any of these a centre of mass. A contact point has no SE(3)
orientation: use a separate oriented frame for approach/orientation constraints.
Pose conditions require an explicit `angle_tolerance_rad` in addition to the
position `tolerance`; P/D/O express partial constraints. D/O/R require a named
reference frame. Invalid numerical values, unused fields and unsupported
relations now fail program loading. See the [complete conditioning audit](CONDITIONING_AUDIT.md)
for every slot/factor and current spatial-relation subtype.
Object `above` requires signed z separation **and projected mesh-footprint
overlap**; `on_top` also requires support contact.

Describe the same slot, frame, axes, numerical band, tolerance and event in the
prompt. Calibrate candidate targets against actual layout/asset geometry. Keep
success checks independent of geometric targets. A target conflicting with the
fixed action predicate is not a useful steering experiment.

Pick/push programs must include a geometry-independent physical recognizer:

```json
"recognition": {
  "kind": "finger_contact_motion",
  "label": "cup",
  "arm": "any",
  "motion_threshold_m": 0.025,
  "min_contact_steps": 2
}
```

Keep this block identical across the pair. Pick requires two distinct fingers
of one arm; push requires one. Contact loss, an arm change or skipped physics
steps reset the held-motion interval. A pick must remain held at endpoint
completion. The current held interval must achieve the full native `is_lift`
threshold; an earlier short grasp or later catch cannot borrow ballistic lift.
Push recognition additionally requires `support_labels`, e.g. `["@table",
"target_t"]` for push_T. `@table` resolves the actual scene table; other values
are loaded object labels. Push measures planar motion while an upward
force-bearing named support contact persists. Older pick/push programs lacking
this block now fail loading; update
them explicitly rather than deriving recognition from their geometry.
Goal-pose geometry can still be reported when native endpoint checks pass but
physical recognition fails; `goal_success` and `interaction_evidence` make that
distinction explicit. Other families currently report `endpoint_checks_only`
until their independent recognizers are implemented.

For displacement from an object's initial stage pose, put
`"time": "stage_start"` on its **reference** selector. The saved pose and rigid
footprint stay fixed as the object moves. Live references remain the default.
Frozen references are not initial referent selection or full scene restoration;
supported-on checks must use live references and physical support contact.

## 3. Generate controlled pairs locally

From this checkout, with Python providing NumPy and Shapely:

```bash
git checkout benchmark/atomic-geometry
python scripts/atomic/task_catalog.py --check
python scripts/atomic/generate_paired_suite.py --output-dir /path/to/new-four-task-suite
```

This creates **8 cases**: baseline/conditioned pairs for `general_pickup`,
`push_T`, `pour_balls_into_vase` and `plug_in_charger`. Each pair has identical
programs/recognition/scoring except `geometric_instruction`. Both arms are scored
against the same requested geometry, including the unconditioned baseline.

For a **custom two-case full-task pair**, first edit a complete program to define
the geometry to score in both arms. Put the matching geometric text in a plain
text file (one paragraph is sufficient):

```bash
python scripts/atomic/generate_ab_suite.py \
  --program /path/to/my-task.program.json \
  --geometric-instruction-file /path/to/geometric-prompt.txt \
  --output-dir /path/to/new-ab-suite
```

The helper preserves a deliberately supplied baseline `instruction`, removes a
preexisting `geometric_instruction`, and creates a partner with the new append.
It refuses to overwrite a populated suite directory. The runner validates that
pairs differ only in that append before accessing the scheduler. You still need
to review whether the text actually matches the numerical condition.

`generate_suite.py` creates **21 exploratory cup/vase variations** across the
five modifier types. Its geometry changes between cases; it is not a controlled
with/without-conditioning A/B test. Orientation variations score the cup frame,
not a contact orientation. Treat its targets as uncalibrated candidates and
create a separate controlled pair for any target you want to compare.

## 4. Prepare the existing Lepton workflow

The launch helpers require the existing **imaginaire4 Cosmos closed-loop
workflow** in addition to this fork. They overlay this fork onto its RoboDojo
image; assets, XPolicyLab, policy dependencies, model weights and simulator
interpreters come from that image/workflow. Prerequisites are a logged-in Lepton
CLI/API environment (`leptonai`, `boto3`, `s5cmd`), checkpoint/storage access,
the workflow's image/secret settings and a healthy reserved L40S node group.

Use the workflow interpreter for host launch/collection. In the following
commands, set `PYTHON`, `I4`, `FORK`, `BASE_RUN`, `SUITE`, `CREDENTIALS`,
`RESERVATION`, `RUN_NAME`, `POLICY_CONFIG`, `CHECKPOINT` and `RESULTS_PREFIX`
to your environment. Use a fresh unique run name and output/storage prefix.
`CREDENTIALS` is a local JSON file in the existing workflow format; do not commit
it. Image pull and Lepton storage-secret settings must also be configured as
required by `_submit_closed_loop_eval.py --help`.

Create a **one-task, one-episode, seed-0 dry-run base plan** (skip this if you
already have a compatible base plan):

```bash
"$PYTHON" "$I4/projects/cosmos3/cosmos3/evaluation/action/robodojo/_submit_closed_loop_eval.py" \
  --tasks pour_balls_into_vase --seeds 0 --eval-num 1 \
  --config-name "$POLICY_CONFIG" --checkpoint "$CHECKPOINT" \
  --action-type joint --disable-compile \
  --run-id "$RUN_NAME-base" --output-dir "$BASE_RUN" \
  --results-prefix "$RESULTS_PREFIX" \
  --reservation "$RESERVATION" --no-reservation-burst \
  --priority high-8000 --dry-run
```

Use the action type/inference settings appropriate to your checkpoint; keep
them fixed across the pair. The base directory must contain `code.tar.gz`,
`source_manifest.json`, `run_plan.json` and its original `*.job-spec.json`.
The source archive must remain available: suite directories reuse it by hard
link or, across filesystems, symlink. This fork's new runtime files must be
Git-tracked before overlay packaging.

The suite runner currently supports **layout 0 / seed 0, one episode per case,
reserved L40S placements**. A `layout_id` in a manifest is not a layout selector.
The underlying workflow routes four large random variants to H200
(`fold_clothes_random`, `hang_mugs_random`, `arrange_largest_number_random`,
`stack_blocks_random`); the L40S suite runner is not suitable for those tasks.
Extending the source catalogue to 54 tasks does not make all 54 launchable by
this runner.

## 5. Review, launch and collect

Store the **suite and collected evidence on a filesystem with sufficient
capacity**, such as Lustre. Raw mesh evidence can make one `eval_report.json`
hundreds of MB. Preserve raw evidence for score reproduction; reports are
written atomically so a quota failure does not truncate a prior result.

```bash
cd "$FORK"
"$PYTHON" scripts/atomic/run_suite.py \
  --suite "$SUITE/suite.json" --base-run "$BASE_RUN" \
  --credentials-file "$CREDENTIALS" --name "$RUN_NAME" \
  --max-concurrent 4 --gpu-memory-ledger "$SUITE/gpu-memory-observations.jsonl" \
  --dry-run
```

This prepares/reviews inputs and reads live scheduler eligibility; it **does
not submit GPU jobs**. It requires Lepton login even in dry-run mode. Review
the generated `runs/<case>/*.atomic-job-spec.json`, source/overlay SHA256,
checkpoint, image, queue priority and strict reservation before launching.

When execution is authorized, keep one controller alive (e.g. a persistent
terminal), using a file lock to prevent duplicate controllers:

```bash
flock -n "$SUITE/controller.lock" "$PYTHON" -u scripts/atomic/run_suite.py \
  --suite "$SUITE/suite.json" --base-run "$BASE_RUN" \
  --credentials-file "$CREDENTIALS" --name "$RUN_NAME" \
  --max-concurrent 4 --gpu-memory-ledger "$SUITE/gpu-memory-observations.jsonl" \
  > "$SUITE/controller.log" 2>&1
```

Concurrency can be 1–8. Each case uses a single GPU for policy and simulator.
The pre-policy guard samples GPU memory twice, rejects preexisting compute
processes and allows at most 512 MiB for driver/display overhead. The monitor
records admission and node-neighbor evidence; scheduler metadata cannot identify
which neighbor owns a particular foreign GPU process.

The controller polls every 30 seconds, starts collectors and can resume already
submitted plans. Re-run the **same command** after an interruption, with the
same immutable suite/code. Do not regenerate programs for submitted jobs:
packaged inputs are immutable and edits do not alter delivered prompts.
Infrastructure/collection failures are excluded from policy outcomes; the
controller stops new submissions after two such failures. A busy-GPU placement
does not automatically become a policy retry. Preserve its attempt, fix the
cause, and prepare a fresh uniquely named retry with the identical pair controls.

For a single prepared case, monitoring/collection can be resumed explicitly:

```bash
"$PYTHON" scripts/atomic/monitor_trace.py \
  --run-dir "$SUITE/runs/baseline" --credentials-file "$CREDENTIALS" \
  --gpu-memory-ledger "$SUITE/gpu-memory-observations.jsonl"
```

Use the actual case directory (the four-task suite uses task-prefixed names).

## 6. Selected-stage A/B trials and later starts

For stage-only runs use `submit_stage.py` with an existing dry-run base plan for
that task. The first stage needs no trace. Later stages require a **layout-linked
simulator action trace** with all preceding, strictly increasing stage boundaries
and successful prefix predicates. LeRobot demonstration videos alone do not
provide that restart state. See [recording and replay](README.md#record-annotate-run).

```bash
"$PYTHON" scripts/atomic/submit_stage.py \
  --run-dir /path/to/fresh-stage-plan --fork "$FORK" \
  --program task/atomic/programs/pour_balls_into_vase.json \
  --stage pour_balls --trace /path/to/annotated-layout-trace.json \
  --reservation "$RESERVATION" --max-initial-gpu-memory-mib 512 --dry-run
```

For the conditioned partner, use another fresh base plan and add
`--variant /path/to/stage-variant.json`; when authorized, omit `--dry-run` and
provide `--credentials-file`. Keep the same trace/layout/checkpoint and success
checks, but ensure **both arms score the same condition**. Put the geometry in
the shared program, keep its stage instruction unconditioned, and use a variant
changing only `instruction` for the partner. A variant changing geometry as well
is a different-target experiment, not with/without-prompt A/B.

The included `pick_cup_positive_x`/`negative_x` variants are different-target
steering candidates: every finger contact in a positive/negative x band, not an
EEF origin. They explicitly use `axes:[0]`. Opposing contacts may make these
bands infeasible for a particular cup/grasp: calibrate first. The basic program
uses z-only contacts, so applying an x-band variant requires a new simulator run.

## 7. Verify the comparison and interpret results

Collected suite artifacts:

| Artifact | Purpose |
| --- | --- |
| `suite.json`, `*.program.json` | Requested geometry and geometric prompt append |
| `runs/<case>/run_plan.json`, `overlay.sha256` | Checkpoint, seed, source and packaged execution provenance |
| `runs/<case>/eval_report.json` | Delivered `policy_prompt_history`, native/atomic results, contact health and raw measurement state |
| `runs/<case>/atomic-score-audit.json` | Independent recomputation of event scores from saved state |
| `benchmark_results.json`, `benchmark_results.md`, `REPORT.md` | Collected case results and paired comparison |
| `gpu_admission.json`, memory ledger, neighbor snapshots | Infrastructure placement evidence |

Before interpreting A/B, verify actual delivered prompt = baseline prompt +
exact append, actual layout IDs agree with the plan, and checkpoint, inference
settings, source runtime and scoring definitions match. Use each immutable
overlay/run plan as evidence, not the currently edited checkout. Require healthy
contact callbacks and zero score mismatches. These fields are reported, but the
generic formatter does not itself certify runtime equality across overlays.

```bash
"$PYTHON" scripts/atomic/audit_scores.py \
  --report /path/to/eval_report.json --output /path/to/recomputed-scores.json
```

Add `--variant /path/to/opposite-target.json` for target-only counterfactual
rescoring. Immutable fields repeated identically are allowed; changing axes,
measurements, references or events requires a new run. Rescoring an outcome is
not evidence that the policy responded to a new instruction.

Report geometric error **and coverage**. Missing events are not geometric passes
or zero errors. A reached goal with unverified contact is not a recognized push.
The `benchmark_proof` pipeline flag indicates collected/reproducible evidence;
it does not certify all actions or good policy performance. One episode per
arm is an integration pilot. Use multiple feasible targets and matched repeated
layouts/seeds after extending the runner before making statistical claims.

The completed [eight-run pilot](PILOT_RESULTS.md) proves text delivery and score
reproduction end to end, with 0/8 native task successes. It does not establish
general steerability or all-family coverage.

## Immutable suite preparation

The suite runner freezes every case's overlay, patched spec and input hash
before submitting any case. `prepared_case.json` records these hashes and a
runtime-content hash excluding the per-case prompt program; every case must
have the same runtime hash. Pending cases submit those exact bundles, and
resume checks them without rebuilding from a changed checkout. Changed input
or bundle requires a fresh suite directory. Existing historical controllers
without frozen preparations should retain their original runner version.

See [RUNTIME.md](RUNTIME.md) for the new button-count and xylophone programs
and their prototype calibration limits. Both arms must score the same contact
or placement conditions; put numerical geometric guidance only in the
conditioned program's `geometric_instruction`.
