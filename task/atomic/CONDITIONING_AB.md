# Condition a policy and run A/B tests

Branch: `benchmark/atomic-geometry` in [MVerghese/RoboDojo](https://github.com/MVerghese/RoboDojo/tree/benchmark/atomic-geometry).

The benchmark reports **native task success**, **recognized atomic action
success**, **geometric adherence at the specified event**, and **event coverage**
separately. Begin with the audited four-task pilot; extending to another task
requires the measurement/event work in [ACTION_AUDIT.md](ACTION_AUDIT.md) and its
source-backed [catalogue entry](TASK_MAP.md).

## 1. What the policy receives

Fresh calibrated pour suites can use generator phases `liquid_mouth` (liquid)
and `pour_mouth` (balls), with the same retained scene/asset calibration inputs
as `liquid_core`/`pour_core`. These strengthen source qualification to an actual
outward mouth-center crossing while held and tilted; they retain separate
destination position/velocity conditioning and source-mouth SE(3) errors.
Keep them in new suite directories and package both arms together. Historical
core-only comparisons retain their previous scope. Independent source/flow and
cloth probe audits can be reproduced with:

```bash
python scripts/atomic/validate_material_witnesses.py --report /path/eval_report.json --output /tmp/material-witnesses.json
```

For full endpoint cloth bending diagnostics, set `cloth_bending_probe: true` in
both case entries before freezing. The controller validates matching boolean
controls and records the flag in runtime execution provenance. This captures
live cloth positions before reset; it changes neither the prompt nor success
gates. `analyze_cloth_bending.py` computes connected new-bending candidates from
actual adjacent faces using explicit mm/degree thresholds. It cannot certify
force-based grasp or a settled crease from a single endpoint.

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

### Checkpoint transport (October 7)

Fresh atomic overlays explicitly set `ROBODOJO_POLICY_API=checkpoint_infer`.
The demo runner caches `update_obs` locally and requests the checkpoint's
`infer` endpoint once per action chunk. Intermediate control-step observations
do not cause extra inference calls. Native action dictionaries and arrays pass
through unchanged; `details[*].policy_transport` records the selected API and
observation/inference counts. Both A/B arms use this same bridge.

This fixes `no model method named 'update_obs'` with the pinned websocket client
and Cosmos infer-only server. A generic websocket check was insufficient: the
new proof exercises the actual demo runner, JPEG decoding, array codec and
keepalive during blocking steps. To reproduce it with protocol dependencies
installed:

```bash
python scripts/atomic/validate_checkpoint_transport.py --output /tmp/checkpoint-rpc-proof.json
```

This proof uses an infer-only toy model, not the GPU checkpoint or simulator.
Failed frozen packages require fresh matched packages; retrying an identical
package preserves the API mismatch. Native client mode remains available for
servers that implement the demo runner's method API.

## 2. Define exactly what the geometry means

### Explicit contact-frame probes

For contact-slot pose/orientation, use `contact_pose` with an explicit
`orientation_frame` of `robot_ee_pose`, `arm: contacting`, the same object label
and sufficient `min_finger_bodies`. Tool contacts use `object_contact_pose` with
`label`, `other_label` and a physical orientation frame on `label`, such as the
mallet's annotated `beat` functional frame. Both frames must be live. These
selectors preserve actual manifold positions; they never use EEF translation.

Generate fresh matched programs from previously reviewed pairs with:

```bash
python scripts/atomic/generate_contact_frame_suite.py \
  --output-dir /path/to/new-contact-frame-suite \
  --source-suite /path/to/source-contact-binding/suite.json \
  --source-suite /path/to/source-tool-push/suite.json \
  --source-suite /path/to/source-direct-push/suite.json \
  --tasks stack_blocks_by_language play_Xylophone align_blocks push_T
```

The generator rejects changed source hashes and differences beyond the prompt,
preserves native/physical gates and saves source provenance. Each source task
must occur in exactly one input suite. Pickup and direct push add point, pose,
z-direction and contact-box probes; tool push/touch add pose and z-direction.
Existing conditions remain scored and their instructions remain in the
conditioned prompt. `suite.json.contact_frame_bindings` names every added stage, event,
reference and frame. Pose errors remain separate mm and degree values.
The box is centered at the reference origin; the point/pose target can differ.

Both arms must be prepared and frozen together before submission using the
run commands below. An absent qualifying contact/action remains unobserved.
Frame adapter source validation is separate from live policy adherence.

### Calibrated initial referent factors

`generate_referent_factor_suite.py` creates four separate paired suites for
`stack_blocks_by_language`: SE(3) pose, landmark displacement, full orientation
and a spatial center relation. It uses an actual seed-0/layout-0 pre-policy scene
from a retained report, including object-root rotations and mesh bounds. All
three candidates must be rigid cubes. Preflight evaluates each candidate and
requires exactly one match per factor; ambiguous orientation is rejected.

```bash
python scripts/atomic/generate_referent_factor_suite.py \
  --output-dir /path/to/new-referent-factor-suites \
  --source-suite /path/to/matched-block-language-suite/suite.json \
  --calibration-report /path/to/block-language-baseline/eval_report.json
```

Run each generated directory separately with the suite runner. Native and
physical success definitions are retained in both arms. Other geometric scores
and paths are omitted so the prompted conditioning is explicit: only the new
initial referent constraint. The policy receives its native task instruction,
with this constraint appended in the conditioned arm. Candidate geometry and
the named reference are frozen at observer activation; later moved poses cannot
repair a wrong initial selection. The selected candidate's initial distance or
orientation error is reported in mm/deg, with separate contact witness checks.
The spatial probe explicitly compares centers toward negative reference x;
it does not claim whole-object footprint overlap. Fresh runtime target
resolution must still agree with calibration; a no-match/ambiguous layout stays
unscored. Suites retain calibration and source-program hashes and every
candidate preflight result.

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

For a diagnostic particle-cloth callback comparison, set `cloth_contact_probe:
true` on both suite cases. The runner passes `--cloth-contact-probe` to
`submit_trace.py` and freezes it as an execution control. Native mesh callback
samples are saved under `contact_instrumentation.cloth_contact_probe`; they do
not establish material-vertex correspondence or supply a cloth grasp score.
See [measurement details](GEOMETRIC_MEASUREMENT.md#diagnostic-particle-cloth-contact-probe).

For stage-only runs use `submit_stage.py` with an existing dry-run base plan for
that task. Any concrete root stage with no dependencies can start in the initial
scene without a trace, including roots listed after another independent root.
A trace recording that root at action zero also uses the initial scene; no
actions, parser reset or robot-origin reset are applied. Dependent stages require
a **layout-linked simulator action trace** from a linear program or a concrete graph
with a single-ancestor selected route and strictly increasing recorded boundaries
and successful prefix predicates. LeRobot demonstration videos alone do not
provide that restart state. See [recording and replay](README.md#record-annotate-run).

An independent graph stage recorded at a nonzero boundary still needs state
restoration and is rejected. Repeats, gates, choices and label templates must be
resolved into a concrete program first. Per-episode `atomic_start` evidence
records `initial_scene`, `linear_prefix`, `linear_substep_prefix` or `linear_timed_prefix`, the selected stage/action index and
`state_restoration=false`; prefix replay is not a full simulator snapshot.

During a nonzero prefix, persistent preceding-stage recognizers receive every
physics step. The evaluator checks physical completion, native predicates and
maintained holds at each recorded boundary. Prefix geometry is omitted from
scoring. A failed prefix aborts before the selected stage runs and retains
`atomic_start.prefix_stage_validation` diagnostics. Robot/parser resets occur
only after verified nonzero replay; memory/game/count state still requires
task-specific restoration.

Fresh recorded traces include per-action physics spans and simulator dt/control
cadence. A selected stage activated inside a command can use these fields to
stop that command at the synchronized physics boundary, verify its preceding
action and discard the remaining command tail. This path currently requires a
linear program, a single environment, joint actions and no scripted support-arm
controls. Earlier partial boundaries are scheduled from their actual physics
indices, including distinct boundaries within one command. A whole selected
boundary with partial predecessors uses `linear_timed_prefix`. Old traces without
timing metadata, IK actions, merged graph boundaries and ambiguous/nonincreasing physics
boundaries are rejected. Multiple partial predecessors have host validation and a completed button
simulator proof. Host
tests cover interruption and physical verification. A fresh bowl proof replayed
87 whole commands plus 7 substeps of command 88, discarded its 3 remaining
controls and verified the pickup/lift; the selected placement also succeeded.
The root-start residual was 0.008497716 mm, with retained source/report hashes.
Other task bindings still require their own live checks. See section 6 of
[recognition and segmentation](RECOGNITION_SEGMENTATION.md).

For a separate live replay proof, `scripts/atomic/run_prefix_validation.py`
provides `prepare`, `start`, `monitor` and `proof` actions. Prepare a fresh
`geometry-*-1006` evidence directory with `--base-run`, `--program`, `--trace`,
`--stage`, `--name` and `--gpu-memory-ledger`. Then use `start` with the same
`--root`, ledger and `--credentials-file`. It freezes the stage package, uses
high-9000/clean-GPU admission, respects the shared 32-job window and starts a
collector. `prefix-validation.json` requires each preceding action's current
physical/native/hold checks to pass at its recorded boundary. Selected-stage
success is separate. This stage-only proof is not included in full-task A/B
summaries and does not establish full simulator-state fidelity.

For asynchronous timed-trace capture, `scripts/atomic/watch_substep_replay.py`
waits for a retained linear activation strictly inside a command, freezes a
stage-only proof and starts its collector automatically. It requires
`--source-suite`, `--output`, `--stage`, `--base-run`, `--credentials-file` and
`--gpu-memory-ledger`. It prefers eligible baseline traces, records immutable
capture hashes, respects the global 32-job window, and writes progress to the
source suite's `substep-replay-watch.json`. It never synthesizes a midpoint or
infers missing timing. If the capture finishes without a qualifying boundary,
it records that limitation without submitting a misleading partial-command proof.

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
# Expanded eval-set screen

See [EVAL_MATRIX.md](EVAL_MATRIX.md) and `generate_eval_matrix.py` for a checkpoint
map and the 49-task partial-observer A/B matrix. Retain the controls below.

## Additional conditioning suites and current calibration workflow

`generate_expansion_suite.py` creates matched full-task programs with identical
scoring/recognizers in both arms. The conditioned arm alone appends the geometric
instruction. Phases are `feasible`, `validation`, `materials`, `breadth`,
`constrained`, `calibrated`, `cloth_patches`, `crease_segments`, `surface_gaps`, and `pour_core`. Every added numeric target names its event,
reference frame, axes, physical units and tolerance.

```bash
# Bolt/nut constrained turns and persistent garment crease poses.
python scripts/atomic/generate_expansion_suite.py \
  --phase constrained --tasks fasten_screws fold_clothes \
  --checkpoints /path/to/checkpoints.json \
  --calibration-root /path/to/geometry-validation-suite \
  --output-dir /path/to/fresh-constrained-suite

# Physical key mouth/tip, blade section clearance and shoulder gap.
python scripts/atomic/generate_expansion_suite.py \
  --phase calibrated --tasks insert_key \
  --checkpoints /path/to/checkpoints.json \
  --calibration-root /path/to/geometry-support-suite \
  --asset-calibration-root /path/to/baked-asset-calibration \
  --output-dir /path/to/fresh-key-suite
```

The constrained and calibrated-key phases require retained actual baseline
`eval_report.json` scene evidence.
The calibrated key phase also requires `asset-summary.json`, `key-geometry.json`
and the selected slot material mesh NPZ from the baked export. Their hashes are
recorded in the manifest. It verifies live scaled bounds/model identity; it does
not use the incorrect 96 mm slot annotation. The explicit blade collision box
is a declared approximation for section fit, not the complete visual key teeth.
The shoulder target is an 18 mm gap, not flush seating.

For custom cavity/flow work, export actual baked meshes with
`export_asset_geometry.py`, derive plane profiles with
`task.atomic.calibration.opening_section`, and validate conservative interior
boxes with `interior_core_box`. Retain raw evidence and hashes. A finite opening
profile is not a whole cavity. Core-restricted source cohorts must be declared.
Use `expected_velocity_direction` to condition flow direction; crossing distance,
angular error, aperture overrun and speed are separate physical measurements.

The model-bound garment phase needs the collected baked garment export,
including source hashes, ordered mesh topology and authored material tags:

```bash
python scripts/atomic/generate_expansion_suite.py \
  --phase cloth_patches --tasks fold_clothes \
  --checkpoints /path/to/checkpoints.json \
  --asset-calibration-root /path/to/cloth-asset-calibration \
  --output-dir /path/to/fresh-cloth-patch-suite
```

This phase binds 30 mm same-side geodesic patches for `Top_Long` models 1, 4
and 9 and verifies live model, asset-file hash and topology hash. It requests
50% moving-patch coverage and 1–30 mm layer gaps (1 mm tolerance) at attempt
end, alongside the fold landmark and crease conditions. The generator records
calibration input hashes. Keep source files fixed during runtime packaging.

For cloth patch geometry, `cloth_patch_surface` selects persistent `face_ids`
and three actual material vertex IDs for its tangent frame. `layered_over`
measures moving-patch projected coverage and all triangle-pair layer gaps. Bind
face IDs from actual garment topology before the policy acts. This geometric
check does not recognize a grasp or establish successful folding on its own.

Operational controllers/results are now under
`/home/mverghese/robodojo-expansion-state/`; immutable original evidence remains
on Lustre. Current execution status and missing evidence are documented in
[EXPANSION_STATUS.md](EXPANSION_STATUS.md). Per-suite Markdown and self-contained
HTML reports use separate mm, degrees, mm², mm³, fractions, speed and duration.

### Calibrated rigid-pour core pair

```bash
python scripts/atomic/generate_expansion_suite.py \
  --phase pour_core --tasks pour_balls_into_vase \
  --checkpoints /path/to/checkpoints.json \
  --calibration-root /path/to/geometry-support-suite \
  --asset-calibration-root /path/to/baked-asset-calibration \
  --output-dir /path/to/fresh-pour-core-suite
```

The generator verifies actual model identity/scaled bounds against the captured
initial scene and calibrates closed mouth traces plus material-free interior
cores. It uses initial baseline scene evidence when available, otherwise the
conditioned arm's initial scene; that input path and hash are recorded. It
selects only whole initial balls inside the verified source core, not all seven
balls. The captured seed-0 calibration selects `sphere_1` and `sphere_6`.

The cup core is root XY ±15 mm, Z −21 to +32 mm. The vase core is root XY
±20 mm, Z −60 to +67 mm. The transfer observer requires both selected balls
to exit a physically held/tilted cup and remain wholly in the target core for
five physics samples. Native full-task success still tests its original task.
At first transfer, cup mouth pose targets [0, 0, 80] mm relative to the vase
mouth, with −90° local-Y orientation (25 mm/30° tolerances). Each qualified
downward mouth crossing targets XY [4, 0] mm with 10 mm tolerance and downward
velocity within 20°. Final whole-ball box error has 1 mm tolerance.

Retained sphere surfaces do not pass the closed-solid volume preflight. This
profile therefore reports whole-mesh vertex enclosure in a calibrated convex
box, not solid outside volume; every triangle between enclosed vertices also
lies in that convex box. Flow tracks the ball's measured mesh centre and
reports its crossing distance, aperture overrun, relative speed and direction
separately. It does not certify liquid volume, continuous stream shape or
transfer of material outside the declared source-core cohort.

For finite crease geometry, run the garment command above with
`--phase crease_segments` and a fresh output directory. This adds 20 mm
symmetric Hausdorff coincidence between each actual material-endpoint chord
and its initial finite segment. Raw endpoints support independent rescoring;
angles and lengths remain separate physical components. The condition covers
the declared chords, not an uninstrumented curved crease.

Use `--phase surface_gaps --tasks fold_clothes` with the same garment asset
export and a fresh output directory to add selected triangle-boundary gap
conditioning (20 mm at attempt end). Both arms retain identical patch coverage
and layer-order checks. Minimum boundary distance alone does not certify
contact, support or absence of penetration. Custom rigid `near` conditions
require explicit reviewed material `mesh_paths` for both objects.

### Pinned websocket runtime

Initialize the protocol submodule before preparing a fresh suite:

```bash
git submodule update --init --depth 1 XPolicyLab
```

The runtime overlay now verifies the checkout against the parent repository's
pinned Git link and ships the websocket client/server/codec plus required shared
observation helpers and license. Dirty or missing protocol source fails before
submission. `task/atomic/pinned-protocol.json` in each overlay records its commit
and per-file SHA-256; protocol files enter the A/B runtime hash. Compiled
simulator dependencies and assets still come from the baked image.

The pinned client runs its event loop on a background thread while simulation
blocks; the pinned server runs blocking model calls outside its event loop.
This keeps websocket heartbeats active. The local real-transport probe survived
a 650 ms caller pause and 400 ms model pause with 50 ms heartbeat interval/timeout,
using one network connection and one model invocation. It checks the protocol
and array codec with a toy model, not image decoding, the checkpoint or simulator.
Fresh full-task pairs validate that integration separately. Existing frozen
suites retain their older image-supplied protocol and are not repackaged.

### Combined garment geometry validation

Use the garment export with `--phase cloth_geometry --tasks fold_clothes` to
combine calibrated patches/layers, 20 mm selected-boundary proximity and 20 mm
finite-chord preservation in one fresh A/B pair. Both arms share recognition and
all measurement targets; only the delivered geometry append differs. This phase
is useful for checking the complete currently available garment geometry path
with the pinned transport. It does not add force-bearing cloth grasp evidence.

### Calibrated partial liquid pour

```bash
python scripts/atomic/generate_expansion_suite.py \
  --phase liquid_core --tasks pour_liquid_into_cup \
  --checkpoints /path/to/checkpoints.json \
  --calibration-root /path/to/retained-material-suite \
  --asset-calibration-root /path/to/baked-asset-calibration \
  --output-dir /path/to/fresh-liquid-core-suite
```

The asset export must include the bottle, mugs 15/16 and goblet 6 with
`asset-summary.json` and their selected material `.npz` files. Generation checks
material-free 30 mm cores and a central 20 × 20 mm window inside each actual
mouth. Model/file/scale checks select the live variant. The program scores
first-transfer bottle-mouth pose (25 mm/30°) and downward source-qualified
crossings ([4,0] mm, 8 mm XY tolerance, 20° velocity angle). See
[GEOMETRIC_MEASUREMENT.md](GEOMETRIC_MEASUREMENT.md) for exact frames and
[ATOMIC_SUCCESS.md](ATOMIC_SUCCESS.md) for the partial-cohort success contract.

The retained material suite must contain
`runs/robodojo_25k_pour_liquid_into_cup_baseline/eval_report.json` with actual
initial particle positions/IDs and vessel root poses. Generation checks that
the independently material-checked source core is initially populated, and
retains the full input SHA and population partitions. Current source uses the
reviewed bottle core at root Z=−40 mm. The earlier +27.5 mm core was empty after
settling, so its failed frozen pair supplies no policy results. Do not reuse its
packaged runtime for the corrected comparison.

Both arms retain the same initially eligible cohort rule, minimum one-particle
transfer and five-sample dwell. This is an integration pilot alongside native
whole-liquid success, not a full-volume transfer claim. Empty initial source
cohorts fail explicitly; live population and solver readback remain to validate.

### Actual two-prong charger entry

```bash
python scripts/atomic/generate_expansion_suite.py \
  --phase charger_tips --tasks plug_in_charger \
  --checkpoints /path/to/checkpoints.json \
  --asset-calibration-root /path/to/baked-asset-calibration \
  --output-dir /path/to/fresh-charger-tip-suite
```

Calibration evidence includes `asset-summary.json`, `charger-parts.json`,
`charger-part-0.npz`, `charger-part-4.npz` and `Rigid_socket_00000.npz`.
Prong parts are the exact root-relative vertex/triangle ranges from the reviewed
baked `asset-geometry.json`, not fitted boxes or repaired solids. Preserve source
asset identities. Generation verifies part bounds, derives actual extreme leading
planes, and checks separate closed aperture traces at socket-root Z=20 mm.

The shared observer requires both leading points to enter the middle outlet
throats while continuously gripped and in actual charger/socket force contact.
Only the conditioned arm gets the middle-slot/tip-pose append: [0,0,−10] mm
relative to each throat, 3 mm and 20° full-orientation tolerances at insertion and
episode end. Whole-prong clearance and electrical seating remain unverified.

### Initial-layout candidate discovery pilot

Generate a fresh stack-block comparison using actual bounded candidate discovery:

```bash
python scripts/atomic/generate_expansion_suite.py \
  --output-dir /absolute/path/to/fresh-suite \
  --checkpoints /absolute/path/to/checkpoints.json \
  --phase selection_query --tasks stack_blocks \
  --calibration-root /absolute/path/to/completed-stack-suite
```

The calibration suite must retain its baseline `eval_report.json` with the actual
initial stack-block scene. The same XYZ selection, geometry and physical
recognizers apply to both arms. Discovery uses exactly three rigid `block_`
labels from the actual layout; only the conditioned arm receives the geometric
append. Candidate inventories are frozen at activation and independently
audited. This is an initial referent pilot, not language parsing or automatic
all-task program compilation.

### Anchored cloth-curve pair

`generate_expansion_suite.py --phase material_curves --tasks fold_clothes
--asset-calibration-root <cloth asset export directory>` adds continuous
polyline preservation to the existing material landmark, patch and surface-gap
conditions. The export directory must contain `asset-geometry.json` with all
three configured garment models and actual material topology. Calibration binds
ordered mesh-edge IDs before the policy acts. Both arms score the same initial
paths at episode end; only the conditioned arm receives the geometric append.
These are explicit anchored material lines, not inferred physical creases.

### Charger local section pair

`generate_expansion_suite.py --phase charger_sections --tasks plug_in_charger
--asset-calibration-root <rigid asset export directory>` adds four local shaft
fit measurements to the two-tip insertion profile. Required exports are the
asset summary, actual charger part paths/meshes and socket mesh. Before packaging,
all six prong/depth cuts must fit one common reviewed pose with 0.25 mm clearance,
and lateral counterexamples must fail. Both prompts score the same conditions
and recognizer. The conditioned append names actual plane cuts and clearance;
no whole-prong volume or electrical seating is requested.

A finished collection worker with no eval report is an evidence failure, with
unavailable rollout outcome and no native/action/geometric result. It is excluded
from matched comparisons. Zero retained episodes does not infer that the worker
executed no policy actions. Keep stop requests, collector exit and failure logs
for diagnosis; never fill missing outcomes with policy failure or zero error.

### Watch older workers for retained simulator exceptions

`python -m scripts.atomic.watch_failed_workers --root <suite parent directory>
--helper <operational expansion helper>` checks running authorized suites every
120 seconds. It uses the existing helper to retain/redact cloud logs and stop
only a worker with an explicit simulator exception after five minutes for
normal cleanup. The current job ID and running state are rechecked before the
stop. Policy/native failure, reconnects and quiet contact scenes cannot trigger
it. Stop evidence is retained in `failed-worker-watch-events.jsonl`. Terminal
collections with unavailable reports are reconciled after every worker in that
suite finishes. New packages also have the faster in-container cleanup guard.

For a proof specifically exercising multiple timed boundaries, add
`--require-partial-predecessor` to `watch_substep_replay.py`. It requires an actual
recorded partial boundary before the selected stage and accepts a selected
partial or whole-command boundary. A trace with only the selected partial
boundary cannot satisfy this stronger validation request. The fresh
`geometry-timed-button-capture-1006` pair observes one red-button cycle, a confirm
cycle, and the next red-button cycle in a concrete linear program. These are
physical observers within the native task; they do not reconstruct its full
number/memory semantics after a parser reset.

An already submitted selected-stage proof can resume its local collector with
`run_prefix_validation.py monitor --root ... --credentials-file ...
--gpu-memory-ledger ... --detach`. It verifies the submitted job identity, retains
previous/resumed monitor provenance, avoids replacing a running monitor and locks
collection per proof. It does not submit another GPU job.

Selected-stage replay also accepts a single-ancestor route inside a concrete
DAG. `prefix_stage_ids` records the verified route. The complete recorded control
trace is preserved; independent peer recognizers are omitted. Merged dependencies,
noninitial route roots and unresolved gates/repeats/choices remain rejected.
This extension has host validation; its dedicated live proof is pending.
