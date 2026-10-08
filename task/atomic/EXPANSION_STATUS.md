# Additional conditioning implementation and live validation

Updated October 7, 2026. Kernel tests, live measurements and matched policy
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

October 8 UTC / October 7 local, 02:40 UTC: combined MD/HTML has **287 valid
episodes, 142 verified A/B pairs, 1423 reproduced event scores**, zero arithmetic
mismatches and ten separately excluded historical windows. All new contact,
referent, nominal-frame and distinct-region pairs are collected. The fork pushed
`21405e1` and passes 378 tests. New independent proofs:

- Distinct strike regions: 12 consistent completed witnesses, 102 consistent
  contact snapshots, no contradictions; 8/4 physical strikes and native false/false.
- Nominal grasp frames: 29 consistent snapshots, all 16 added scores reproduced;
  both pickups in each arm. Full rotations 0.73–0.74 degrees baseline versus
  0.33–0.41 degrees conditioned; native false/false. One conditioned contact is
  0.1064 mm outside the position bound. One episode per arm is descriptive only.
- Isolated initial referents: all eight cases collected, all candidate/force
  witnesses consistent; every first selection wrong. Point selection's fresh
  force/root pair is also collected with consistent witnesses in both arms.
- Both bowl capture pairs: native true/true, all 16 activation readbacks observed
  across the two profiles. The later boundary has actual nonzero solver velocities.
- New high-9000 jobs: scoped kinematic replay `rb-kinematics-replay-1007-000-5z4z`
  and the two-case screw history batch from `21405e1`. No completion is inferred
  until collection/proof. Replay monitor submitted it after validating the source.

The latest twelve GPU admission observations since 00:00 UTC had no existing
allocations and no rejection. Raw ledgers and adjacent-user evidence are retained.
No healthy evaluation was cancelled.


October 8 UTC / October 7 local, 00:14 UTC: all sixteen contact-binding and all
eight contact-frame cases are collected. Independent contact-binding checks:
455 consistent snapshots, 16 historical partial pair snapshots, zero
contradictions. Contact-frame checks: 149 consistent snapshots and thirteen
consistent declared-radius strike windows; 46 added scores observed and
reproduced, 18 events absent, four contacts absent at the event. Missing tool-push
contacts remain explicit. The fork passes 365 tests and pushed `ace3b02`.

A fresh nearest-landmark-region strike pair is Running at high-9000 from
`ace3b02`; all eight target frames and a 2 mm distance margin prevent neighboring
40 mm neighborhoods from qualifying the wrong requested landmark. Prompts and
geometric scoring definitions remain byte-equivalent to the source treatment.
Physical bar identity/timing is not inferred from the merged collision actor.

Seven of eight isolated referent-factor cases are collected: every observed
first choice was block_2, not the calibrated target. Candidate geometry and actual
root/finger-force/arm/timing witnesses reproduced without contradiction. The
point-selection root/force pair has its conditioned arm collected and baseline
Running. Both attainable nominal grasp-frame arms are Running. Pending results
are not included as completed pairs. New evidence sections in the three detailed
docs distinguish recognition, measurement and policy success.


October 7 snapshot, 23:42 UTC: the integrated MD/HTML contains **259 valid
episodes, 128 verified A/B pairs and 1237 usable reproduced event scores**, with
zero arithmetic mismatches and ten historical incompatible recognition windows
excluded. Fourteen contact-binding cases are collected; two screw cases remain
Running. Independent contact checks retain 437 consistent snapshots, 16 partial
older tool-pair snapshots and no contradictions in those fourteen reports.
These are snapshot counts, not distinct actions or force-closure certificates.
Hashes and checks are in the suite's `independent-contact-validation.json`.

All eight new `geometry-contact-frames-1006` cases are submitted at high-9000
from frozen `ecd7003`: block pickup, T pushing, held tool pushing and mallet
strikes. Four are Running and four Starting. Explicit named-frame pose and
z-direction conditions retain actual contact positions. Pickup/push also test
point and reference-origin box constraints. Prior scoring definitions and
recognition are preserved, with prompt text added only to the conditioned arm.
The generator's task coverage metadata was corrected after dry-run reporting
found stage rows where task rows were required; packaged programs/runtime stayed
unchanged. The fork now passes 353 host tests, including the metadata regression.

The concrete graph's single-ancestry placement start proof completed separately:
132 whole controls plus five substeps of control 133; required held pickup and
activation verified, block-root position difference 0.000725 mm. Subsequent
placement failed. Prefix proof does not establish selected-action success or
full-state restoration. MD/HTML keeps it outside full-task A/B counts.

Next, selected-referent validation records immutable actual candidate roots and
environment identity and independently checks first-selection raw finger forces,
counts, arm and timing. Root aliases fail on activation. Corrupt witnesses become
`invalid_selection_witness`, not a reproduced adherence score. Historical missing
roots remain partial. A fresh matching live selection pair is being prepared.

October 7 snapshot, 18:09 UTC: combined MD/HTML has **213 valid episodes,
105 verified A/B pairs and 966 usable reproduced event scores**, zero arithmetic
mismatches and ten separately excluded historical recognition windows. Both
endpoint cloth arms are collected: native true/false, with new bending candidates
in both; sampled stability is unavailable in this older frozen pair.

The prerequisite tool/button four-case suite is collected. Both tool arms lack
recorded grasp and tool/block contact throughout the observed windows; support
remains measured. The conditioned button arm recognizes its first red cycle;
other cycles remain missing. A reproduced recognizer blind spot occurs when the
first force sample has already compressed the cap below the unpressed threshold.
The fix now retains adjacent unpressed state and independently auditable raw
cycle witnesses, including an activation snapshot for repeated presses.

All sixteen cases across eight further tasks are submitted at high-9000 from
`017e523`: bowl release, bottle handover, screw twist, charger insertion, strikes,
actual-mouth liquid transfer, cloth deformation/history and direct T pushing. At
18:09 nine jobs were Running, eight Starting and one Queueing, including the two
previous temporal cloth cases. Collectors/report refresh continue automatically.

October 7 snapshot, 17:58 UTC: the endpoint-only cloth baseline is collected
with native success true and all three landmark fold observers false. Actual
9665-vertex/19000-face garment readback produces 2501 selected bend hinges, 149
length-qualified open chains and 70 branched networks; 142 overstretched hinges
are excluded. The longest open chain is 54.41 mm. Network edge-length sums do not
represent unique physical crease lengths. No temporal witness exists in this
frozen endpoint-only run; the fresh `978b3ec` persistence pair is running/starting.

The fresh table-level tool-push baseline is collected: native failure and no
qualified held-tool strokes. Active rigid callbacks report direct fingers/block
contact and support, with no tool/block force pair. The diagnostic tool/button
pair continues running. Requirement diagnostics now cover all implemented
families, with 291 passing host tests.

October 7 snapshot, 17:48 UTC: both actual-mouth ball cases are collected. Both
pick up their cup, native tasks fail, and neither produces a completed pour or
destination crossing. The liquid actual-mouth pair retains 13 fully consistent
destination witnesses, separate from the older source-core comparisons.

The four fresh prerequisite-diagnostic cases are running from `ae4a2d0`:
matched `align_blocks` and `press_by_number`. Automatic reports and the retained-
exception watchdog are alive. The full-mesh cloth endpoint pair continues
sampling policy controls with no retained simulator exception.

Cloth sampled-persistence implementation now passes 287 host tests. It retains
eight actual meshes and checks persistent bending plus position/angle stability
over physical time; it does not modify action success. The three instrumentation
docs are updated, and a fresh live validation pair is next.

Current October 7 snapshot, 17:41 UTC: the actual-source-mouth liquid A/B pair
is collected. Native task success is false/true and both atomic partial-cohort
pour observers succeed. All 10 baseline and 3 conditioned destination crossings
independently reproduce with consistent held/tilted source-mouth evidence. This
certifies outward particle-center aperture passage, not whole-fluid volume. The
ball baseline picks up its cup but has no completed pour or destination crossing.
The conditioned ball and both cloth endpoint cases continue running. Both fresh
independent tool-push cases are submitted at high-9000, frozen at `01178f2`.

New recognition prerequisite diagnostics cover tool push, part/landmark touch,
joint travel and button cycles. Separate true/false/not-evaluated counts expose
missing observed requirements without converting them into geometric scores or
policy-failure labels. Duplicate steps and sampling gaps are tested. All **283
host tests pass**; the core three docs and MD/HTML renderer are updated. Fresh
matched live validation is the next execution step.

Current October 7 snapshot, 17:19 UTC: the additional cloth and source-witness
six-episode batch is collected. The integrated MD/HTML has **201 valid episodes,
99 verified A/B pairs and 913 usable reproduced geometric event scores**, with
zero arithmetic mismatches. Fresh liquid source evidence is consistent for all
64 baseline and 80 conditioned crossings. Both partial-cohort observers completed;
native success is false/true. Both ball runs picked up the cup but supplied no
completed core-pour observer or destination crossing. Both cloth native tasks and
fold observers failed; the opt-in native cloth callback probe returned zero
garment headers, points and finger forces despite active rigid callbacks.

The persistent physical-prefix replay fix is pushed as `bc41fa2`. Its selected-
stage validation `rb-prefix-pour-1007-000-cd4w` has completed and collected:
`prefix-validation.json` is `observed_verified_prefix`, with both pickup success
and `prefix_boundary_verified` true. The 45-action prefix retained a two-finger
right-arm held lift (56.31 mm observed displacement, 87 consecutive contact
samples). The selected pour then ran 400 policy actions/13 checkpoint inferences
and failed its endpoint. This stage-only proof is excluded from full-task A/B
aggregates. All four source-mouth `liquid_mouth`/`pour_mouth` cases were submitted
at high-9000 from frozen `67318bf` after 272 passing host tests. The new gate requires actual outward aperture
passage while held/tilted; source-core departure alone does not qualify. Balls
use a center crossing plus whole-mesh target containment, not whole-ball mouth fit.

Next implementation adds opt-in full endpoint garment readback and initial/final
adjacent-face bending candidates, with invalid topology/stretch exclusions and
explicit angles/lengths. These remain diagnostics rather than unique physical
crease or action-success claims. A fresh matched cloth validation is being prepared.

At 17:27 UTC both cloth endpoint cases were Running: `rb-cloth-bend-1007-000-000-cwzf`
and `rb-cloth-bend-1007-001-000-8289`, frozen at `b8cf398`. Programs/prompts exactly
match the prior material-curve pair; the new flag captures full garment endpoints.
All four mouth cases were also Running. No new GPU-memory rejection was reported
by those admission monitors at this snapshot.

The next task activation fix removes the unnecessary lifted-tool prerequisite
from `align_blocks`. Tool strokes keep their own strict hold/contact/support/motion
checks and can start at table level. Lifted-tool pickup is optional, and direct
finger/block pushing does not qualify. The current source passes 279 host tests;
a new matched tool-push comparison is being prepared.

October 7 snapshot, 16:07 UTC: all twenty repaired-runtime episodes have
been collected after recovering local NFS quota failures. The integrated MD/HTML
contains **195 valid episodes, 96 verified A/B pairs and 861 usable reproduced
event scores, with zero arithmetic mismatches**. Fresh strike evidence has sixteen
consistent windows; fresh bowl/handover evidence has five consistent completed
windows and no inconsistent windows. Historical invalid archives remain flagged.

The material-curve pair reproduced all six full edge-interior Hausdorff errors:
baseline sleeve-left/right/body 35.09/58.89/70.33 mm; conditioned
44.66/27.10/46.58 mm. Both native tasks failed; the conditioned left-sleeve observer
completed. These preserve selected anchored material paths, not discovered creases.

The populated-liquid pair has native success true/false, observed bottle-mouth
translation errors 38.60/28.25 mm and full orientation errors 164.49/171.72 degrees.
Its 73/86 destination crossings reproduce numerically, but all have partial
historical source-witness evidence. The new validator found no inconsistent
source witnesses. Current runtime saves initial region frames/masks and every
particle's held-exit manifold; fresh source-witness validation is required.

The node-local checkout and operational state preserve their original home paths
through symlinks. Cloud artifacts and NFS backups remain retained; collectors and
MD/HTML refresh have resumed. Audit generators now preserve prior files on write
failure. A fresh `geometry-cloth-contact-probe-1006` pair is running on clean
admitted GPUs at high-9000, probing native particle-cloth callbacks without adding
rigid bodies. Material/finger force correspondence is still unverified.

The following dated snapshots describe earlier stages of the work.

October 7 snapshot, 06:56 UTC: all previously submitted jobs are terminal. The
integrated report contains **175 valid episodes, 86 verified matched pairs and
679 reproduced geometric event scores, with zero reproduction mismatches**.
The dated ledger below is retained as historical status, not the current queue.

Seven fresh pinned-protocol suites failed before evaluation because the demo
runner called `update_obs` on the infer-only checkpoint. This is an infrastructure
failure, not zero adherence. The explicit bridge is validated with the actual
demo runner and real websocket/JPEG/array transport, but GPU rollouts still need
fresh frozen pairs. Replacement scopes cover bottle handovers, combined cloth
geometry, charger sections, populated liquid cores, material curves, ball-pour
initialization and bounded initial block selection. Checkpoint, layout and
geometric scoring targets stay fixed. Selection text removes the accidental
`np.float64(...)` rendering without changing its numerical target.

At 07:16 UTC all 14 replacement cases were submitted: eight Running and six
Starting. Controllers, report refresh and the retained-exception watcher are
active. No completed replacement episode was available at that snapshot.

Additional witness audit: all eight baseline xylophone strike windows were
consistent. The conditioned arm has seven consistent windows; `strike_7` joined
an aborted impact to a later successful strike. The raw trace/outcomes and prior
derived results are retained. Updated MD/HTML excludes that incompatible contact
score and retraction path, leaving **678 reproduced geometric event scores**
across the current integrated evidence, with zero arithmetic reproduction
mismatches and one separately reported recognition witness failure. The runtime
attempt-archive repair is covered by 240 offline tests and needs fresh live runs.

Broader retained-boundary audit: seven completed handover/release windows passed,
three archives were inconsistent (two conditioned bowl releases and one baseline
bottle giver event), and 64 windows had no complete events. These are boundary
checks, not reconstruction of all intermediate contacts. Four affected bowl
release scores are excluded, while the valid handover receiver-only score stays.
The integrated count is now **674 reproduced event scores**, with zero arithmetic
mismatches and **four inconsistent witness windows** including the strike.
Raw reports and previous derived results remain retained. Current source passes
245 offline tests. Sixteen fresh cases are active, including the strike pair;
the repaired selection baseline has reached real checkpoint inference.

07:30 UTC progress: five replacement episodes are valid, including both block-
selection arms; both selected the wrong initial block. The integrated report had
180 valid episodes, 87 verified pairs, 712 usable reproduced event scores and
nine independently flagged boundary archives (including original-screen
handovers and fresh runs with the older frozen runtime). These failure counts
are separate from zero arithmetic mismatches. Raw-boundary revalidation occurs
during rendering so long-lived older controllers cannot bypass new checks.
Four additional bowl-placement/bottle-handover cases use the corrected runtime.

The CPU contact-binding inventory completed: all 267 installed `.pyi` stubs were
scanned, five matched, none exceeded the size limit. It exposes generic contact
callbacks, collider face IDs and point-instancer IDs, but establishes no actual
cloth-particle impulse readout. Native face/instancer metadata is now retained
in raw contact rows, explicitly distinguished from cloth solver identities.

All pairs use the 25k checkpoint, layout/seed 0, one episode per arm, reservation
`cosmos-rollout-luemzvvo`, priority `high-9000`, no burst, and the 512 MiB/two-sample
GPU admission guard. The global controller window allows at most 32 queued plus
executing jobs. Frozen packages never change when source instrumentation changes.

Ledger snapshot: 2026-10-06 23:18 UTC.

| Suite | Cases | Collected evidence at this update | Conditions |
| --- | ---: | --- | --- |
| `geometry-expansion-1006` | 16 | 16 collected; 15 valid episodes; 27 reproduced scores; 0 mismatches; 0 pending | New grasp band, first-lift displacement/full orientation, push contact side, cap contact offset, handover root pose |
| `geometry-validation-1006` | 16 | 16 collected; 16 valid episodes; 54 reproduced scores; 0 mismatches; 0 pending | Release yaw/full pose, failed push endpoint, pre-contact mallet pose, tool heading, annotated charger insertion |
| `geometry-support-1006` | 10 | 9 collected; 9 valid episodes; 48 reproduced scores; 0 mismatches; 1 pending | Persistent support, raw body-pair diagnostics, full material mesh export |
| `geometry-materials-1006` | 4 | 3 collected; 3 valid episodes; 20 reproduced scores; 0 mismatches; 1 pending | Real garment landmark destination, tangent normal and crease drift; liquid scene capture/pickup, not calibrated liquid transfer |
| `geometry-breadth-1006` | 12 | 8 collected; 8 valid episodes; 19 reproduced scores; 0 mismatches; 4 pending | Actual contacting-arm TCP orientation, initial object selection, returned button cap, receiving-hand offset, tool heading and strike retraction path |
| `geometry-body-contacts-1006` | 4 | 4 collected; 4 valid episodes; 29 reproduced scores; 0 mismatches; 0 pending | Stack release/settling using contact APIs enabled after task objects load |
| `geometry-constrained-1006` | 4 | 2 collected; 2 valid episodes; 21 reproduced scores; 0 mismatches; 2 pending | Matching nut/bolt constrained signed rotation, pivot/contact/axis endpoints; actual cloth crease midpoint/full tangent pose |
| `geometry-tool-contacts-1006` | 4 | 2 collected; 2 valid episodes; 10 reproduced scores; 0 mismatches; 2 pending | Fresh mallet strike/retraction and align-block tool heading with task-body contact enablement |
| `geometry-crease-segments-1006` | 2 | 1 collected; 1 valid episodes; 18 reproduced scores; 0 mismatches; 1 pending | Actual finite material-endpoint segment coincidence alongside patch layering |
| `geometry-cloth-patches-1006` | 2 | 1 collected; 1 valid episodes; 15 reproduced scores; 0 mismatches; 1 pending | Model/asset/topology-verified local garment patch coverage and layer gaps |
| `geometry-pour-cores-1006` | 2 | 2 terminal collection attempts; 0 valid episodes; 0 reproduced scores; 0 mismatches; no pending jobs | Declared initial whole-ball core cohort, actual mouth pose, crossing XY/direction and final core enclosure |
| `geometry-key-fit-1006` | 2 | 0 collected; 0 valid episodes; 0 reproduced scores; 0 mismatches; 2 pending | Actual key mouth/tip, closed blade collider section/clearance and shoulder gap |
| `geometry-surface-gaps-1006` | 2 | 0 collected; 0 valid episodes; 0 reproduced scores; 0 mismatches; 2 pending | Actual selected-patch triangle-boundary gap alongside layers |
| `geometry-bottle-runtime-1006` | 2 | 0 collected; 0 valid episodes; 0 reproduced scores; 0 mismatches; 2 pending | Original bottle geometry with rigid readback fix and pinned websocket protocol |
| `geometry-cloth-runtime-1006` | 2 | 0 collected; 0 valid episodes; 0 reproduced scores; 0 mismatches; 2 pending | Combined patch/layer, finite-chord and boundary-gap conditions with pinned protocol |
| `geometry-liquid-cores-1006` | 2 | 0 collected; 0 valid episodes; 0 reproduced scores; 0 mismatches; 2 pending | Verified model-specific mouth pose and partial-cohort particle crossings |
| `geometry-charger-tips-1006` | 2 | 0 collected; 0 valid episodes; 0 reproduced scores; 0 mismatches; 2 pending | Both actual leading-tip frames and middle-slot throat entry |
| `geometry-pour-initialization-1006` | 2 | 0 collected; 0 valid episodes; 0 reproduced scores; 2 pending | Corrected early contact API setup and guarded reset; actual ball cohort/mouth/flow conditions |
| `geometry-selection-query-1006` | 2 | 0 collected; 0 valid episodes; 0 reproduced scores; 2 pending | Actual three-block bounded initial-layout candidate query and first sustained selected-object contact |
| `geometry-material-curves-1006` | 2 | 0 collected; 0 valid episodes; 0 reproduced scores; 2 pending | Model-bound ordered material-edge path preservation, patch layers and surface gaps |
| `geometry-charger-sections-1006` | 2 | 0 collected; 0 valid episodes; 0 reproduced scores; 2 pending | Both actual leading tips plus closed local shaft-section fit/clearance |

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
broader calibrated pour/fit bindings, matched cloth patch/finite-segment and
new material-curve validation, discovery of newly formed physical creases, and actual
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

### Terminal collection reconciliation

A finished collector without `eval_report.json` now has failed evidence status,
zero retained episodes and `rollout_outcome=unavailable`. It is not left pending
forever and does not become a native/policy failure. An actual retained report
takes precedence over collector exit. Both stopped old pour-core attempts are
now terminal in the ledger; the queued corrected pair remains distinct.
Reconciliation runs only after every collection worker has finished and stops
only the matching obsolete controller. Current source passes 224 atomic tests.

A host watchdog now checks retained explicit simulator exceptions on older
frozen packages. It gives the original cleanup five minutes, rechecks job
identity/running state, uses the existing proof-gated stop helper, and records
every action. Normal task failure/reconnect/quiet contact cannot trigger it.
Collection-only failures are reconciled after all workers finish. The report
monitor and all active suite controllers were verified in the host PID namespace.
Current source passes 226 atomic tests; GPU validation remains in progress.

### Live held-strike witness validation

The collected `geometry-tool-contacts-1006` xylophone baseline recognized a
contact-held mallet pickup and all eight held strike/retraction intervals.
Native task success remained false. Its frozen physical recognizer uses a
15 mm retraction threshold; native reward history retains separate ordered bbox,
height and repeated 25 mm lift requirements. These outcomes are kept separate.

Actual mallet/xylophone force-contact XY errors were 1.23–6.33 mm; pickup contact
height error was 2.30 mm. Actual retraction-path maximum deviations were
3.38–32.88 mm. Only one of eight paths satisfied every declared path criterion;
some trajectories failed waypoint/start/backtracking constraints despite small
maximum deviation. The conditioned partner remains queued, so these observations
do not establish a conditioning effect.

`scripts/atomic/validate_strike_evidence.py` independently reconstructs pre-impact
relative velocity and retraction rise from retained poses, checks sample
continuity, impact force/landmark distances and same-arm boundary hold evidence.
All eight witnesses passed those consistency checks. Speeds were 0.252–0.574 m/s,
and rises 15.17–15.93 mm. It does not reconstruct unrecorded intermediate force
contacts or rewrite action outcomes. Altered speeds, hold intervals, retraction
poses and sample gaps fail; missing evidence remains unobserved/partial.

The retained validation, input report SHA256 and validator SHA256 are at:

`/home/mverghese/robodojo-expansion-state/geometry-tool-contacts-1006/strike-evidence-validation.json`

Reproduce using the benchmark Python environment:

```bash
python scripts/atomic/validate_strike_evidence.py \
  --report /home/mverghese/robodojo-expansion-state/geometry-tool-contacts-1006/runs/robodojo_25k_play_Xylophone_baseline/eval_report.json \
  --output /tmp/robodojo-strike-validation.json
```

The conditioning audit now cites specific live tool-contact and cloth patch/chord
measurements rather than leaving them marked as awaiting any simulator evidence.
New curve/shaft-fit/selection-query and corrected pour pairs remain pending.
Current source passes 229 offline atomic tests.

### Liquid initialization calibration correction

The first calibrated liquid baseline repeatedly failed before policy evaluation:
its source-only particle cohort was empty. The host watchdog retained the
explicit simulator exception and stopped that worker after the cleanup grace;
the queued same-runtime conditioned partner was also stopped using retained
proof. These are calibration failures with policy outcomes unavailable.

The prior +27.5 mm bottle core was material-free but above the settled liquid.
Review of the earlier valid `geometry-materials-1006` initial simulator snapshot
places the central population near bottle-root Z=−41.1 mm. A new 30 mm cube at
Z=−40 mm, XY=[0.309,−0.202] mm passes actual wall-trace and triangle/box material
exclusion. It contains 1,498 source-only particles of all 6,072 initial IDs.
Outside-core and scattered particles remain explicitly accounted for.

The generator now requires retained initial scene evidence for liquid cores and
checks population after independent material calibration. Runtime empty-cohort
errors retain population counts, real source/target poses and particle world
bounds. The fresh corrected comparison is `geometry-liquid-populated-1006`;
the failed frozen pair is preserved separately. Full native-liquid success and
physical partial-core transfer remain distinct.

Calibration, retained input SHA and full population partitions:

`/home/mverghese/robodojo-expansion-state/asset-calibration-1006/liquid-populated-core-validation.json`

Current source passes 232 offline atomic tests, including transformed-population,
initial-overlap, empty-core and invalid-ID counterexamples. Fresh runtime
population/transfer validation is pending.

### Live selected-surface-gap validation

The `geometry-surface-gaps-1006` conditioned garment episode completed with
native failure and no qualified fold observers. Actual selected triangle-boundary
distances were 41.52, 290.50 and 15.24 mm for left sleeve, right sleeve and body.
The body boundary was within its 20 mm target, but projected body-patch coverage
was only 0.01073 against the independent 0.50 requirement. Its measured overlapping
region had 15.89–22.86 mm layer gaps. Sleeve vertical gaps remained unobserved
because their patches had zero projected overlap. Local material-normal errors
were also measured. These are geometric measurements of a failed attempt;
they do not supply missing fold events or force-bearing cloth contacts.

All 18 required-event geometry scores reproduced. The baseline partner is pending.
At 23:39 UTC, the unified MD/HTML report contained 160 valid episodes, 72 verified
matched pairs and 566 reproduced required-event scores, with zero mismatches.
Both corrected `geometry-liquid-populated-1006` cases were submitted at high-9000
after the two-case batch fitted the existing global window.

## October 7, 21:18 UTC follow-up

Both native-defaults block-language runs and both concrete timed-button captures
are collected. Both block arms recognize two pickups and the first placement;
both button arms recognize all three physical cycles. Native full-task success
is false in all four. The earlier two block-language crashed runs remain retained
infrastructure failures with no completed episode. The automatic replay monitor
has submitted `rb-timed-button-proof-1007-000-6b88`, using the baseline's actual
partial predecessor at command 45 / physics 988 and selected boundary at command
108 / physics 1616. Its stage-only result is excluded from full-task A/B counts.

The completed bowl recontact pair recognizes `place_bowl1` in both arms, each
with 24 settling samples and 50/35 separated samples. Both native tasks succeed.
Raw release/settling and named-support force checks pass independently, with
report hashes in `geometry-release-brush-1006/release-brush-independent-validation.json`.
The unified MD/HTML reports include these new pairs. See the three measurement,
success and segmentation docs for remaining proof boundaries.

## October 7, 22:56 UTC follow-up

Multiple-boundary button proof `rb-timed-button-proof-1007-000-6b88` completed
with both prefix cycles verified and selected cycle success. It replayed 107
whole commands plus 6 substeps of command 108 and discarded 4 pending controls.
This is a separate selected-stage proof. The 16-case, eight-task contact-binding
A/B suite is submitted from `e0f1d9c` at high-9000: 12 Running / 4 Starting at
22:56. Programs/prompts are unchanged clones with retained source hashes.
The unified MD/HTML currently includes 245 valid episodes, 121 verified A/B
pairs and 1,160 reproduced event scores, with zero arithmetic mismatches and
ten excluded historical recognition windows.

### Latest scoped replay and settling audit

The live kinematic replay finished with a verified prefix and successful selected
placement: 74 full controls + six substeps of control 75, four dropped. Bowl-root
residuals: 0.004078 mm position, 0.006229 degrees rotation, 3.261018 mm/s linear
velocity and 2.470848 degrees/s angular velocity. Both activation clocks are 1286.
This is one named-root comparison, not full-state restoration; source/proof hashes
are in the three detailed docs. The report keeps this outside full-task A/B counts.

Source `179dd5f` passes 384 tests and adds independent bounded settling pose/support
windows. A fresh twelve-state bowl pair is submitted at high-9000 from that
runtime with original prompts/geometric targets. The screw pose/force-history
pair from `21405e1` is still running. Completed historical runs with no settling
pose history remain partial for that separate validation.


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

The current gate passes 411 offline atomic tests, including six completion-event
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
clock and action index. Total counts and outcomes continue over the whole
episode; a truncation flag prevents treating the retained subset as a complete
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
