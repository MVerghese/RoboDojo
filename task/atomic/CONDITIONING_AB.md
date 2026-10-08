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

For nominal contact-frame targets with actual feasibility evidence, use:

```bash
python scripts/atomic/generate_calibrated_contact_frames.py \
  --output-dir /path/to/new-calibrated-contact-suite \
  --source-suite /path/to/contact-frame-suite/suite.json \
  --report /path/to/contact-frame-baseline/eval_report.json \
  --prior-suite /path/to/original-contact-binding-suite/suite.json
```

This currently binds the two block-language pickups. It requires actual
successful grasps, consistent raw force/frame witnesses and an observed pose
satisfying the position target. The report hash and exact relative axes are
retained. Both arms receive the same calibrated geometry; the conditioned prompt
names the measured physical link and its three directions in object axes.
Initial native/physical success gates stay unchanged. This witnessed nominal
target does not certify arbitrary orientation perturbations as feasible.

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

### Matched distinct strike target regions

Generate a fresh pair from the reviewed eight-strike contact-frame suite:

```bash
python scripts/atomic/generate_strike_region_suite.py \
  --source-suite /path/contact-frame-suite/suite.json \
  --output-dir /path/fresh-strike-region-suite
```

Both arms receive the same stricter recognition settings: all eight live hit
landmarks, with 2 mm minimum distance advantage for the requested target.
The baseline/conditioned prompts and all geometric scoring definitions are
preserved exactly from the source pair. This isolates an instrumentation change;
it does not create a new prompt treatment. Freeze/package both arms together.
The provenance file lists source hashes and the exact changed fields. These
regions distinguish overlapping contact neighborhoods; they are not a claim
of calibrated bar surfaces, exclusive single-key contact or musical timing.

### Replay fidelity beyond root positions

Fresh capture runs save stage `initial_object_states` from actual rigid solver
pose/linear/angular velocity readbacks. Run a new source episode after packaging
this runtime, then use `run_prefix_validation.py prepare/start/proof` as described
above with its recorded trace. Historical source traces cannot supply missing
activation velocities. Prefix proof reports retain source/trace hashes and
separate mm, degree, mm/s and degree/s residuals. Missing readbacks stay N/A.
These diagnostics cover named rigid roots, not complete simulator restoration.

### Independent twist-history audit

Fresh screw/twist runs retain relative root/pivot pose histories and selected raw
finger/constraint force rows. Running `scripts/atomic/audit_scores.py` applies
independent history validation automatically, including cached-report refresh.
Old/truncated histories stay partial. Keep both arms on a newly frozen runtime;
changing requested orientations cannot replace missing physical twist history.

### Calibrate supported-release observation duration

`settle_steps` is a shared recognition parameter, separate from geometric
conditioning. For a duration probe, keep both prompts and all geometric targets
fixed and package both arms with the same new count. The current fresh bowl
profile uses twelve adjacent states. Their actual duration is eleven physics
intervals, measured from saved dt. Raw settling pose/support windows are checked
automatically by `audit_scores.py`, including cached report refresh. Historical
runs cannot supply missing poses, and bounded stability does not prove future rest.


### Robot joint state at activation and replay

Fresh stages capture actual `IsaacLab.Articulation.data.joint_pos` and
`joint_vel` after the simulator scene update, for every solver DOF, including
grippers. Coupled arms sharing an articulation are captured once. The actual
`root_physx_view.prim_paths` root must belong to the selected environment and
configured robot subtree. Each solver joint name must uniquely match a live USD
revolute or prismatic joint there; ambiguous, absent or unsupported types and
failed/nonfinite readbacks remain unavailable. Commands and drive targets are
not substituted for physical state. Captures are immutable and timestamped at
the activation physics step.

Replay compares the same environment, articulation and typed joint paths.
Revolute position/velocity residuals are degrees and degrees/s; prismatic
residuals are mm and mm/s. They remain separate columns in MD and HTML, with
per-joint values in the proof. Rotation residuals do not wrap a full turn to zero.
Columns show maxima within each joint type, with historical missing captures
N/A. No arbitrary fidelity threshold is introduced. These readbacks do not prove
equal drives, efforts, robot root state, contact warm starts or full simulator
restoration, and they do not change atomic success or geometric conditioning.
Six regressions cover immutable coupled capture, mixed units/full turns, bad
binding/clock/source/nonfinite data, adjacent robots/environments, live USD joint
ambiguity and separate report units. Fresh capture/replay evidence is pending.


### Finite rigid material fit at sampled mouth crossings

Rigid material transfers can set `finite_material_bound: true` independently in
`recognition.source_exit` and `recognition.flow`. This is unsupported for fluid
particles: no solver particle radius is invented. Apply the same recognizer
configuration to both prompt arms. Fresh stages capture each material object's
actual complete scaled root-relative USD mesh, physical root, label, environment
and activation step. The center is its actual mesh-bounds center, and the bound
radius is the maximum vertex distance from that center. Every triangle is inside
this enclosing sphere. Open seams are recorded with `closed_oriented_mesh: false`;
they are not sealed and do not establish solid volume.

At the adjacent sampled center crossing, the projected enclosing disk must fit
inside the reviewed aperture, including every hole. Clearance is the signed
center distance to the nearest aperture boundary minus the measured radius;
negative clearance is a finite-fit shortfall. This conservative check can reject
a non-spherical object whose exact local section would fit. A positive result
certifies all captured mesh triangles fit within this projected bound at this
sampled crossing plane. It does not establish continuous passage, thick-wall
clearance, collision response, fluid volume or an unseen curved trajectory.
Existing center-only profiles retain their declared semantics.

Target-flow reports expose radius, signed clearance and nonnegative shortfall in
separate mm measurements, including explicit N/A columns when an event is absent.
Source-mouth raw witnesses retain the same scalars. Missing, malformed or stale
bounds leave fit unavailable, without center-only fallback. Independent audits
recompute the bound from raw vertices/topology and bind each crossing to the
correct material, environment and immutable activation capture. Changed captures
or wrong material identity exclude otherwise numerically reproduced flow scores.
An inward center crossing clears an earlier exit even if its finite fit failed.

The retained seed-0 asset calibration has seven ball meshes, each with a measured
5.0000003 mm enclosing radius and open exported topology. Eight regressions cover
edge/hole overruns, missing/forged/topologically inconsistent bounds, target
flow/report units, grazing reentry, unsupported fluid bounds, actual rigid-runtime
capture and source-witness exclusion. Live finite-mouth evidence is pending.


### Live robot captures and target-bound twist intervals

`geometry-robot-joints-capture-1006` completed both bowl arms with native and
atomic pickup/placement success. Each selected placement activation retained two
actual articulations with eight solver DOFs each, including grippers. This is
live joint-readback evidence; the selected-stage replay comparison is still
pending separately.

`geometry-twist-target-binding-1006` completed both screw arms. Native task success
was false in baseline and true with conditioning. All six pickups were observed,
but no nut reached the separate 90 degree constrained-rotation gate. Five retained
partial rotation intervals independently validate pose arithmetic, force rows,
declared labels/frame and same actual constraint roots; baseline nut0 has no
valid retained interval. Clockwise progress/off-axis sums in degrees are:

| Nut | Baseline progress / off-axis | Conditioned progress / off-axis |
| --- | --- | --- |
| nut0 | N/A | 7.024942 / 6.430205 |
| nut1 | 75.500796 / 19.872551 | 64.054478 / 19.808941 |
| nut2 | 0.107279 / 1.632637 | 45.093453 / 19.776772 |

These are the greatest net directional progress among saved valid current or
interrupted intervals, not a complete-turn witness or mechanical thread proof.
Native fasten_screws checks alignment/depth and arm reset, without a 90 degree
rotation requirement. One episode per arm does not support a statistical steering
claim. The independent artifact retains report hashes and all failed/unobserved
completion events; historical compact partial histories remain partial.


### Drive command targets at action activation

Fresh robot captures separately save the current IsaacLab `joint_pos_target` and
`joint_vel_target` buffers, with the same actual solver DOF names, live USD joint
paths/types and activation timestamp as the physical joint capture. These are
command targets. They do not replace measured `joint_pos`/`joint_vel`, and an
absent or failed target-buffer readback leaves physical-state evidence available.
The native RobotManager writes arm position/velocity targets and gripper position
targets through the articulation setters before simulation steps.

Replay compares retained command buffers independently of physical state. A
physically identical joint configuration can therefore have a nonzero command
difference. Revolute target position/rate residuals are degrees and degrees/s;
prismatic residuals are mm and mm/s. Per-DOF results remain in the proof, with
maxima of each joint type in a separate MD/HTML table. No full-turn wrapping or
combined score across joint types is used. Historical missing buffers remain N/A.
Wrong source APIs, names, paths, indices, units and nonfinite buffers cannot
certify command equality. Target equality does not prove equal stiffness,
damping, effort, actuator memory or full controller state.

Five targeted regressions check immutable commanded-versus-measured captures,
equal physical states with changed commands, missing-buffer independence,
invalid source/binding and separate report units. Fresh live target-buffer
capture and replay evidence are pending; no existing frozen run is relabeled.

## October 7: qualified stage-success measurement events

`stage_success` geometry now uses the same completion gate as atomic success:
the native endpoint, required physical interaction, contact-coupled held lift
for pickup, and maintained-hold requirements must pass together. An endpoint
reached by unsupported motion or a later catch cannot latch completion geometry.
For supported placement, completion measurements wait for transport, release and
the configured supported settling window. Geometry failure still does not change
the action success flag.

Each new completion measurement retains the synchronized physics/action clock,
native and qualified completion flags, recognizer kind, physical-interaction
flag and maintained-hold failure count. Pickup additionally retains the current
grasp, contact-coupled displacement and required lift threshold. Independent
`completion_validation.py` checks those saved fields, clock/binding and lift
math; contradictory geometry is excluded as `invalid_stage_success_witness`
while its arithmetic result and native/action outcome remain available. These
flags do not reconstruct unsaved force or hold histories. Historical endpoint
measurements without the new metadata remain explicitly partial evidence.

The current gate passes 411 offline atomic tests, including six completion-event
counterexample and independent-audit tests. MD and HTML expose completion
witness status separately from scalar geometry. Fresh pickup/settled-placement
and push A/B validation is the next live check; offline tests are not live proof.

## October 7: bounded source-mouth candidate qualification diagnostics

`SourceExitObserver` now retains the first 32 outward candidate crossings,
including rejected fit/sampling cases, their adjacent raw positions/opening
poses, actual finite mesh bound when requested, numerical result, physics
clock and action index. Total counts and outcomes continue over the observed steps of the stage; a truncation flag prevents treating the retained subset as a complete
distribution. Returned snapshots are immutable copies.

At each retained candidate, both fluid and rigid recognizers add the same-step
source/core frame, initial source frame, observed sustained-hold contact snapshot
(or explicit unavailable hold), source tilt, inside-core flag, initial eligibility,
reentry and previous-qualification flags, and the actual source-exit eligibility
decision. Rigid candidates additionally retain the actual material root pose.
This does not change recognition thresholds, physical qualification or prompts.

`source_candidates.py` independently reproduces geometry, adjacent clocks/dt,
calibrated mouth/core composition, tilt from raw frames, contact identity/force
snapshot and sustained-hold clock/count when present, finite bound identity and
center, current whole-mesh source-box containment or fluid-center containment,
fluid initial cohort, and the Boolean qualification decision. Contradictory
diagnostic values are excluded; missing historical candidate geometry/contact
bindings remain partial. Initial rigid cohort flags are retained, not a new
reconstruction of initial solid containment. A missing observed hold does not
independently prove absent physical contact. No unsaved hold history, torque,
whole fluid volume, continuous finite-body passage or destination transfer is
inferred.

MD and HTML show a separate per-candidate diagnostic table with aperture overrun
and finite clearance in mm, measured and required tilt in degrees, and physical
gate state. It is separate from successful-pour and destination-conditioning
scores. Older summary-only candidates have N/A per-crossing scalars.

All 416 offline atomic tests pass. Five new candidate tests cover named raw
forces/tilt/mesh binding and corrupted snapshots, geometrically valid unheld or
insufficiently tilted exits, real observer unheld/reentry/held transitions, bounded
immutable history with full counts, and fluid cohort/core/legacy evidence. Fresh
ball and liquid pairs with unchanged programs/prompts are the next live validation;
these offline checks are not checkpoint rollout proof.

## October 8: authored xylophone key-surface calibration

A CPU-only job exported the actual pinned-image xylophone and mallet USD meshes.
The xylophone has separate visual/collision meshes with 23,832 triangles each.
`calibrate_strike_surfaces.py` partitions only the explicitly selected collision
mesh into 42 connected components using a declared 0.0001 mm positional welding
tolerance for connectivity. Distance always uses unchanged actual triangle
coordinates. Each of eight authored `hit_*` points uniquely binds a different
668-triangle component, with a 17.018494–19.545991 mm gap to the next nearest
component. Landmarks are **5.164799–5.225569 mm from their key surfaces**; they
are annotated reference points, not actual surface contact points.

`point_surface_distances` measures exact face-interior/edge/vertex boundary
distance, including slivers and explicit degenerate-face exclusions. It does not
use nearest mesh vertices, bounding boxes or solid containment. Ambiguous/tied
surfaces, aliased landmarks and unreviewed annotation scaling are rejected.

`audit_strike_surfaces.py` reconstructs a root from archived functional frames,
checks all eight frame/position bindings and same-step force points/model actor,
and compares recorded impacts with these authored surface components. The
previous strict-region pair has eight baseline / four conditioned impacts, all
with partial surface evidence and zero contradictions: selected-surface distance
0.116525–1.766269 mm, nearest other key distance 19.235888–32.626368 mm. This
archive reconstruction lacks live selected-mesh/scale capture, so it does not
upgrade live coverage or assert cooked-collider part identity, exclusive impact,
acoustics or native task success. Capturing those actual live USD triangles and
bindings is the next runtime step.

Artifacts:
`/home/mverghese/robodojo-expansion-state/xylophone-asset-calibration-1006/`.
Calibration can be reproduced using the exported `asset-geometry.json`:

```bash
python scripts/atomic/calibrate_strike_surfaces.py \
  --assets /path/asset-geometry.json --asset-key Geometry/xylophone/00000 \
  --mesh /World/collision --tags hit_0 hit_1 hit_2 hit_3 hit_4 hit_5 hit_6 hit_7 \
  --output /tmp/key-surface-calibration.json
python scripts/atomic/audit_strike_surfaces.py \
  --profile /tmp/key-surface-calibration.json --report /path/eval_report.json \
  --output /tmp/contact-surface-validation.json
```

The source passes 422 offline atomic tests, including face/edge/sliver distance,
collision-versus-visual selection, surface ambiguity/alias/scale rejection and
archive frame/force/clock/model/origin corruption counterexamples.

## October 8: live strike surface-region instrumentation

The optional `recognition.target_surface` binding is supported by
`held_tool_strike` and `held_tool_landmark_contact`. It names a reviewed asset
model, file SHA-256, scaled whole-mesh bounds, root-relative collision mesh paths,
source triangle indices and their calibrated coordinates, and the authored
functional-point frame (index 0). At stage activation the adapter resolves the
actual model/file and live scaled USD mesh, verifies every selected triangle
and landmark transform, and retains an immutable root-local capture. Missing or
changed geometry remains unavailable.

At each candidate force-bearing tool/target encounter, actual environment-local
contact points are transformed into the current target root frame. Distance is
the Euclidean distance to the selected triangle region, including face interiors,
edges and vertices. `distance_tolerance_m` is in metres. With `require_contact: true`,
only contacts within that tolerance can contribute to the physical contact/strike
recognizer; sustained hold, landmark neighbourhoods, force, approach and retraction
requirements continue to apply. With `false`, the surface distance is diagnostic.

The independent validator checks model/file/scale/triangle/landmark bindings,
capture and event clocks, contact selection, positive impulses, unit force
normals, same-step reports, target actor identity, environment origin conversion
and target-root/landmark consistency. Contradictory surface evidence excludes
condition and path scores using the affected recognition boundaries while
preserving numerical arithmetic and recorded native/atomic outcomes. Missing
historical captures stay partial. MD and HTML show capture/contact statuses and
maximum selected surface distance and tolerance separately in **mm**.

Five counterexample tests exercise changed actual asset/mesh, landmark proximity
without surface contact, stale/zero-force reports, wrong actor/origin/root and
invalid selected indices, and cached-window score exclusion. These are offline
tests; a fresh live matched pair is required to establish live mesh capture.
The xylophone pair applies the same **2 mm** surface gate to both arms without
changing geometric targets or delivered prompt text from the earlier strict
target-region pair.

This measures a region of the actual scaled USD collision mesh. It does not
certify a separately cooked key collider, exclusive single-key impact, sound
or musical timing. Authored hit landmarks are about 5.2 mm from the key surfaces;
contact-to-landmark distance and contact-to-surface distance are distinct metrics.

Generate and freeze a fresh pair from the previously reviewed strict target-region
manifest and the actual exported xylophone calibration:

```bash
python scripts/atomic/generate_strike_surface_suite.py \
  --source-suite /path/strict-region/suite.json \
  --profile /path/key-surface-calibration.json \
  --output-dir /path/fresh-surface-pair
python scripts/atomic/run_suite.py --suite /path/fresh-surface-pair/suite.json \
  --base-run /path/base-run --dry-run
```

Then run the frozen suite with the reservation, checkpoint credentials and
GPU admission options described above. Generator provenance retains profile and
source program hashes; both arms keep identical physical requirements and scoring.

## October 8: completed source-candidate validation

All four `geometry-source-candidates-1006` episodes from `f18acbb` were collected
and independently audited. Native task success was false in all four. Both
liquid prototype pours succeeded with **required_count=1**; both finite-ball
prototype pours failed with **required_count=2**. These requirements differ
from the native liquid quantity predicate.

| Measurement | Baseline | Conditioned |
|---|---:|---:|
| Liquid destination crossings, reproduced with consistent source witnesses | 7 | 9 |
| Liquid opening point XY error, mean (mm) | 5.922746 | 8.179372 |
| Liquid relative velocity direction error, mean (degrees) | 15.994118 | 17.353837 |
| Liquid opening aperture overrun, mean (mm) | 0 | 0 |
| Bottle mouth pose translation at prototype transfer (mm) | 36.463563 | 28.027000 |
| Bottle mouth pose full orientation at prototype transfer (degrees) | 165.820867 | 168.038982 |
| Ball destination crossings, reproduced with consistent source witnesses | 2 | 0 |
| Ball opening point XY error, mean over observed crossings (mm) | 20.244652 | N/A |
| Ball finite bound clearance at destination crossing, mean (mm) | 3.161606 | N/A |
| Ball relative velocity direction error, mean (degrees) | 19.271728 | N/A |
| Ball sphere_1 final core containment error (mm) | 8.219149 | 379.298721 |
| Ball sphere_6 final core containment error (mm) | 9.446685 | 338.338551 |

The liquid target is **[4,0] mm** in the opening XY plane, within **8 mm**;
the crossing fixes the normal coordinate. Relative velocity should align with
the declared opening normal within **20 degrees**. The central opening window is
**20 x 20 mm**. The mouth pose target is **[0,0,80] mm** above the opening, with
**minus 90 degrees about opening-frame y** (25 mm translation and 30 degree
full orientation tolerances). The
finite-ball opening target remains its separately frozen vase target; its
center-error mean above is not pooled with the liquid target. Programs and
delivered prompts are unchanged from their corresponding source pairs.

Source-mouth history retained all **4/24 ball candidates**, all independently
consistent, and the first **32/32 liquid candidates**, all independently
consistent, out of **37/38 observed**. Liquid histories are explicitly truncated.
Baseline ball source exit qualification passed for two candidates; a later pair
of outward center-plane crossings failed the finite aperture fit by about
165–168 mm. In the conditioned ball run, 23 candidates failed the finite fit;
the one fitting candidate had no sustained hold snapshot and was rejected.
Twenty later conditioned candidates retained a hold, but no candidate met the
full physical source exit gate. An absent observed hold does not independently
prove absent force at unrecorded contacts.

The separate contact audit found **167 consistent retained snapshots**, four
consistent initialized material bounds, ten reproduced event geometry scores
and two unobserved transfer events. Source/flow audits retained report hashes in
`runs/*/independent-material-validation.json`; contact results are in
`independent-contact-batch-validation.json`. No contradictions were found.

The taxonomy now records narrowly validated live opening **point, relative
velocity orientation and aperture-entry relation** factors for this liquid pair.
Opening SE(3) and explicit displacement variants still need matched live tests.
Sampled particle centers, a one-particle prototype and open-mesh finite bounds
do not certify total fluid volume/density/spill, full native quantity, whole
solid volume or continuous passage through a thick mouth wall. One episode per
arm and different crossing populations do not establish statistical steering.

## October 8: collision configuration provenance

Asset exports and fresh live strike surface captures now retain the actual USD
CollisionAPI and MeshCollisionAPI presence, composed collision-enabled value,
approximation mode, applied schemas and relevant PhysX collision attributes.
Every attribute separates its effective value from whether a value opinion is
authored. Missing mesh schemas do not default to an assumed triangle-mesh mode.
Live settings come from the actual selected mesh prim under the task root; baked
asset settings are separate evidence and can differ from scene overrides.

The retained-configuration validator checks selected mesh/root paths, source,
value types and duplicate effective-value consistency. MD/HTML show enabled and
approximation settings separately from surface-distance metrics. Historical
missing configuration remains partial; malformed configuration hides its values
and does not change numerical surface distances or recorded action outcomes.
Two tests cover schema fallbacks, authored settings, absent mesh schemas, disabled
collision and contradictory root/effective-value records.

These are **USD configuration values**, not a readback of cooked PhysX shape
topology or a mapping from callback face indices to authored USD triangles. The
first fresh surface pair (`cdd22a9`) was frozen before this additional provenance
capture; it remains immutable. A further fresh capture is needed to validate
these live configuration fields.
