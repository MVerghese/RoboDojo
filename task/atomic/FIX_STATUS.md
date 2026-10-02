# Audit fixes and remaining implementation

Updated 2026-10-02. This page distinguishes implemented fixes from source plans
and missing adapters. See [instrumentation evidence](INSTRUMENTATION_AUDIT.md),
[slot/factor coverage](CONDITIONING_AUDIT.md), and [all-task plans](SEGMENTATION.md).

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

Verification: **86 offline atomic tests pass**, including 22 new temporal/runtime
counterexamples; the updated audit skill validates. No new live results are
claimed. Earlier table entries describe their original implementation boundary;
held-tool, placement and handover additions supersede the missing-recognizer
parts of those entries.

## Remaining implementation/calibration

- Initial referent selection and ambiguity checks against a start-state candidate
  snapshot; fixed labels alone do not score which object the robot selected.
- Task-specific binding/calibration/live verification of generic rigid adapters:
  openings/tips, actual tool/control parts, pivots, constraints and thresholds.
- Tool strike approach velocity, rebound and musical timing; swept path scoring.
- Live articulated child-link geometry selectors; thread engagement/progress
  and feasibility of the screw assets.
- Liquid particle transfer, raw residue/spill mass and material conservation.
- Cloth material IDs/vertices, particle/finger contact, grasp correspondence,
  crease and layer order.
- Automatic source-plan compilation with layout-dependent choices, repeats,
  memory/game/conveyor scene-event gates and constraint bindings.
- Faithful full-state restoration and partial-action replay for graph or
  mid-chunk starts. Whole-action prefix replay remains limited to linear starts.
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
