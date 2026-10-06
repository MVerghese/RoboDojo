# Additional conditioning implementation and live validation

Updated October 6, 2026. Kernel tests, live measurements and matched policy
comparisons are separate evidence levels. Reports retain missing-event statuses
and separate physical units; one episode per arm makes no statistical claim.

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
| `geometry-breadth-1006` | 12 | 4 collected cases, 15 reproduced scores | Actual contacting-arm TCP orientation, initial object selection, returned button cap, receiving-hand offset, tool heading and strike retraction path |
| `geometry-body-contacts-1006` | 4 | 2 valid baselines, 14 reproduced scores; actual upward support in blocks and bowls | Stack release/settling using contact APIs enabled after task objects load |
| `geometry-constrained-1006` | 4 | 1 valid conditioned screw episode, 9 reproduced scores; baseline pending | Matching nut/bolt constrained signed rotation, pivot/contact/axis endpoints; actual cloth crease midpoint/full tangent pose |
| `geometry-tool-contacts-1006` | 4 | 1 valid align-block baseline; policy never acquired the tool; no tool scores | Fresh mallet strike/retraction and align-block tool heading with task-body contact enablement |
| `geometry-crease-segments-1006` | 2 | Submitted | Actual finite material-endpoint segment coincidence alongside patch layering |
| `geometry-cloth-patches-1006` | 2 | Submitted | Model/asset/topology-verified local garment patch coverage and layer gaps |
| `geometry-pour-cores-1006` | 2 | Submitted | Declared initial whole-ball core cohort, actual mouth pose, crossing XY/direction and final core enclosure |
| `geometry-key-fit-1006` | 2 | Submitted | Actual key mouth/tip, closed blade collider section/clearance and shoulder gap |
| `geometry-surface-gaps-1006` | 2 | Submitted after a global slot opened | Actual selected-patch triangle-boundary gap alongside layers |
| `geometry-bottle-runtime-1006` | 2 | Prepared; monitor awaits two global slots | Original bottle geometry with rigid readback fix and pinned websocket protocol |

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
and exact boundary proximity. It retains the physical cloth-grasp gap. Its
execution state will be added when packaging/submission is complete.
