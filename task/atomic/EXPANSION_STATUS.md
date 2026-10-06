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
| `geometry-breadth-1006` | 12 | Submitted | Actual contacting-arm TCP orientation, initial object selection, returned button cap, receiving-hand offset, tool heading and strike retraction path |
| `geometry-body-contacts-1006` | 4 | Submitted | Stack release/settling using contact APIs enabled after task objects load |
| `geometry-constrained-1006` | 4 | Submitted | Matching nut/bolt constrained signed rotation, pivot/contact/axis endpoints; actual cloth crease midpoint/full tangent pose |
| `geometry-tool-contacts-1006` | 4 | Submitted | Fresh mallet strike/retraction and align-block tool heading with task-body contact enablement |

The bottle retry retained the exact program/checkpoint/runtime package. It ended
with client code 143 and no completed native episode. Archived logs show a policy
websocket keepalive timeout; diagnosis is ongoing. It is an infrastructure failure,
not a conditioning score or policy action failure.

## Implemented additions

- Contact APIs are enabled after each scene load, including task object bodies.
  Earlier packages enabled only robot bodies; grasps worked but object/object
  tool and support contacts were not observable. Fresh stack pairs validate the
  corrected lifecycle. All contact/support history is cleared on episode reset.
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
  now have local counterexample tests; live face bindings are pending.
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
calibrated pour/fit bindings, live cloth patch layer bindings and crease intersection relations, and actual
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

A second CPU job exports the three `Top_Long` garment topologies used by
`fold_clothes` and inventories installed cloth/particle Python APIs. It uses no
GPU and is counted in the shared 32-job window. Source code now includes physical
opening trace and conservative interior-core calibration, selected cloth patch
layering, optional stream direction, and small-retreat insertion handling.
These later additions have local regression evidence; fresh calibrated bindings
are prepared separately from already immutable queued packages.
