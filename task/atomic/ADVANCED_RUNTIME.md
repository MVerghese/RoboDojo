# Selection, paths, choices and material state

Implemented October 2, 2026. **Offline verification only.** The queued eight-run
suite uses its immutable earlier runtime (`f8025e5`); it cannot validate these
later additions. Use a fresh suite to run this code after asset calibration.

## Before contact

A geometric condition can sample the state immediately before an actual contact:

```json
{
  "id": "approach", "slot": "hand approach", "kind": "relative_displacement",
  "measurement": {"kind": "functional_point", "label": "mallet", "tag": "beat", "type": "active"},
  "reference": {"kind": "functional_point", "label": "xylophone", "tag": "hit_0", "type": "passive"},
  "expected": [0, 0, 0.03], "axes": [2], "tolerance": 0.005,
  "event": {"kind": "before_contact", "measurement": {"kind": "object_contact_points", "label": "mallet", "other_label": "xylophone"}}
}
```

The preceding physics sample's **measurement and reference** are retained, even
if the target moves at impact. First contact without a contiguous prior sample
is `preceding_sample_missing`; a later attempt cannot replace it. Contact points
do not exist before contact, so use an actual hand/tool landmark for approach.
This example's 3 cm target requires live calibration.

## Trajectory conditions

Each stage may declare `trajectories`, separate from endpoint `geometry`:

```json
{
  "id": "sweep_path", "slot": "sweep segment",
  "measurement": {"kind": "functional_point", "label": "tool", "tag": "tip", "type": "active"},
  "reference": {"kind": "object_pose", "label": "target", "time": "stage_start"},
  "expected": [[0, 0, 0], [0.1, 0, 0], [0.1, 0.1, 0]],
  "axes": [0, 1], "tolerance": 0.005, "backtrack_tolerance_m": 0.005,
  "min_samples": 3, "start_event": {"kind": "stage_start"},
  "end_event": {"kind": "stage_success"}
}
```

These are template labels and waypoints; bind them to actual calibrated assets.
Available window events include native read-only predicates, contact and named
physical recognizer events. `stage_success` ends at physical action completion;
`before_contact` is a historical sample and cannot delimit a path window.

The observer samples every distinct synchronized physics step, retaining point,
reference, sources, action index and dt. Scores include maximum/RMS polyline
deviation, endpoint error, ordered waypoint witnesses, backtracking and duration.
Skipped corners, correct endpoints around a detour, stationary closed loops and
out-of-order segments fail. Sample gaps, insufficient samples, changing dt and
incomplete windows have **no pass score**. No motion between unsampled physics
states is certified. Waypoint witnesses are conservative: a corner crossed
between recorded samples may remain unverified. Calibrate sample density and
waypoint tolerances against feasible motion; self-intersections can be ambiguous.

Paths measure one real landmark, not a centroid of many tool contacts. Contact
locations remain individually scored by the existing geometric checker. Paths
and selection are preserved when changing a stage instruction with a variant.

## Initial referent selection

A stage can declare an explicit initial candidate set:

```json
"selection": {
  "candidates": ["block_1", "block_2"], "arm": "any",
  "min_finger_bodies": 2, "min_contact_steps": 2,
  "conditions": [{
    "id": "initial_location", "slot": "object", "kind": "point",
    "measurement": {"kind": "object_center_position", "label": "@candidate"},
    "expected": [0.2, 0.1, 0.05], "tolerance": 0.015
  }]
}
```

All candidates and reference frames are captured at stage activation. Conditions
use the existing five geometric types on explicit object roots/mesh centers;
whole-object relations require their usual surface semantics. The first sustained
physical contact determines the observed referent. A wrong object moved to the
right position later still fails the original selection condition.

Exactly one geometrically eligible candidate is required for a selection score.
Zero matches, multiple eligible targets or simultaneous qualifying contacts are
reported explicitly; they do not pass by choosing the nearest or first label.
Selection is independent of physical action recognition. This does not compile
language roles, enumerate all scene objects automatically or select arbitrary
control/tip/material landmarks. Candidate-set completeness remains a task binding.

## Choosing routes or subsets

An `AtomicProgram` may supply `choices`, in addition to gates and repeats:

```json
"choices": [{
  "id": "choose_two", "branches": [["pick_a", "finish_a"], ["pick_b", "finish_b"], ["pick_c", "finish_c"]],
  "required": 2
}],
"stage_dependencies": {
  "pick_a": [], "finish_a": ["pick_a"],
  "pick_b": [], "finish_b": ["pick_b"],
  "pick_c": [], "finish_c": ["pick_c"],
  "choose_two": ["finish_a", "finish_b", "finish_c"],
  "next_action": ["choose_two"]
}
```

Supply the concrete stage definitions separately. A branch terminal must depend
on every earlier action in its branch. Branches cannot share actions or depend
on another optional branch. External successors depend on the choice node.

The first required number of complete physical branches resolves the choice.
Remaining alternatives become `required=false`, `choice_status=not_selected`;
their attempted/completed evidence is retained. If excess branches complete in
the same sampled interval, report `ambiguous_completion` and leave the successor
blocked; no arbitrary subset is selected. Repeats expand within a branch and
rewrite its terminal dependency. This is an explicit reviewed runtime construct,
not an automatic compiler for all source plans. Native exact counts, slot
occupancy, unused objects and other full-task rules remain independent checks.
Selected-stage execution/prefix replay rejects choices until state restoration
is implemented.

## Strikes and retraction

`held_tool_strike` augments landmark contact with:

- Two separated pre-impact samples and target-relative velocity along the target
  landmark's normal; no commanded policy velocity or already-stopped impact pose.
- A currently held tool and actual landmark-scoped force-bearing impact.
- Continued same-arm holding, separation from the target and a minimum rise
  within an explicit number of physics steps.

Fields extend `held_tool_landmark_contact` with `min_approach_speed_m_s`,
`min_retraction_m`, `min_retraction_steps`, `max_retraction_steps`. Events are
`impact`, `retracted`, `strike`. The retained impact evidence includes both
approach samples, relative velocity, impulse and actual contact points.
`programs/play_Xylophone_strike.json` is a stricter prototype of the existing
contact-only program, with a proposed 0.05 m/s approach threshold and 25 mm
retraction. It needs fresh live calibration; thresholds are not success claims.
Retraction can be driven by the robot and does not prove natural rebound.
Musical tempo/timing constraints remain separate work.

## Cloth material landmarks

- `cloth_points`: explicit stable material vertex `ids`, measured individually.
- `cloth_landmark`: annotated `passive.functional[tag].id` vertices, measured
  individually; a centroid is diagnostic and cannot mask opposite vertex errors.
- `cloth_patch_frame`: `origin_id`, `x_id`, `y_id` define a live tangent frame.
  Coincident/collinear patches fail instead of inventing an orientation.

The garment adapter uses initialized **PhysX cloth world-position tensors**,
subtracts the environment origin once and preserves material indices. Cached
rigid meshes and CPU/USD fallback are rejected. GPU cloth tensor APIs and actual
annotated IDs still need live verification. These selectors provide geometry;
they do not prove a cloth grasp or recognize a fold. Particle/finger contact,
grip correspondence, crease/layer order and self-intersection remain missing.

## Liquid particles and transfer

`FluidObject` assigns explicit persistent PointInstancer IDs and exposes updated
particle coordinates only while physics/particle copies to USD are enabled.
The adapter applies the current complete USD local-to-world matrix, including
scale, then subtracts the environment origin. `fluid_points` selects explicit
persistent particle IDs and scores every point. Freshness of the USD copy still
needs live verification under the deployed simulator configuration.

`fluid_material_transfer` uses the source vessel, target vessel, distinct fluid
population, live source/target frames, **explicit interior box half-extents**,
required particle count, minimum tilt and settling samples. The native
`pour_liquid_into_cup` labels are `bottle`, `cup`, `wine`; interior volumes are not
yet calibrated, so no executable task program with guessed cavity bounds is
published.

Only particles initially in the source and outside the target are eligible.
A held/tilted source exit must be observed, followed by sustained target-only
containment. Preexisting target fluid, unheld exits and exits across a sampling
gap cannot count. Persistent IDs permit buffer row reordering; population or
nominal-mass changes fail explicitly. Occupancy partitions retain source-only,
target-only, both-interior and outside-both counts, without artifact filtering.
Mass is **configured nominal particle mass**, not measured density. Containment
uses particle centers, not whole fluid volumes. Outside-both includes flight and
cannot automatically be called spill. Stream/opening crossings, velocities,
flight/spill discrimination and liquid volume calibration remain open.

## Articulated surface geometry

Mesh templates are decomposed by their actual rigid child links and transformed
by one live PhysX link-pose snapshot. Whole-object centers/footprints follow all
child meshes; link-scoped geometry includes only the requested body. Meshes
without an explicit rigid body, sheared transforms and missing physics fail
instead of falling back to the object root. Deforming material cannot reuse a
rigid surface cache. Frozen object references retain actual historical vertices,
including the former child poses, rather than only a root pose.

Object-scoped relations can use `articulated_link_pose`/`joint_link_pose`.
Link-supported `on_top` uses the selected body's actual prim path to scope signed
force-bearing actor/collider contacts on either side. It retains raw support
contacts and scopes alongside live link meshes. A mechanism-base contact cannot
prove cap support, and an unscoped root contact cannot identify a specific link.
Historical supported-on is rejected because it lacks current support evidence.
Triangle extraction and actual asset link mappings need live validation.

## Evidence and reporting

`audit_scores.py` reproduces path aggregates and initial candidate scores from
raw saved state. Reports distinguish optional routes, selection ambiguity,
trajectory coverage, geometric error and native action/task success. Current
code has offline counterexamples, not universal live action or steering proof.
