# Audit fixes and remaining implementation

Updated 2026-10-08. This page distinguishes implemented fixes from source plans
and missing adapters. See [instrumentation evidence](INSTRUMENTATION_AUDIT.md),
[slot/factor coverage](CONDITIONING_AUDIT.md), and [all-task plans](SEGMENTATION.md).

## Current verification snapshot (October 7)

Latest additions retain actual object/robot activation kinematics and independent
joint-state replay residuals, twelve-state supported-release pose windows,
label/frame/root-bound constrained twist histories, conservative finite mesh
aperture bounds and separately identified drive command buffers. The joint replay
and settling proofs completed; the new finite-mouth and drive-target pairs are
running. Detailed dated evidence below distinguishes observations from pending
capture/replay checks. No completed 90 degree screw twist was observed.

The current source passes **422 offline atomic tests**. Dated sections below
retain earlier checkpoints of implementation and verification. Current work adds
model-bound ordered material curves, continuous edge-interior Hausdorff distance,
bounded initial-layout candidate discovery, local closed shaft-section fit,
early contact API installation and
bounded cleanup after simulator exceptions. Cloth path calibration covers all
three configured garment models. Repaired curve, selection-query, liquid and
ball-pour pairs now have retained checkpoint rollouts; exact observations and
missing physical witnesses are reported separately.

Explicit contact-frame adapters now cover the eight formerly F pose/orientation
cells: real contact coordinates plus same-step named robot-link/tool axes.
Specific pickup/direct-push/tool-touch cells now have independently checked live
measurements; the source audit has 26 L cells, 141 G, 70 S, five M and 28 NA.
These are physical link/tool axes, not surface-normal frames. All eight fresh
contact-frame cases and later nominal/target-region/referent pairs are collected.
Independent selected-referent force/root/arm/time validation and root-alias
rejection also passed live; historical missing metadata stays partial.
The single-ancestry graph prefix also passed live boundary validation, with
0.000725 mm block-root drift; its subsequent selected placement failed.

The optional source-mouth gate now checks outward material-center crossings
through the actual calibrated aperture, including holes and source-frame/model
binding, while held and tilted. It rejects core-only escapes, unheld crossings,
sampling gaps and stale qualification after source reentry. Whole-ball source
aperture fit and whole-fluid volume remain outside this center witness. Fresh
matched `liquid_mouth`/`pour_mouth` validation is being prepared.

Those four source-mouth cases are now submitted at high-9000 from frozen
`67318bf`. Live later-stage replay proof `bc41fa2` also completed: a 45-action
prefix verified the contact-held pickup before 400 policy actions in the selected
pour stage. Replay validity passed; the selected pour endpoint failed.

Opt-in full garment endpoint capture and adjacent-face bending analysis are
implemented. They preserve persistent IDs/topology, compare angle increase from
initial shape, and expose bad winding, nonmanifold, degenerate and stretch
exclusions. Components remain diagnostic bending candidates; unique physical
crease recognition, temporal settling and task-specific binding are unresolved.
Five new host tests verify real hinge geometry, rigid-motion/preexisting-bend
counterexamples, reordered IDs, mesh capture before reset and failure visibility.

The matched full-endpoint cloth pair is now Running from frozen `b8cf398` at
high-9000; programs and prompts match the earlier material-curve pair exactly.
All three authored garment models also passed unchanged and 1 mm rigid-motion
counterexamples, with 30,832 / 27,765 / 28,334 usable hinges and no false candidates.

`align_blocks` tool-push observers now start independently. The native task does
not require lifting the tool, so a vertical pickup cannot gate a table-level
stroke. Pick remains an optional observation; force-bearing tool hold/contact,
support and planar motion are still required. New tests recognize a held stroke
with zero lift and reject direct finger/block pushing. Per-block witnesses can
belong to one shared stroke. A new matched comparison is being prepared.

The fresh core-only liquid pair supplies **144 consistent source witnesses**,
with no inconsistent source evidence (native false/true). The cloth callback
probe has zero garment headers/points in both completed episodes; applying its
native report API did not expose cloth/finger forces. Those five grasp-factor
cells remain missing. The integrated MD/HTML now includes **201 valid episodes,
99 verified pairs and 913 reproduced event scores**, with zero arithmetic
mismatches. Historical invalid recognition windows remain excluded.

October 7 transport repair: fresh pinned-client runs reached the policy but
failed because the demo runner sent `update_obs` to an infer-only checkpoint.
An explicit local observation cache/inference bridge now preserves action-chunk
cadence and prompts. Actual demo-runner unit tests and a real websocket/JPEG/
array/keepalive proof pass. Twenty fresh GPU episodes completed across ten
comparisons, validating the repaired checkpoint transport. Overlay preflight checks the inference signature
before model initialization. Generated selection prompts now use plain numbers.

October 7 interval repair: a conditioned xylophone retry exposed stale first-
impact events paired with later completion. Interrupted strike, handover,
insertion and supported-release windows now archive their events/geometry/paths
and reset current measurements. Attempt IDs and adversarial retry tests prevent
cross-attempt stitching. Cached strike audits now receive independent raw-witness
validation; incompatible windows are excluded from scalar MD/HTML summaries.
The original trace and arithmetic audit remain retained. The repaired strike
pair has sixteen consistent impact/retraction witnesses; native success is
true/false for baseline/conditioned. The new bowl/handover pairs have five
consistent completed boundary windows and no inconsistent windows.

The broader boundary audit found three additional inconsistent archives in
retained traces: two conditioned bowl releases and the baseline bottle handover's
initial giver event. Geometry using those specific invalid events is excluded;
the valid receiver-only event remains scored. Seven other completed release/
handover archives passed boundary identity checks; 64 incomplete windows remain
unobserved. These checks do not reconstruct unsaved intermediate force histories.
Physical completion before a failed native endpoint is also archived on retry;
it cannot freeze a stale release/entry event. Completed successful stages retain
their evidence. Both new bowl and bottle arms have native success; declared
physical action coverage is lower and remains separately reported.

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

Later linear prefixes now keep their recognizers alive through every physics
substep and apply the same physical/native/maintained-hold success gates at
recorded boundaries. The old fresh-session endpoint check lost physical history
and could bypass physical contact gates. Prefix geometry is not scored; failure
clears replay state and aborts before baseline resets or selected-stage inference.
`atomic_start.prefix_stage_validation` saves the preceding physical evidence.
Host tests exercise the actual evaluator callback path; simulator replay fidelity
and faithful memory/game state restoration remain separate validation needs.

A CPU-only search scanned all 267 installed binding stubs, including generic
`_physx.pyi`. It retained five matching interfaces without skipped files. Contact
headers expose collider face and instancer indices, now retained in raw force
rows; these are not cloth material vertex IDs. Generic rigid contact-report APIs
were found, but no particle/finger impulse readout was established. A live cloth
contact probe and solver identity correspondence remain necessary.

The opt-in native cloth callback probe is now implemented: contact-report API
installation precedes cloth tensor initialization; no rigid body is added.
Raw force/zero-force samples have separate budgets, real finger identities,
native face/instancer indices and explicit unverified material correspondence.
Matched pairs enforce the same probe setting. Live callback validation remains
necessary; the five cloth grasp cells remain missing.

NFS quota failures interrupted local collection and audit generation. The
checkout and operational state now use node storage with original home paths
preserved as symlinks; NFS backups and original cloud artifacts remain retained.
Truncated authored/generated files were restored before the full test run.
Audit generators now use atomic writes, preserving prior artifacts if a write
fails. Completed remote jobs are collected from unchanged frozen inputs.

Corrected support recognition has live stack-block/stack-bowl evidence. See
[EXPANSION_STATUS.md](EXPANSION_STATUS.md) for frozen suite provenance and the
integrated report. Physical cloth finger contact/force remains unresolved;
anchored material curves do not locate a newly formed physical crease. Source
plans cover all 54 task modules, but arbitrary language/game binding and faithful
full-state replay remain implementation gaps.

The current integrated report has 195 valid episodes, 96 verified A/B pairs and
861 usable reproduced event scores with zero arithmetic mismatches. Historical
invalid physical windows stay flagged and excluded. The material-curve pair
reproduced all six declared curve errors (baseline 35.09/58.89/70.33 mm;
conditioned 44.66/27.10/46.58 mm), with native failure in both arms. These are
anchored material-edge paths, not newly detected physical creases.

The calibrated liquid baseline exposed an initially empty upper bottle core.
The corrected lower core is independently material-free and contains 1,498
particles in retained calibration evidence. The populated-core pair completed,
with native success true/false and 159 reproduced sampled destination crossings.
Per-particle initial-region and held-exit witnesses were missing from its older
runtime; the independent audit labels all 159 as partial evidence, without
altering their sampled geometry. Current runtime retains initial frames/masks,
each particle's source hold and source frame. Independent cohort, exit ordering,
force/arm/label and tilt checks exclude inconsistent flow witnesses. Two retained
ball crossings are also partial, without any inconsistent source witnesses.

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

## Recognition prerequisite diagnostics (October 7)

Tool push, part/landmark touch, joint travel and button cycles now retain
synchronized observed prerequisite counts and current physical measurements.
False and not evaluated are distinct; sampling gaps and duplicate calls are
tracked. Success gates remain unchanged. Collector and MD/HTML render these
counts separately from conditioning errors. Four new counterexample tests and
the existing full gate pass: **283 tests**. Fresh matched live validation remains
required for these diagnostic fields.

## Sampled cloth bending persistence (October 7)

The optional endpoint probe now retains eight full material meshes, sampled every
four physics steps and at finalization. Its independent auditor checks constant
dt, bounded sample intervals, topology/identity/frame witnesses, matching final
coordinates, sustained new bending, pairwise vertex drift and angle range.
Diagnostic bounds are 0.1 s, 2 mm and 2 degrees. Four counterexample tests and the
full **287-test** gate pass. This is sampled candidate stability, not a unique task
crease, layering or grasp-force certificate. A fresh live matched pair is required.

## Requirement diagnostics for every implemented recognizer (October 7)

Observed counters now cover base pick/push and all physical adapters. They expose
held lift, support, release settling, named-arm handover, insertion aperture/depth/
axis, twist constraints/rotation, strike approach/retraction, source/target transfer
and cloth landmark deformation. A completed strike does not reuse stale hold
evidence; off-axis twist violations retain their measured values. Four additional
regressions and the full **291-test** gate pass. Source audit fingerprints include
the shared diagnostic recorder. Fresh matched live coverage is next.

## Button unpressed-start witness (October 7)

Button arming now accepts verified unpressed state immediately before first
moving-cap force contact, including a read-only stage-activation snapshot. It
retains raw start/press/release joint limits and positions plus contact interval
identity. Independent boundary validation checks ratios, time, body/arm and release;
historical missing witnesses remain partial. Six new regressions and the full
**297-test** gate pass. A fresh matched button pair is required for live proof.

## October 7, 21:18 UTC follow-up

Native predicate defaults are preserved through the actual RewardManager
constructors, with resolved arguments retained. The fresh block-language pair
completes after the `z_threshold=None` repair; both arms recognize two pickups
and one placement but fail the native full task. Fresh bowl placement succeeds
in both arms after single-finger brush handling, with consistent independent
release/separation/settling and named-support force evidence. Support evidence is
now audited even for placement programs without an on-top geometry condition.

Linear replay schedules multiple partial predecessors at their recorded physics
boundaries, including distinct boundaries in one command; it does not restore
DAG/choice/material or native game state. All 325 host tests pass. A three-cycle
button pair recognized every cycle in both arms. Its automatic monitor submitted
a separate multiple-boundary selected-stage proof, pending at this snapshot.
The existing bowl selected-stage proof succeeded with a 0.008497716 mm root
position residual. Missing cloth force/material correspondence, unique task
creases, full layering, full-volume transfer and full simulator state restoration
remain explicit limitations.

Independent finger/object contact audit now reconstructs raw force eligibility,
body/environment identity and local points. Contradictory contact measurements
are excluded even if their arithmetic reproduces. Missing historical bindings
remain partial. New contact sources serialize the required roots, finger mapping
and environment origin; fresh matched validation is being prepared.

## October 7, 22:56 UTC follow-up

The multiple-boundary button simulator proof completed: both preceding cycles
were verified and the selected cycle succeeded. The 16-case contact-binding
validation suite is submitted from frozen `e0f1d9c`; at 22:56, 12 jobs were Running
and 4 Starting. The MD/HTML report contains 245 valid full-task episodes, 121
verified pairs and 1,160 reproduced event scores with zero arithmetic mismatches.
Stage-only replay proofs remain separate. Single-ancestor routes inside concrete
dependency graphs are now implemented and host-validated; merged dependencies
and unresolved stateful programs remain unsupported.


### Distinct physical target regions (October 7)

Neighboring xylophone hit landmarks are about 42 mm apart; the original 40 mm
recognition neighborhoods overlap. A real impact near the preceding landmark
could therefore qualify for the next one. The native collision actor combines
bars into one mesh, so its collider path cannot identify a bar.

The optional `target_candidates` and `target_identity_margin_m` fields now
require actual force-bearing contact points to be closer to the requested live
landmark than to every competing live landmark by the declared margin. The
reviewed profile uses all eight physical `hit_0` through `hit_7` frames and a
2 mm distance margin. Ties, coincident landmark positions and neighboring-region
contacts do not qualify. Tool/target radii, held-force interval, pre-impact speed,
impulse and held retraction requirements remain in effect.

Each qualifying event retains every candidate descriptor, resolved pose/source,
physics step, selected index and contact distances. Independent validation
recomputes assignment from those retained points/poses and excludes inconsistent
windows from geometric aggregates. This certifies contact in a declared nearest-
landmark region, not an exclusive single-bar hit, calibrated bar surface identity
or musical timing. Multiple simultaneous contacts may include other regions.
Geometric conditioning still measures all pair contacts at the event, so its
maximum contact error can exceed the qualifying subset's recognition radius.
Older frozen radius-only reports retain their declared scope.


### Activation-time rigid kinematics and replay fidelity

Every fresh stage retains immutable `initial_object_states` for its observed
initial-position labels, with a capture physics step. For actual rigid bodies,
this contains environment-local root pose (metres and wxyz), live solver linear
velocity (m/s), live solver angular velocity (rad/s), actor path, environment and
readback API metadata. Velocities come from `SingleRigidPrim` getters inherited
by RoboDojo `RigidObject`; constructor defaults, policy commands and pose finite
differences are not used. Missing, failed or nonfinite APIs and nonrigid bodies
remain explicitly unavailable. The diagnostics do not change completion gates.

Selected-stage proofs compare bound source/replay captures at their respective
activation physics boundaries, linked to the source trace/report hashes.
MD/HTML adds separate root rotation (degrees), linear velocity (mm/s) and angular
velocity (degrees/s) residuals. Matching positions cannot hide changed rotation
or motion; opposite quaternion signs represent the same rotation. Wrong actor,
environment, timestamp, frame, units or API bindings are not comparable.
Historical captures with positions alone retain N/A in these new columns.

This is a scoped kinematic comparison, not a full simulator snapshot/restore or
a fidelity pass/fail certificate. Robot joints, drives, contact warm starts,
materials and game state are not covered. A fresh bowl A/B capture is being
prepared; live source capture plus a separately verified prefix replay is needed
before claiming observed kinematic replay evidence.


### Independently checked twist histories and retries

Fresh constrained twists retain every valid physics-step object/pivot pose up to
16384 samples per attempt, with hold interval/arm identity, one actual force row
per contacting finger and one actual part/target constraint force row. These
selected force rows certify the required quorum, not the complete contact
manifold. Final geometric contact scoring still retains its own actual points.
The recognizer's angle and off-axis limits remain independent of conditioning.

An independent validator reconstructs relative SO(3) increments using quaternion
axis-angle arithmetic, sums signed axial and off-axis rotation, and checks
contiguous steps, radii/depth, hold identity/counts, raw force and actor binding,
final timestamp and declared thresholds. An identical endpoint quaternion cannot
prove a full turn; moving the pivot and object together cannot claim relative
rotation. Wrong histories are excluded from rotation-event geometric aggregates,
while numerical errors and native/atomic flags remain available for diagnosis.
Old or explicitly truncated histories are partial evidence, not invented failures.
No torque or physical thread engagement is inferred.

Contact loss, arm change, sampling gaps or invalid twist constraints now archive
an earlier completed rotation if its native endpoint had not succeeded. The next
attempt cannot borrow its event-conditioned geometry. Completed successful stages
remain immutable. Eight targeted regressions cover full/reversed turns, moving
pivots, force/root/step corruption, cached-score exclusion and a full-turn retry.
A fresh screw A/B pair is needed for live history validation.

Incomplete twists also retain the greatest net directional progress among the
valid current/interrupted intervals saved by the observer. A separate
`twist_rotation_diagnostic` validator checks its pose/force history without
requiring the completed-turn threshold. A measured 90 degree partial turn
therefore stays a diagnostic with an unobserved completion event, not a successful
twist or native task. The history cap is explicit; truncated histories remain
partial. Empty invalid intervals do not repeatedly copy retained histories.


### Independent supported-release settling windows

Fresh supported-release events retain the required window of adjacent physics
poses, support snapshots, recorded robot-separation states and simulation dt,
plus the original settling anchor pose/step. Motion or loss of support resets
that window; a one-jaw brush also restarts separation and settling. The observer
still uses the same configured per-step and anchor-relative position/angle bounds.

The independent validator reconstructs every retained position/rotation change,
anchor-relative drift, final metrics, actual window duration, clock continuity,
object/support identity and raw upward support forces. Equal endpoints cannot
hide intermediate motion. Contradictory windows exclude settled-event geometry
from aggregates while preserving its arithmetic and native/atomic outcomes.
Historical missing pose windows stay partial; lifecycle-cached support forces
retain their separate persistence limitation.

A window of N adjacent sampled states spans (N-1)*dt seconds. It certifies the
declared bounded-motion window, not zero velocity or future immobility. A fresh
bowl pair uses twelve states in both arms instead of the earlier three, with
identical task prompts and geometric targets. Its measured duration and pose/force
proof are pending. Six host regressions cover hidden intermediate motion/rotation,
clock/force/root/recontact corruption, cached exclusion and runtime history reset.


### Live kinematic replay proof (October 7 local / October 8 UTC)

`geometry-kinematics-replay-validation-1006` replayed 74 whole controls and six
physics substeps of control 75, dropping its remaining four substeps. The required
force-held pickup and selected activation verified; the subsequent selected bowl
placement succeeded. Recorded and replayed activation physics steps are both 1286.
The named bowl root retained actual solver state in the same environment frame:

| Residual | Observed difference |
| --- | --- |
| Root position | 0.004078 mm |
| Root orientation | 0.006229 degrees |
| Linear velocity | 3.261018 mm/s |
| Angular velocity | 2.470848 degrees/s |

This proves one scoped source/replay comparison and successful selected action,
not a full simulator state restore or universal fidelity bound. Robot joints,
drives, contact warm starts, materials and game state remain unchecked. The job
uses the earlier three-sample settling profile; the new twelve-sample pose-window
pair is a separate live validation and is still pending. Replay runs are excluded
from full-task A/B episode counts.

Report SHA256: `c9eeed91769eb47a923fd0b7df86cf1f6ff4f5df0aff8a38e2313ce879ff4ae4`.
Proof SHA256: `ecb497d19fd786057bf5308f1743bc8e61b02845c6689738f31e857d919b9f53`.
Retained artifact: `geometry-kinematics-replay-validation-1006/prefix-validation.json`.
MD/HTML now displays the four separate residuals.


### Twist target binding in retained histories

Twist validation now checks the declared part/target labels and environment-frame
marker, plus the same actual constraint roots throughout the sampled interval.
Well-formed force rows from a different target cannot certify the requested
rotation. Full completion witnesses can bind earlier compact samples through
their retained named final pair; older partial diagnostics without those saved
labels remain partial. Fresh compact samples and partial-interval diagnostics
retain actual resolver label/frame metadata themselves. This is an archive
binding check; no missing labels are inferred from collider names.


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


### Live twelve-state settling validation (October 7 local / October 8 UTC)

`geometry-settling-history-1006` completed both bowl prompt arms. Native success,
required pickup and selected placement were true in both. Both twelve-state
settling histories independently validate with no contradictions, and all four
geometric-condition scores reproduce. Actual simulation dt is 4 ms, so each
window spans 44 ms. Maximum retained motion is:

| Measurement | Baseline | Conditioned |
| --- | --- | --- |
| Position change per adjacent state (mm) | 0.372703 | 0.462446 |
| Rotation change per adjacent state (degrees) | 0.508325 | 0.369913 |
| Position from settling anchor (mm) | 2.606504 | 2.486047 |
| Rotation from settling anchor (degrees) | 3.282015 | 2.646970 |

Bounds are 2 mm / 0.05 rad per step and 5 mm / 0.1 rad from the anchor,
identical in both arms. The observed bounded-motion interval certifies this
sampled settling event, not zero velocity or future immobility. The retained
artifact is `geometry-settling-history-1006/independent-contact-batch-validation.json`.
The fresh robot-joint captures and named-target twist histories are separate
pending runs; historical metadata is not filled in retroactively.


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


### Live replay comparison of actual robot DOFs

`geometry-robot-joints-replay-validation-1006` completed with a verified required
pickup prefix and successful selected placement. It replayed 82 whole controls
and two physics substeps of control 83, discarding the remaining eight substeps.
Activation is at recorded physics step 1362. Both named robot articulations have
actual, independently bound readbacks: twelve revolute DOFs and four prismatic
gripper DOFs, with no unavailable joint comparisons. Maximum differences are:

| Activation measurement | Difference |
| --- | --- |
| Revolute joint position (degrees) | 0.001575 |
| Revolute joint velocity (degrees/s) | 0.103488 |
| Prismatic joint position (mm) | 0.024606 |
| Prismatic joint velocity (mm/s) | 8.925289 |
| Bowl root position (mm) | 0.321322 |
| Bowl root orientation (degrees) | 0.379657 |
| Bowl linear velocity (mm/s) | 26.821973 |
| Bowl angular velocity (degrees/s) | 68.966259 |

The largest prismatic rate difference belongs to robot1 joint7. Small joint
position differences do not establish equal contact dynamics; the larger object
velocity differences remain visible. These are scoped measured residuals without
an arbitrary fidelity pass threshold. The runtime predates command-target
captures, so it provides no drive-buffer comparison. The new command-target
capture/replay pair remains separate. This selected-stage proof is excluded from
full-task A/B episode counts.

Report SHA256: `ded403aabfc22ca147bcf4d0693166ef48b57c85d57cf755d54821755179da65`.
Proof SHA256: `b7ec4b1d3b0a0905f848638bb8ca3afdb4a596e116a5df93005c9612e2e42dd6`.
The raw artifact is `geometry-robot-joints-replay-validation-1006/prefix-validation.json`.

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

The current gate passes 416 offline atomic tests, including six completion-event
counterexample and independent-audit tests. MD and HTML expose completion
witness status separately from scalar geometry. Fresh pickup/settled-placement
and push A/B validation is the next live check; offline tests are not live proof.

## October 7: diagnostic scalar tables and finite-ball observation

The MD/HTML report now includes a separate retained-twist-interval table in
degrees: signed net rotation, progress in the requested direction, off-axis
rotation and required travel. Consistent or explicitly partial interval
evidence is shown; contradictory values are excluded. These are diagnostics
from one contact-constrained interval, not completed-action scores, torque or
summed rotation across regrasp intervals.

A separate finite-material table reports independently reconstructed enclosing
mesh radius in mm and recorded closure. `geometry-ball-finite-mouth-1006`
completed both arms from frozen `3d9fd79`: both native tasks and both pour stages
failed; both cup pickups succeeded. Four actual sphere mesh bounds independently
validated, each approximately 5.000000257 mm; their meshes have open seams, so
no solid volume is inferred. Six contact snapshots and six geometry scores
reproduced. No source-qualified target crossing occurred. Initialization bounds
and candidate aperture passage alone do not establish a held-and-tilted exit.

The baseline recorded two outward candidates (one passing the sampled finite
aperture fit and one exceeding the opening-rotation sampling guard). The
conditioned arm recorded four candidates (two passing and two failing fit).
Historical candidate summaries do not retain the per-crossing hold/tilt state,
so those specific missing physical gates cannot be independently diagnosed from
the summary counts. Retaining bounded raw candidate witnesses with same-step
qualification evidence is the next instrumentation priority.

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

## October 8: live qualified completion and command-buffer replay

`geometry-qualified-completion-1006` completed all four full-task cases from
frozen `700d387`. Both bowl native tasks, pickups and supported placements
succeeded. The four new stage-success snapshots independently passed completion
clock/qualification checks; 16 retained contacts and two release/settling windows
also validated. Eight geometry scores reproduced. At qualified bowl pickup, worst
vertical contact error was **24.102474 mm baseline / 5.936854 mm conditioned**,
against 10 mm. At qualified supported settling, full orientation error was
**14.173171 / 19.002117 degrees**, against 30 degrees. This is one episode per
arm, with different observed contact populations, not a statistical steering
estimate. Both T-block native/action goals failed; two stage-success targets
were unobserved and ten contact conditions had no eligible contact at their
required event. Missing measurements remain N/A.

The command-buffer capture pair from `3467649` also completed both native bowl
tasks and both pick/place observers. Its selected-stage replay
`geometry-drive-targets-replay-validation-1006` from `700d387` verified the
physical pickup prefix: 82 complete controls plus eight substeps of control 83,
discarding two, activated at physics step 1368. All 16 actual solver joints and
16 separate position/velocity command buffers were compared with no unavailable
readbacks. Maximum residuals:

| Readback | Revolute position | Revolute rate | Prismatic position | Prismatic rate |
| --- | ---: | ---: | ---: | ---: |
| Actual solver state | 0.000232226 degrees | 0.099811262 degrees/s | 0.004944741 mm | 2.730621025 mm/s |
| Separate command buffers | 0.000013660 degrees | 0 degrees/s | 0.000027008 mm | 0 mm/s |

Bowl-root residuals were 0.007167137 mm, 0.009353926 degrees, 5.431972716 mm/s
and 5.311638728 degrees/s. The selected placement failed despite the verified
prefix; the full source capture succeeded. This does not establish identical
policy cache, future contact evolution, full controller state or full-state
restoration. No arbitrary fidelity threshold was applied. Replay is excluded
from full-task A/B counts.

Report SHA-256:
`81edffc7cd4eafb340b89c02dbaf62543db4d999b5a2ff902eb9d8afcc9a42bf`.
Proof SHA-256:
`505be7292d8b67defbdf2efd936935c41a65276c7600bbba36725dca8c131779`.

The ball/liquid candidate-witness quartet from `f18acbb` is running at
high-9000 with byte-identical source programs/prompts. Only the existing seed-0
25k checkpoint was found in a nontruncated inventory of this known training
lineage; no additional checkpoint outcome is inferred.

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
