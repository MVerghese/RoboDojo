# Physical recognizers and dependency runtime

Implemented 2026-10-02. The additions have offline counterexample tests;
**fresh Isaac Sim validation is still required**. The October 1 pilot used older
recognizers and remains historical evidence only.

## What runs now

`AtomicSequence` observes every enabled stage on every synchronized physics
substep. A program can supply `stage_dependencies`, mapping every stage ID to
its prerequisite IDs. All prerequisites must complete; independent branches
remain enabled together. Without that field the existing linear ordering is
preserved. Cycles, unknown parents, duplicate parents and incomplete maps fail
at load time. Finite repetitions can be unrolled into distinct stage IDs.
Successors start after all previously enabled nodes are sampled, so one physics
sample cannot complete successive stages by reusing the same motion.

The runtime is an observer; it does not schedule the policy or move either arm.
It handles the actions declared in the program, not arbitrary undeclared actions.
Automatic role/choice resolution, scene-event gates, repeat expansion and general
compilation of the 54 prose source plans remain to implement.

Each stage's `recognition` is independent of its geometric conditions and is
preserved across variants. A geometric target cannot relax a contact, motion,
provenance or support requirement. Native endpoint checks remain separate.

| Family | Recognition kind | Physical evidence |
| --- | --- | --- |
| pick | `finger_contact_motion` | Existing two-finger same-arm held interval; full native lift within current hold |
| push | `finger_contact_motion` | Existing one-finger contact-held planar interval and upward named support |
| place | `supported_release` | Sustained same-arm grasp, transport, absence of **all** finger contacts, upward support and bounded translation/rotation over consecutive settling steps |
| push_with_tool | `held_tool_push` | Two-finger tool hold, simultaneous tool/target contact, target support, new tool and target planar motion, bounded target vertical motion |
| touch_with_tool | `held_tool_contact` | Sustained tool hold, separation followed by a new force-bearing encounter, explicit tool and target body/collider suffixes, minimum impulse |
| handover | `grip_transfer` | Giver-only hold, sustained dual-arm overlap, actual giver release, continued receiver-only hold, bounded per-step object translation |
| insert | `held_insertion` | Held tip approaches from outside a live opening, aligned lateral/axis path, inward signed depth, receptacle contact; an already inserted object cannot count |
| actuate | `contact_joint_motion` | Contact on the joint's actual USD body1 moving rigid body and directed live DOF travel during the same-arm contact interval |
| twist | `contact_constrained_twist` | Held part/receptacle contact, calibrated pivot depth/radius, signed rotation accumulated over substeps in the live target frame, bounded off-axis rotation |
| pour | `rigid_material_transfer` | Initially selected source contents, held/tilted source at observed exit, whole rigid-object entry into calibrated target interior, consecutive containment, raw residue/target/outside counts |
| fold | unavailable | Requires live cloth patch IDs, particle/finger contacts, grasp correspondence, crease and layer tracking |

These are evidence-based heuristics, not proofs of force closure, thread
engagement or causality. Tool touch is a debounced contact recognizer; strike
velocity, rebound and musical timing remain separate adapters. Insertion uses a
calibrated frame and tolerances; it does not prove arbitrary peg/hole clearance.
Twist uses a configured part root and pivot; verify the root represents the
intended constrained axis before using it. Joint travel uses simulator-native
units (metres for prismatic DOFs, radians for revolute DOFs).

Rigid pouring requires **explicit calibrated interior convex boxes**, not vessel
outer bounding boxes. Source and target half-extents are expressed in their
named live frames. Whole material meshes must fit. `outside_both` includes
material in flight and is not automatically labeled a spill. This adapter does
not read liquid particles or report fluid mass. It is not yet bound to the
historical ball-pouring program, whose cavity calibration remains to verify.

## Physical transitions and continuous constraints

A condition can use an actual physical transition:

```json
"event": {"kind": "recognition_event", "name": "release"}
```

It then captures geometry at first release, before the later settled pose.
The event must be emitted by that stage's recognizer. Available transitions:

- Place: `release`, `settled`.
- Tool push: `stroke`; tool touch: `contact`.
- Handover: `giver_hold`, `overlap`, `receiver_only`.
- Insertion: `entry`, `inserted`.
- Actuation: `motion`; twist: `rotation`.
- Rigid pour: `source_exit`, `first_transfer`, `transfer_complete`.

Raw first-event evidence is in `physical_events`. Current count diagnostics are
in `physical_metrics`. Event geometry is retained independently of later action
success. Missed contacts and incomplete stages remain unobserved.

A stage can declare continuously required other-arm holds:

```json
"maintained_holds": [
  {"label": "holder", "arm": "left_arm", "min_finger_bodies": 2}
]
```

Every observed substep must satisfy these contacts. Contact loss or a sampling
gap permanently fails that stage's maintained constraint, recorded in
`maintained_hold_failures`. This is deliberately stricter than checking the
other arm only at the final endpoint.

Stateful native predicates that consume transition history are rejected in
observers. Use the private recognizer state machine and read-only endpoint
predicates instead; annotation must not consume events from native rewards.

## Programs and calibration

Eight programs now load. Three additions:

- `align_blocks`: tool pick, then independently enabled tool pushes for each of
  the three blocks. A single stroke may complete several branches. These stages
  recognize contact-coupled pushing; native row alignment/no-lift/arm-return
  remain the full-task outcome. The pick uses a proposed 2.5 cm lift threshold.
- `stack_blocks_by_language`: pick/place the middle and top blocks onto their
  required supports. The two picks are independent; placing the top waits for
  middle placement. Leaving the base in place is a proposed valid route.
  Settling requires 24 consecutive samples; duration depends on simulator dt.
- `push_T_random`: the existing physical T-push program with matching random-task
  identity and the same source-verified labels/native endpoint thresholds.

New thresholds are prototype recognition parameters. Contact dropout, dt,
asset geometry, reachability and event timing need live calibration. These
programs do not claim successful policy episodes or full-task restart coverage.
The original coin/charger insertion and ball pour retain endpoint-only stages
until their new recognizers are explicitly calibrated and bound.

The exact required fields for each recognizer are in `recognizers.SCHEMAS`;
unknown or omitted fields fail. See the new programs for supported placement
and held-tool push examples. Contact suffixes are paths relative to the selected
physical object's prim root and must identify the actual active part.

## Boundaries and starting stages

`stage_boundaries` saves action index, physics step and whether activation
occurred at a whole-action boundary. `stage_starts` contains **only** starts that
can be represented by whole-action prefix replay. Mid-chunk starts are marked
`prefix_replay_supported=false` and are omitted from `stage_starts`.

A program root (no prerequisites) may be selected from a fresh episode. Prefix
replay currently accepts only linear programs with available whole-action
boundaries. Graph starts and mid-chunk starts require faithful state restoration
or verified partial-action replay. Neither is implemented; no boundary is
silently rounded to the end of an action chunk.

## Verification

```bash
python -m unittest discover -s tests -p 'test_atomic*.py'
python scripts/atomic/segmentation_plans.py --check
python scripts/atomic/conditioning_audit.py --check
```

Counterexamples cover already-resting placement, one-finger contact at release,
unheld tools, wrong struck parts, delayed touches, simultaneous initial holds,
already-inserted objects, wrong-link actuation, full-turn quaternion aliasing,
preexisting target contents, source exit before grasp, protruding material,
dropped other-arm holds, skipped/duplicate callbacks, backend failures, DAG
cycles and several stages completing in one policy chunk.
