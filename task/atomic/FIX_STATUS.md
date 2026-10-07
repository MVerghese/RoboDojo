# Audit fixes and remaining implementation

Updated 2026-10-07. This page distinguishes implemented fixes from source plans
and missing adapters. See [instrumentation evidence](INSTRUMENTATION_AUDIT.md),
[slot/factor coverage](CONDITIONING_AUDIT.md), and [all-task plans](SEGMENTATION.md).

## Current verification snapshot (October 6)

The current source passes **249 offline atomic tests**. Dated sections below
retain earlier checkpoints of implementation and verification. Current work adds
model-bound ordered material curves, continuous edge-interior Hausdorff distance,
bounded initial-layout candidate discovery, local closed shaft-section fit,
early contact API installation and
bounded cleanup after simulator exceptions. Cloth path calibration covers all
three configured garment models. Fresh curve, selection-query and corrected pour
pairs require simulator validation; host tests and baked assets do not supply it.

October 7 transport repair: fresh pinned-client runs reached the policy but
failed because the demo runner sent `update_obs` to an infer-only checkpoint.
An explicit local observation cache/inference bridge now preserves action-chunk
cadence and prompts. Actual demo-runner unit tests and a real websocket/JPEG/
array/keepalive proof pass. Fresh GPU pairs are required; this is not yet a
checkpoint rollout validation. Overlay preflight checks the inference signature
before model initialization. Generated selection prompts now use plain numbers.

October 7 interval repair: a conditioned xylophone retry exposed stale first-
impact events paired with later completion. Interrupted strike, handover,
insertion and supported-release windows now archive their events/geometry/paths
and reset current measurements. Attempt IDs and adversarial retry tests prevent
cross-attempt stitching. Cached strike audits now receive independent raw-witness
validation; incompatible windows are excluded from scalar MD/HTML summaries.
The original trace and arithmetic audit remain retained. Corrected paired runtime
validation is the next live check.

The broader boundary audit found three additional inconsistent archives in
retained traces: two conditioned bowl releases and the baseline bottle handover's
initial giver event. Geometry using those specific invalid events is excluded;
the valid receiver-only event remains scored. Seven other completed release/
handover archives passed boundary identity checks; 64 incomplete windows remain
unobserved. These checks do not reconstruct unsaved intermediate force histories.
Physical completion before a failed native endpoint is also archived on retry;
it cannot freeze a stale release/entry event. Completed successful stages retain
their evidence. Fresh bowl/handover runtime validation is being prepared.

Live progress: the repaired block-selection pair completed, with 18 checkpoint
inferences over 550 control actions per arm and 23 arithmetic-reproduced event
scores. Both native tasks failed; both selected the wrong first block, producing
a physical point error rather than a missing referent. Current report rendering
revalidates raw boundaries even when an older running collector used a cached
auditor. Native reports and input result files are preserved.

Selected-stage starts now share a boundary validator between submission and
evaluation. Any concrete independent root can start in the initial scene,
including a nonfirst root or its retained action-zero trace. Zero replay preserves
native parser and robot-origin baselines, and `atomic_start` retains provenance.
Nonzero graph boundaries still require state restoration and are rejected.

A CPU-only search scanned all 267 installed binding stubs, including generic
`_physx.pyi`. It retained five matching interfaces without skipped files. Contact
headers expose collider face and instancer indices, now retained in raw force
rows; these are not cloth material vertex IDs. Generic rigid contact-report APIs
were found, but no particle/finger impulse readout was established. A live cloth
contact probe and solver identity correspondence remain necessary.

Corrected support recognition has live stack-block/stack-bowl evidence. See
[EXPANSION_STATUS.md](EXPANSION_STATUS.md) for frozen suite provenance and the
integrated report. Physical cloth finger contact/force remains unresolved;
anchored material curves do not locate a newly formed physical crease. Source
plans cover all 54 task modules, but arbitrary language/game binding and faithful
full-state replay remain implementation gaps.

Eight held xylophone strikes now have retained live impact/retraction evidence,
including a separate raw-witness consistency validator. The native task failed;
its stricter reward-history requirements are separate from these physical atomic
events. The conditioned partner is pending. Selected cloth patch and finite-chord
geometry also has specific live reproduction evidence; material curves remain
queued. The conditioning audit now cites these exact observations.

The calibrated liquid baseline exposed an initially empty upper bottle core.
The corrected lower core is independently material-free and contains 1,498
particles in retained initial simulator evidence. Initial population preflight
and diagnostic runtime cohort errors are implemented; a fresh matched pair is
required. The stopped original pair supplies no policy adherence results.

## Implemented before the expanded audit

- Real force-bearing finger contacts replace the EEF-origin grasp proxy.
- Same-physics-substep contacts/poses, contact processing enablement and health
  checks, arm/object/environment scoping and worst-point scoring.
- Named root versus mesh-bound centre frames; quaternion/axis semantics and
  separate position/angular tolerances.
- Relative height plus projected mesh-footprint overlap, holes preserved;
  support contact for supported-on and finite whole-object containment.
- Annotated charger tip/outlet frames and correct T/pad height.
- Input validation rejects nonfinite values, incompatible frame types and
  ignored condition fields.

The published eight-run pilot exercises a subset of those fixes. It is not
universal validation of every family, slot or asset.

## Implemented after the expanded audit

| Finding | Change | Verification and remaining limits |
| --- | --- | --- |
| Removing contact geometry relaxes pick/push recognition and suppresses contact initialization. | Explicit stage `recognition`, independent of geometry; contacts initialize from it. At least two consecutive distinct physics steps, same arm, contact-held motion interval. Pick requires two fingers, the full requested native lift within the current held interval and continued hold at goal. Push requires one finger, planar motion and named upward force-bearing support. | Regression cases remove/change geometry/events; unheld lift and touching a previously raised object fail. Full force closure, general palm/tool support and live recapture remain open. |
| Ballistic lift after an earlier short grasp can satisfy native height alone. | Contact loss resets interval; the current held interval must achieve the full native lift and remain held at goal. Later catches cannot borrow prior displacement. | Ballistic-release, later-catch, contact-loss and arm-change tests. Native endpoint and physical recognition are separately reported. |
| Finger lifting can be labeled push; unsigned normals/tangential force can be labeled support. | Push measures planar held motion with named scene-table/object support each sampled step. Support requires signed upward object-side normal and impulse, handling either actor ordering. | Vertical-only movement, absent support, inverted normals, reversed actor order and tangential-only impulses tested. |
| A live self-reference cannot measure displacement from the starting pose. | `reference.time=stage_start` freezes actual pose and historical rigid footprint; live remains default. Reject historical supported-on. | Moving/rotating object, immutable saved reference and historical-footprint tests. Initial referent selection and full simulator-state restore are separate gaps. |
| Many contacts from one finger hide another arm's valid grasp. | Filter arms by distinct-finger requirement before choosing among qualifying arms. | Twenty one-finger points do not hide the other arm's two-finger grasp. |
| No actual tool/target contact measurement or contact event. | `object_contact_points` measures an explicit physical object pair; `first_contact` captures synchronized geometry and raw contact-event evidence. | Actor/collider paths, reversed pairs, environment/object scoping, absent contacts and first-event persistence tested. Held-tool, calibrated active-part, sweep and impact/rebound recognizers remain missing. |
| Support scoring can ignore backend errors; invalid report vectors silently disappear. | Support and pair samplers reject callback failures; nonfinite/malformed contact vectors are instrumentation failures. | Broken backend and nonfinite report tests. |

These new fixes have offline regression coverage. No new live simulator
validation is claimed here; previous pilot results must not be relabeled as
evidence for the new recognizer or snapshot semantics.

## Additional runtime implementation

See [RUNTIME.md](RUNTIME.md) for the complete schema, semantics and limits.

- Concurrent dependency-driven stage observer, sampled every physics substep.
  Independent branches can overlap; finite repetitions can be explicitly unrolled.
- Eight additional recognizers: supported release, held-tool push, held-tool
  contact, grip transfer, held insertion, contact-coupled joint motion,
  constrained unwrapped rotation, and rigid material transfer provenance/counts.
- Named physical-transition geometry events and continuous other-arm holds.
- Stateful native predicates rejected to protect native reward history.
- Precise substep boundaries saved; mid-chunk starts excluded from whole-action
  prefix replay. Nonlinear prefix replay fails explicitly.
- New prototype programs: align_blocks, stack_blocks_by_language, push_T_random.

Verification: **132 offline atomic tests pass**, including additional dynamic/runtime
counterexamples; the updated audit skill validates. No new live results are
claimed. Earlier table entries describe their original implementation boundary;
held-tool, placement and handover additions supersede the missing-recognizer
parts of those entries.

## Next implementation batch (October 2)

- Fixed live layout object-type matching: RoboDojo stores lowercase categories.
- Added numeric asset repeat binding, explicit read-only scene gates and private
  rise baselines. Gates are kept separate from atomic robot actions.
- Added real press/release cycle recognition and actual moving-body contacts.
- Added held-tool contacts bound to annotated tip/target neighborhoods.
- Added live PhysX link landmarks, including moving functional/support frames.
- Added press_by_number and play_Xylophone prototype programs; ten total.
- Frozen suite archives/specs/inputs before submission; all cases must share the
  same packaged runtime hash, and resumes reject changed evidence.

New matched comparisons: align_blocks, stack_blocks_by_language,
press_by_number, play_Xylophone. Fresh live evidence is pending; offline tests
are not successful simulator recognition or demonstrated steerability.

## Further implementation batch (October 2)

- `before_contact` scores the last contiguous pre-contact point/frame and reference.
- Physics-resolution polyline paths retain raw samples, max/RMS errors, ordered
  waypoints, backtracking, endpoint errors and missing-coverage status.
- Explicit initial object candidates are snapshotted and scored against first
  sustained contact identity; ambiguous targets/contacts are never guessed.
- Route/subset choices retain optional attempts, bind repeated branches and
  report simultaneous excess completion as ambiguity.
- `held_tool_strike` adds target-relative pre-impact speed, real impact and
  continued held separation/retraction. Added a stricter xylophone alternative.
- Live material vertex IDs and noncollinear cloth patch frames; no rigid-cache
  or CPU/USD fallback for cloth. Cloth contact/fold recognition is still missing.
- Persistent liquid particle IDs, scaled world coordinates and transfer provenance,
  raw occupancy partitions and configured nominal mass without artifact filtering.
- Articulated meshes follow actual live child poses, and frozen references retain
  historical child geometry. Sheared/unsupported meshes and material-as-rigid
  queries fail explicitly. Link support contacts are scoped to the selected physical
  bodies, with signed vectors and both actor orderings tested.
- Offline score reproduction/reporting includes paths, selection and optional routes.

See [ADVANCED_RUNTIME.md](ADVANCED_RUNTIME.md) for schemas, examples and limits.
The queued eight-run suite uses its earlier immutable runtime (`f8025e5`) and
cannot establish live evidence for these further additions.

## Remaining implementation/calibration

- Automatic candidate enumeration and categorical/task role resolution; selection
  of arbitrary controls, tips and material landmarks beyond explicit object candidates.
- Task-specific binding/calibration/live verification of recognizers, cavities,
  tool/control parts, pivots, physical normals and thresholds.
- Musical timing constraints, natural rebound and intermediate motion between
  physics samples; physical sweep-tip/path feasibility.
- Actual asset mesh/link/contact validation; thread engagement/progress, torque
  and screw feasibility.
- Liquid USD-copy freshness, interior/opening/stream geometry, whole-fluid volume,
  measured density/mass and flight-versus-spill classification.
- Cloth particle/finger contact and grip correspondence, crease/layer order,
  stable fold recognition, self-intersection and CPU cloth state backend.
- Automatic source-plan compilation, task-specific memory/game/conveyor event
  adapters and constraint bindings. Explicit choices, bounded asset repeats and
  read-only scene gates are implemented.
- Faithful full-state restoration and partial-action replay for graph, choice,
  template or mid-chunk starts. Whole-action prefix replay remains linear.
- Throw taxonomy and release/flight/landing recognition.

Original coin/charger insertion and ball-pour programs still have
`endpoint_checks_only` stages. Generic adapters do not migrate these programs
without calibrated landmarks/volumes. All 54 plans remain source plans.

## Support-vector convention

The [PhysX PxContactPairPoint definition](https://github.com/NVIDIA-Omniverse/PhysX/blob/main/physx/include/PxSimulationEventCallback.h)
states that the contact normal points from shape 1 toward shape 0. Support
checks reverse the normal/impulse when the supported object is slot 1 and
require an upward normal component and upward force-bearing impulse. Taking
an absolute normal dot product would accept a downward force. Raw actor,
collider, normal and impulse evidence remains in the result.
