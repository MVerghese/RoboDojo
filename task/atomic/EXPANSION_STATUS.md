# Additional conditioning implementation and live validation

Started October 6, 2026. This work extends the completed 49-task screen. A
source implementation, offline counterexample test, simulator measurement and
policy A/B comparison are distinct evidence levels. Every added condition must
retain its physical units and its missing-event status.

## Execution

The first suite has 16 baseline/conditioned cases across general pickup, charger
pickup, coin deposit, ball pouring (pickup observer), T pushing, button presses,
key insertion (pickup/handover observers), and bottle disposal. It probes a
different grasp band, first-lift displacement/full orientation, positive-side
push contact, offset button contact and handover exchange pose. Its packaged
runtime is immutable. These are prototype numerical targets: feasible surface
regions and frame conventions must be checked against live asset evidence.

The second suite tests the updated endpoint sampler and gradual-release
recognizer, full release orientation, pre-contact mallet orientation, tool
heading, and a physically recognized annotated charger insertion. It also
exports initial asset metadata, landmark frames and live mesh/material bounds.

Both suites use the 25k checkpoint, layout/seed 0, one episode per arm, strict
cosmos-rollout placement, priority 9000 and the existing 512 MiB/two-sample GPU
admission guard. Queued and executing jobs together must stay within the
authorized 32-job window across controllers. No run establishes statistical
steerability with one episode per arm.

## Work list

| Requested extension | Source/runtime status | Required live evidence |
| --- | --- | --- |
| Pick: contact region and held endpoint/orientation | Existing physical contact and rigid-frame scoring; first suite generated | Contact measurements, target feasibility and matched prompts |
| Initial object selection by point/relation | Explicit candidate snapshots and sustained-contact selection exist | Task candidate bindings, unique geometric eligibility, live selection |
| Hand/tool approach pose and orientation | Synchronized pre-contact samples exist | Fixed arm/active-part frames and live contact event |
| Place: release/settled pose, yaw, offsets and relations | Fixed loss of verified transport during gradual same-arm jaw release; final support diagnostics added | Reproduce settling on stack tasks and inspect signed support contacts |
| Push: contact side and final goal error on failures | New `attempt_end` sampler; started/completed stages retain episode-end measurements independently of action success | Failed-run position/orientation error with no fabricated interaction |
| Tool push/touch: active region, heading, endpoints/path | Existing contact/strike and trajectory observers | Asset calibration and live held contact/stroke/path evidence |
| Handover: exchange pose and receiving-arm references | Existing receiver-only event and rigid frames | Live exchange measurement and correct arm binding |
| Pour: source pose, tilt, spout/opening, stream | Rigid/fluid transfer adapters and persistent material coordinates exist | Verified interior/mouth/spout geometry, crossing and flow measurements |
| Insert: entry/offset/alignment/depth | Annotated charger tip and middle opening bound to physical insertion | Live tip/opening frame calibration, approach from outside, insertion contact |
| Insert: flush/seated/clearance | Entry recognition alone does not establish fit | Implement and validate explicit fit/crossing predicates |
| Twist: constrained axis/pivot/contact/angle | Contact-constrained unwrapped rotation exists | Nut/bolt or key/slot frame calibration and live held rotation |
| Fold: cloth contact, crease, patch destination/layer | Live material vertex/frame selectors exist; physical fold recognition unavailable | Implement cloth interaction and deformation evidence; rigid proxies forbidden |
| General receptacle containment | Existing finite convex-box whole-mesh check | Implement calibrated interior geometry beyond a single box and validate boundary cases |

## Applied fixes

- `attempt_end` conditions sample before scene reset, even when action success
  never happens or the action completed earlier. Unstarted stages remain
  unobserved. This endpoint cannot recover a missed contact/lift/entry event.
- Gradual release preserves an already verified held transport while the same
  arm loses one jaw. One-finger motion cannot establish transport, another arm
  cannot inherit it, and release still requires all fingers to leave.
- Placement diagnostics retain support candidates, signed normal and impulse
  checks, release phase and settling drift to distinguish contact, support and
  stability problems.
- Initial scene calibration exports actual annotations and resolved live
  landmarks. Exporting an annotation is not verification that it denotes an
  interior or mouth.

## Evidence locations

Operational suites and bulky evidence live below:

`/lustre/fsw/portfolios/cosmos/projects/cosmos_base_cap/users/mverghese/robodojo-atomic-runs/`

- `geometry-expansion-1006/`: first suite, manifest, controller and results.
- `geometry-validation-1006/`: new-runtime validation suite.
- `eval-matrix-1004/`: completed original screen; remains unchanged.
