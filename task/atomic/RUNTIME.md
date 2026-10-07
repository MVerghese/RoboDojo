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
Bounded numeric asset repeats and explicit read-only scene gates now bind at
layout setup. Explicit route/subset choices, initial object candidate snapshots, trajectory
windows and material geometry are also available; see [ADVANCED_RUNTIME.md](ADVANCED_RUNTIME.md).
Automatic role resolution, task-specific game/conveyor gates and compilation
of the 54 prose source plans remain to implement.

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
| actuate | `button_press_cycle` | Annotated moving joint, force-bearing finger contact while crossing from above 0.95 to below 0.5, all-finger release and spring return above 0.9; a held-down button cannot complete another cycle |
| touch_with_tool | `held_tool_landmark_contact` | New force-bearing encounter while tool is held; actual contact points must lie near both annotated active tip and target landmarks, with impulse and per-key bbox identity |
| actuate | `contact_joint_motion` | Contact on the joint's actual USD body1 moving rigid body and directed live DOF travel during the same-arm contact interval |
| twist | `contact_constrained_twist` | Held part/receptacle contact, calibrated pivot depth/radius, signed rotation accumulated over substeps in the live target frame, bounded off-axis rotation |
| pour | `rigid_material_transfer` | Initially selected source contents, held/tilted source at observed exit, whole rigid-object entry into calibrated target interior, consecutive containment, raw residue/target/outside counts |
| fold | unavailable | Requires live cloth patch IDs, particle/finger contacts, grasp correspondence, crease and layer tracking |

These are evidence-based heuristics, not proofs of force closure, thread
engagement or causality. Tool touch is a debounced contact recognizer; `held_tool_strike` additionally
measures pre-impact target-relative speed, impact and held separation/retraction.
Natural rebound and musical timing constraints remain separate work. Insertion uses a
calibrated frame and tolerances; it does not prove arbitrary peg/hole clearance.
Twist uses a configured part root and pivot; verify the root represents the
intended constrained axis before using it. Joint travel uses simulator-native
units (metres for prismatic DOFs, radians for revolute DOFs).

Rigid pouring requires **explicit calibrated interior convex boxes**, not vessel
outer bounding boxes. Source and target half-extents are expressed in their
named live frames. Whole material meshes must fit. `outside_both` includes
material in flight and is not automatically labeled a spill. This adapter is distinct from the new `fluid_material_transfer` adapter, which reads persistent
particle IDs and reports raw counts/nominal mass in calibrated interiors. It is not yet bound to the
historical ball-pouring program, whose cavity calibration remains to verify.

## Physical transitions and continuous constraints

October 6: `attempt_end` is an explicit episode-end state sampling event. It is
independent of action success and is not a physical recognizer transition.
The evaluator finalizes started and earlier-completed sessions before reset;
unstarted stages retain missing scores. Completed action boundaries remain
unchanged. Initial live calibration evidence appears in `scene_calibration`.

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
- Actuation: `motion`; button cycle: `press`, `release`, `cycle`; twist: `rotation`.
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

Eleven program files now load for ten tasks, including a stricter xylophone alternative. Five original additions:

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

- `press_by_number`: red0 cycles, blue confirmation, red1 cycles, blue
  confirmation. Repeated red stages bind counts from actual number-card
  `model_id` metadata (1–9); expanded IDs and binding evidence are recorded.
  Geometry scores moving-cap finger contact relative to its annotated press frame.
- `play_Xylophone`: mallet pick and eight ordered contact strokes, separated by
  seven private 2.5 cm rise gates. Contact neighborhoods are prototype 4 cm
  radii; key identity also requires the native per-key functional bbox. Native
  reward's height-only checkpoint remains an independent outcome. No strike
  velocity, natural rebound or musical timing claim is made.

New thresholds are prototype recognition parameters. Contact dropout, dt,
asset geometry, reachability and event timing need live calibration. These
programs do not claim successful policy episodes or full-task restart coverage.
The original coin/charger insertion and ball pour retain endpoint-only stages
until their new recognizers are explicitly calibrated and bound.

The exact required fields for each recognizer are in `recognizers.SCHEMAS`;
unknown or omitted fields fail. See the new programs for supported placement
and held-tool push examples. Contact suffixes are paths relative to the selected
physical object's prim root and must identify the actual active part.

## Layout bindings and live articulated frames

`repeat_counts` maps a stage template ID to `{"label":"num0","min":1,"max":9}`.
The loaded asset's numeric `model_id` determines repetition; label suffixes do
not. Instances receive unique IDs and form a serial chain; dependencies on
the template target its last instance. Invalid metadata or ID collisions fail.

`gates` contains `{"id":"ready","checks":[...]}` definitions, with every gate
in `stage_dependencies`. Gates are physical scene observations, reported
separately from robot action stages. Checks must be read-only. The private
`is_atomic_rise_since_activation` check uses its own activation pose and does
not consume/reset native reward baselines. Game/opponent/memory predicates
require further task-specific binding.

`articulated_link_pose` selects an explicit link; `joint_link_pose` resolves
a joint's moving body from an annotated `joint_tag`. Functional/support
landmarks with `base_link` use initialized PhysX articulation link transforms,
converted xyzw→wxyz and translated into the environment-local frame. They
never fall back to stale USD/Fabric xforms. `contact_points.joint_tag` filters
to the actual moving joint body. Moving-link mesh templates now follow live PhysX
child poses, including frozen historical footprints. Link-supported-on scopes
signed force-bearing support contacts to the selected bodies and retains their
raw evidence. Asset mesh/link mappings still need simulator validation.

## Boundaries and starting stages

`stage_boundaries` saves action index, physics step and whether activation
occurred at a whole-action boundary. `stage_starts` contains **only** starts that
can be represented by whole-action prefix replay. Mid-chunk starts are marked
`prefix_replay_supported=false` and are omitted from `stage_starts`.

A concrete program root (no prerequisites) may be selected from a fresh episode,
regardless of its list position. A supplied trace with that root at action zero
also starts in the initial scene and preserves native parser/robot-origin
baselines. The submission helper and evaluator share the same boundary validator.
Per-episode `atomic_start` retains mode, selected stage, action index and the
explicit absence of state restoration.

Nonzero prefix replay currently accepts only linear programs with available
whole-action boundaries. `PrefixReplayObserver` keeps preceding sessions alive
through every physics substep, including their physical recognizers and maintained
holds. It initializes successors at recorded action boundaries and checks the
same physical success gates there; a fresh endpoint session cannot substitute
for that history. Prefix geometry targets are not success gates and are not
scored. `atomic_start.prefix_stage_validation` retains each preceding action's
physical/native evidence. Divergence clears the replay observer and aborts before
baseline resets or selected-stage policy inference.

Later graph starts and mid-chunk starts require faithful state restoration
or verified partial-action replay. Templates with repeats or gates must first be concretely resolved for selected-stage execution. Neither restoration nor partial replay is implemented; no boundary is
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
