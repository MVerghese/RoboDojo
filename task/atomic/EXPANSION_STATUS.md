# Additional conditioning implementation and live validation

Updated October 6, 2026. Kernel tests, live measurements and matched policy
comparisons are separate evidence levels. Reports retain missing-event statuses
and separate physical units; one episode per arm makes no statistical claim.

The original screen and all expansion results are now integrated into the same
searchable MD/HTML report. The original report paths are refreshed automatically,
and the combined home copy is at
`/home/mverghese/robodojo-expansion-state/integrated-report/`.
Suite-specific summaries and runtime provenance keep repeated tasks distinct.
See [EVAL_MATRIX.md](EVAL_MATRIX.md#integrated-original-and-expansion-report-october-6)
for regeneration commands and preserved original backups.

## Execution ledger

All pairs use the 25k checkpoint, layout/seed 0, one episode per arm, reservation
`cosmos-rollout-luemzvvo`, priority `high-9000`, no burst, and the 512 MiB/two-sample
GPU admission guard. The global controller window allows at most 32 queued plus
executing jobs. Frozen packages never change when source instrumentation changes.

| Suite | Cases | Collected evidence at this update | Conditions |
| --- | ---: | --- | --- |
| `geometry-expansion-1006` | 16 | 15 valid episodes, 27 independently reproduced scores; one conditioned bottle case failed twice before episode completion | New grasp band, first-lift displacement/full orientation, push contact side, cap contact offset, handover root pose |
| `geometry-validation-1006` | 16 | 16 valid episodes, 54 reproduced scores; no mismatches | Release yaw/full pose, failed push endpoint, pre-contact mallet pose, tool heading, annotated charger insertion |
| `geometry-support-1006` | 10 | 9 collected cases, 48 reproduced scores; remaining cases submitted | Persistent support, raw body-pair diagnostics, full material mesh export |
| `geometry-materials-1006` | 4 | Submitted | Real garment landmark destination, tangent normal and crease drift; liquid scene capture/pickup, not calibrated liquid transfer |
| `geometry-breadth-1006` | 12 | 5 collected cases, 17 reproduced scores | Actual contacting-arm TCP orientation, initial object selection, returned button cap, receiving-hand offset, tool heading and strike retraction path |
| `geometry-body-contacts-1006` | 4 | 3 valid episodes, 20 reproduced scores; verified bowl A/B pair with actual upward support | Stack release/settling using contact APIs enabled after task objects load |
| `geometry-constrained-1006` | 4 | 1 valid conditioned screw episode, 9 reproduced scores; baseline pending | Matching nut/bolt constrained signed rotation, pivot/contact/axis endpoints; actual cloth crease midpoint/full tangent pose |
| `geometry-tool-contacts-1006` | 4 | 1 valid align-block baseline; policy never acquired the tool; no tool scores | Fresh mallet strike/retraction and align-block tool heading with task-body contact enablement |
| `geometry-crease-segments-1006` | 2 | Submitted | Actual finite material-endpoint segment coincidence alongside patch layering |
| `geometry-cloth-patches-1006` | 2 | Submitted | Model/asset/topology-verified local garment patch coverage and layer gaps |
| `geometry-pour-cores-1006` | 2 | Baseline reset failed before an episode; both arms stopped and retained | Declared initial whole-ball core cohort, actual mouth pose, crossing XY/direction and final core enclosure |
| `geometry-key-fit-1006` | 2 | Submitted | Actual key mouth/tip, closed blade collider section/clearance and shoulder gap |
| `geometry-surface-gaps-1006` | 2 | Submitted after a global slot opened | Actual selected-patch triangle-boundary gap alongside layers |
| `geometry-bottle-runtime-1006` | 2 | Submitted; both queued | Original bottle geometry with rigid readback fix and pinned websocket protocol |
| `geometry-cloth-runtime-1006` | 2 | Submitted; queued | Combined patch/layer, finite-chord and boundary-gap conditions with pinned protocol |
| `geometry-liquid-cores-1006` | 2 | Prepared; automatic monitor awaits capacity | Verified model-specific mouth pose and partial-cohort particle crossings |
| `geometry-charger-tips-1006` | 2 | Prepared; automatic monitor awaits capacity | Both actual leading-tip frames and middle-slot throat entry |

The bottle retry retained the exact program/checkpoint/runtime package. It ended
with client code 143 and no completed native episode. Archived logs show a policy
websocket keepalive timeout **before a successful reconnect and rollout**; it
does not establish the later termination cause. The retry stops at step 168/700
and diagnosis is ongoing. It is an infrastructure failure,
not a conditioning score or policy action failure.

## Implemented additions

- Contact APIs are enabled after each scene load, including task object bodies.
  Earlier packages enabled only robot bodies; grasps worked but object/object
  tool and support contacts were not observable. The first fresh stack-block baseline validates actual block/block and
  block/table force contacts: native success, all three place observers successful,
  release/settled events and 36/27/65 support-seen samples. Other pair cases remain
  pending. All contact/support history is cleared on episode reset.
- Supported release retains verified transport through gradual same-arm jaw
  opening. One finger cannot establish transport and another arm cannot inherit
  it. Quiet support requires an earlier upward force contact, no lost event and
  unchanged poses of both bodies.
- Attempt-end measurements occur before reset even when success never happens;
  they do not fabricate earlier contact/lift/entry events.
- Calibrated local frames follow live roots and may enforce actual asset model
  identity. Explicit material-mesh paths exclude duplicate visual/collision
  proxies for solid volume and cross-section checks; missing paths fail closed.
- Finite interior-box unions measure whole-solid outside volume and independent
  vertex error. Opening polygons preserve holes and measure actual solid section
  area outside the allowed opening and requested physical clearance.
- Persistent material IDs support cloth points, tangent and crease line frames,
  and first downward opening crossings with position/velocity errors. Flow has
  source-held/tilted exit provenance and independent offline reproduction.
- Cloth folding observes newly lifted, closed, bent, layered and settled material
  landmarks. This does not certify finger/cloth contact, global cloth self-intersection. Explicit selected-patch overlap/layer checks
  now have local counterexample tests. Model-bound local patch IDs are calibrated for all three baked garments; a fresh matched pair is submitted and awaits live validation.
- Bolt-constrained twist uses continuous physical grip and nut/bolt contact,
  pivot radius/depth, unwrapped signed angle and bounded off-axis rotation. It
  does not certify mechanical thread engagement.

## Calibration and remaining work

A CPU worker successfully exported all 24 baked assets: key/slot, cup, charger/
socket, bottle, two mugs, goblet, five nuts, five bolts and five vases. The original
export and SHA identities are retained outside Git. Actual material sections are
being checked before assigning mouths, cavities or insertion clearance. An outer
bounding box is never labeled a cavity. Some authored meshes are nonmanifold;
those require reviewed geometric repairs or alternative physical representations,
not weaker acceptance thresholds.

Remaining work includes live validation of the corrected body contact lifecycle,
broader calibrated pour/fit bindings, live cloth patch/finite-segment validation, curved crease relations, and actual
cloth finger/particle contact instrumentation. Missing physical evidence is reported
explicitly and is not converted into a zero error.

## Evidence and storage

Operational state now lives at:

`/home/mverghese/robodojo-expansion-state/`

The original Lustre project hit its shared project **inode** limit. Controllers
and suites were copied to home storage and resumed using the same cloud job IDs;
original evidence and immutable packages were preserved. `storage-migration.json`
records the recovery. The original 49-task screen remains at:

`/lustre/fsw/portfolios/cosmos/projects/cosmos_base_cap/users/mverghese/robodojo-atomic-runs/eval-matrix-1004/`

Each suite produces `EVAL_MATRIX_REPORT.md`, `EVAL_MATRIX_REPORT.html`, raw native
reports and independently reproduced scores. GPU admission and neighboring-job
observations remain in separate ledgers outside Git.

A second CPU job successfully exported all three `Top_Long` garment models
(1, 4, 9) and inventoried the installed cloth/particle Python API declarations.
It used no GPU. Cloth position/velocity methods were found, but no cloth contact-
force readout was exposed in those declarations. The scope of that inventory
is retained; native binary APIs are not ruled out by a Python source inspection.

The new `cloth_patches` phase binds local same-side 30 mm geodesic patches to
actual topology, verifies live model/asset/topology hashes, and measures at
least 50% moving-patch coverage with 1–30 mm layer gaps (1 mm tolerance).
Unit/counterexample tests cover disconnected layers and identity mismatches;
live policy validation remains pending. These are local selected patches,
not complete garment regions or force-bearing cloth grasps.

Physical opening trace and conservative interior-core calibration, optional
stream direction, and small-retreat insertion handling also have local regression
evidence. Fresh bindings are packaged separately from immutable queued runs.

A rigid-pour core pair is calibrated for seed 0: cup-6 and vase-2 material-free
cores select the whole initial meshes of `sphere_1` and `sphere_6`. Mouth pose,
downward crossing XY/velocity direction and final convex-core enclosure are
bound. Sphere volume preflight fails closed, so the endpoint condition reports
whole-mesh box enclosure rather than a fabricated solid outside volume.

The first corrected-contact baseline evidence is retained at
`/home/mverghese/robodojo-expansion-state/geometry-body-contacts-1006/runs/robodojo_25k_stack_blocks_baseline/eval_report.json`.
Each place observer reported four current force contacts at settling completion,
with positive upward axial impulses. Recorded settling drift was 0.018, 0.191
and 0.548 mm for blocks 0, 1 and 2 respectively. This demonstrates the corrected
scene contact lifecycle in that rollout; it does not establish all tools or
receptacle bindings or a conditioned-versus-baseline effect.

Finite material-endpoint segment intersection and coincidence are implemented
and counterexample tested. The `crease_segments` garment phase adds initial
finite-chord preservation (20 mm symmetric Hausdorff distance). Curved creases
and force-bearing finger/cloth contact remain distinct gaps.

The corrected-contact stack-bowl baseline also completed with native success
and actual upward support. Only `place_bowl2` reached release/settled recognition;
`place_bowl1` recorded release without recognized settling and `place_bowl0`
recorded support without a release event. Native success is therefore reported
separately from these stricter atomic events; missing events are retained.

Actual selected-material surface proximity is implemented with exact triangle
checks and bounding-volume pruning, and has intersection, centre/vertex proxy
and exhaustive-pruning regression evidence. The `surface_gaps` garment profile
binds minimum boundary gap independently of patch coverage/layer ordering.
It has been submitted after a global execution slot opened; it does not substitute for physical contact.

A costly rigid-centre path was found while investigating the bottle stall:
centre readback built/serialized full meshes, and initial scene capture did so
even for meshes above its retained-evidence budget. Source now caches actual
vertex bounds, vectorizes USD transforms with Gf witnesses, and avoids unused
large initial exports. Regression tests verify equivalent centres and explicit
large-mesh omission. This is a candidate infrastructure fix, not a confirmed
termination diagnosis; an affected fresh matched pair will validate it.

The baked image's older websocket client omits the newer heartbeat options.
The parent repository already pins XPolicyLab `bb9a0b5f5136a74503b679af830bfd0a3a837d5c`,
whose synchronous client has a background event loop and whose server keeps
blocking model calls off its loop. New runtime packages now ship that verified
protocol on both sides instead of inheriting the older image copy. A real local
transport probe passed 650 ms/400 ms caller/model pauses with 50 ms heartbeat
interval and timeout, one connection and one model call. Raw proof is at
`/home/mverghese/robodojo-expansion-state/pinned-protocol-validation.json`.
This addresses a demonstrated connection-liveness risk; fresh simulator/policy
validation is pending and the bottle termination cause is still not established.

### Latest recognition evidence (20:21 UTC snapshot)

The conditioned screw rollout had native success and three recognized nut
pickups, but no recognized contact-constrained twist. The final nut-0 metric
showed actual shaft contact, 0.282 mm radius and 2.722 mm depth, with no current
verified grip or qualifying signed rotation. Nine scores reproduced with zero
mismatches; its baseline is pending. The align-block tool baseline had healthy
contact readout but no tool acquisition/contact, so dependent tool pushes never
started. These are observed policy/recognition outcomes, not successful adapter
validation or measured steering effects.

A fresh `cloth_geometry` profile combines all currently available calibrated
local garment geometry in one pair: patch layers/coverage, finite endpoint chords
and exact boundary proximity. It retains the physical cloth-grasp gap. It is prepared under `geometry-cloth-runtime-1006`; its monitor waits for two
slots in the global window before submission.

### Calibrated liquid binding

The new `liquid_core` phase has material-checked cores and actual mouth planes
for the bottle and all three configured cups. Actual file hashes/scaled bounds
are verified before model-specific frames are used. Mug cavity offsets of
roughly 14–18 mm are explicitly retained. The pilot conditions bottle-mouth
pose and source-qualified downward particle crossings through a restricted
20 × 20 mm mouth window. Local calibration and counterexample validation pass;
initial live source-cohort population, USD solver readback and policy transfer
remain pending. Partial transfer success requires at least one particle and is
reported separately from the native whole-liquid task.

### Automatically refreshed report index

The report monitor checks collected result changes every 30 seconds and
regenerates each suite's Markdown and HTML. A navigation/status index is at:

- `/home/mverghese/robodojo-expansion-state/EXPANSION_REPORT.html`
- `/home/mverghese/robodojo-expansion-state/EXPANSION_REPORT.md`

Each linked report states exactly which geometric conditioning was tested,
retains separate physical units and marks unobserved events explicitly. Frozen
experimental inputs are unchanged by report rendering. The index includes
prepared/queued suites as pending rather than claiming measured results.

### Paired charger leading-point entry

Both actual leading prong planes and separate middle-outlet throat apertures
are now calibrated. `held_multi_tip_insertion` observes the coupled entry under
continuous grip and physical charger/socket contact, rejecting single-tip entry
or a regrip after crossing. The `charger_tips` A/B profile scores each actual tip
frame at recognized insertion and episode end. Local real-asset calibration and
counterexamples pass; live validation is pending. The open prong meshes still
cannot support whole-solid cross-section/clearance claims, and tested higher
socket planes failed closed-trace calibration. These boundaries remain explicit.

The charger matched pair is frozen under `geometry-charger-tips-1006` and its
capacity monitor is running. The current suite/source checks include 198 passing
atomic tests, including wrong model/file/scale rejection and coupled insertion
counterexamples. These test results do not replace pending simulator validation.

### First matched pair with corrected support contacts

`geometry-body-contacts-1006` now has a verified `stack_bowls` A/B pair: both
arms reached native success, delivered prompting/runtime/checkpoint/layout match,
and geometric scores have zero audit mismatches. Baseline recognized bowl-2
placement; the conditioned arm recognized bowl-1 and bowl-2 release/settling.
The base bowl had no verified held transport in either arm, so its optional
placement observer stays unrecognized. Actual upward support was recorded;
conditioned settling drift was 0.436/0.174 mm for bowls 1/2. This is descriptive
single-episode evidence, not a statistical steering effect. Per-condition angles,
missing events and shared-event comparisons are in the automatically refreshed
`geometry-body-contacts-1006/EVAL_MATRIX_REPORT.html` and Markdown counterpart.

### Pour initialization correction (22:39 UTC investigation)

The `geometry-pour-cores-1006` baseline reached no episode. Retained historical
logs show late report API authoring, sphere shape deletion/view invalidation,
then `NoneType.link_names` during robot pose initialization. The cloud allocation
and its queued same-runtime partner were stopped; the original frozen evidence
is retained. This is an infrastructure outcome, not a geometric/policy score.

Source now installs task-body reports before tensor initialization, reuses them
during the later scene audit, and records invalid nested bodies without adding
independent report APIs. A bounded workflow guard preserves simulator failure
evidence and invokes the existing collection/cleanup trap. These changes have
local lifecycle/subprocess tests; live validation is still pending. A fresh
`geometry-pour-initialization-1006` matched pair retains the calibrated targets
and checkpoint, with the corrected runtime.

### Bounded initial-layout candidate discovery

Selection now accepts explicit labels or a bounded actual-layout query with
prefix/category and optional model/exclusion filters. The frozen inventory,
resolved labels and rejected candidates are retained and reproduced separately
from geometric values. Unknown required metadata, duplicate/aliased identities
and count violations fail. It preserves the first sustained contact and original
activation snapshots even if objects move or new layout labels appear later.
Local counterexamples pass. A fresh `geometry-selection-query-1006` stack-block
pair will exercise the calibrated initial XYZ target; live results are pending.
Language/game roles and arbitrary per-control/material candidates remain gaps.

### Continuous material-curve implementation and calibration

Added ordered persistent mesh-edge curve selectors with actual model/file/topology
binding and continuous polyline distance. Counterexamples reject endpoint and
vertex-set proxies, disconnected nearby layers and changed asset/topology
identities; dense independent Lipschitz bounds cover numerical scales.
All nine anchor/model combinations calibrate to actual authored routes of
15–69 vertices. Retained evidence is
`/home/mverghese/robodojo-expansion-state/cloth-asset-calibration-1006/material-curve-validation.json`.
The new `material_curves` phase adds three 20 mm initial path-preservation
conditions to the cloth landmark/patch/surface tests. Live validation is pending.
These anchored material routes do not locate a newly formed curved crease.

A completed CPU inventory inspected sphere/charger baked body declarations,
22 installed particle/cloth declarations and symbol records from 29 PhysX
binaries. The sphere root, visual and collision children all declare enabled
rigid bodies without transform resets. No verified per-material finger contact
force/identity readout was found in this inspected API subset. Declaration and
symbol inventory is not a proof that no internal API exists. Evidence:
`/home/mverghese/robodojo-expansion-state/physics-asset-calibration-1006/physics-inventory-summary.json`.

Failure-cleanup follow-up: forwarded external signals, actual node-cache output
placement, buffered fatal-marker draining and an ignored-TERM timeout are tested
with real subprocesses. The current host suite passes 213 atomic tests. Frozen
pour/selection cases preserve earlier runtimes; new curve cases include this
cleanup fix.

### Charger local shaft fit: former whole-solid blocker narrowed

Implemented `inside_trace_aperture` with explicitly selected actual prong meshes,
closed directed plane traces, winding/holes and clearance. It rejects missing,
reversed, duplicate, branching, crossing and coplanar traces. Global solid/volume
requirements are unchanged. One pre-policy common rigid pose fits both baked
prong cuts at 5/10/13 mm depth with 0.309 mm raw boundary clearance; each section
is about 5.018 mm². Six 4 mm lateral counterexamples fail. Thus local shaft fit
is now calibrated, while whole-prong volume/seating remains unsupported.
Actual evidence: `/home/mverghese/robodojo-expansion-state/asset-calibration-1006/charger-section-validation.json`.
The `charger_sections` phase adds four plane-fit conditions to the existing
leading-point A/B test; simulator validation is pending.

Live report snapshot at 23:08 UTC: 156 valid episodes, 72 verified matched pairs,
505 independently reproduced required-event scores and zero score mismatches.
Frozen old cloth-patch logs retain keepalive reconnections; the newer combined
cloth-runtime and curve packages ship the pinned background-loop websocket
client/server/codec. These remain distinct comparisons with immutable hashes.

### First live calibrated cloth-patch and chord results

`geometry-cloth-patches-1006` conditioned: valid episode, native failure, only
partial body-fold recognition. All three final patch overlap fractions are zero;
measured planar patch gaps are 18.69, 104.78 and 17.69 mm.
`geometry-crease-segments-1006` baseline: valid episode/native success, no
qualified fold observers; chord Hausdorff distances are 73.71, 78.77 and 78.77 mm.
Body patch overlap is 0.0553, with overlapping-pair gaps 13.79–38.70 mm.
The asset/model/topology material adapters now have retained simulator scores;
partner cases, curved-path scores and physical cloth contacts remain pending.

Report correction preserves these frozen results and their offline reproduction.
A retained `gap_observed=false` masks unmeasured vertical gap-error defaults from
statistics; coverage/separation stay measured. Per-condition component reasons
explain the resulting N/A. Pending curve/segment/section/selection rows now use
their actual units and checker fields. The current host suite passes 221 tests.
