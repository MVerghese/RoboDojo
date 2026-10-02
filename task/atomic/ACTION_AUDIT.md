# Audit of all atomic action families

This extends the [implemented geometry audit](INSTRUMENTATION_AUDIT.md) across all
**11 families** in the [taxonomy](TAXONOMY.md). The [task catalogue](TASK_MAP.md)
contains examples and source evidence for **every one of the 54 task modules**.
An action occurs only in the tasks that require it; not every task contains every
action. Examples below describe requirements, not observed successful rollouts.

## Current instrumentation boundary

The schema accepts all eleven family names. That does **not** install eleven
recognizers. The live four-task pilot exercised finger contacts for pick/push,
rigid mesh geometry, ball transfer predicates and annotated charger entry frames.
It did not reach charger insertion. Place, tool interactions, actuation, twisting,
handover, deformable folds and liquid mass measurements still need dedicated
recognition/measurement adapters and live validation. Generic native predicates
can be observed, but final task state does not prove the intervening action.

The five geometric types and the complete per-slot applicability matrices are
in [TAXONOMY.md](TAXONOMY.md). The audit adds the **physical meaning** of each
slot: selection is evaluated at stage start; interaction geometry at a declared
contact/entry/transfer event; goal geometry after completion and release where
required. A requested contact position has no orientation. To condition approach
orientation, use an actual tool/gripper frame as a separate slot, not an invented
orientation on a contact point.

## Family audit and concrete examples

| Family; example task | Slots and geometry to measure | Recognition and continuous metrics | Implementation status / required correction |
| --- | --- | --- | --- |
| **pick**; `general_pickup`, cup in `pour_balls_into_vase` | Object selection at start; force-bearing finger contacts in object frame; grasp/approach frame separately; lift displacement/pose. P/D/R for contact location, T/O only on an actual oriented frame. | Same-arm opposing finger-body evidence and object lift. Per-contact distance or selected-axis band error; worst point determines pass. Also report contact count, arm, lift and timing. | Implemented contact sampler and first-lift event. No EEF-origin fallback. The current recognizer checks contacts at that event, not grasp continuity over the whole lift. Two bodies do not by themselves prove force closure; add normals/load persistence if claiming secure grasp. |
| **place**; `stack_blocks`, `hang_mugs` | Held object, target support surface/interior, release pose and final object pose. P/T/D/O/R on oriented object/target frames; hanging uses handle/hook frames. | Previously held object released, stable at target for a declared interval; support/contact or valid enclosure. Pose error, signed height gap, footprint overlap, containment violation and drift. | Generic pose/mesh relations available, dedicated release/stability recognizer absent. Native `is_stacked`, root proximity or handle proximity cannot establish supported placement. Cavities and hooks need actual shell/contact geometry. |
| **push**; `push_T`, keyboard in `organize_table` | Object contact on the actual touched surface; object goal pose/path; maintained support. P/D/R contact, T/O on object/approach frames. | Finger/object contact concurrent with motion, object remains table supported; declared final goal predicate. Contact-region error, goal pose error, lift/support deviation and contact duration. | Contact at first motion implemented for T; goal pose implemented. Event-specific missing contact leaves interaction unverified even if final pose passes. Add contact intervals and palm selectors for a broader recognizer; never silently substitute them into existing results. |
| **push_with_tool**; `sweep_blocks`, `align_blocks` | Tool grasp, active head/edge pose, tool-target contact, swept objects and goal region. P/T/D/O/R apply to appropriate points/frames; sweep corridor is a path/region extension, not a single 3D point. | Robot holds tool; tool, not bare hand, contacts targets during motion; objects reach dustpan/row; stabilizing hand maintains its constraint. Contact error, tool normal/axis error, path deviation, final containment, missed/spilled objects. | Finger sampler cannot represent broom/cube or set-square/block contact. Add explicit collision-body pairs and active-edge landmarks. Native sweep containment and row alignment do not establish tool use or handover. |
| **pour**; `pour_balls_into_vase`, `pour_liquid_into_cup` | Source/target selection, source mouth pose, aim point and target opening; orientation of pour axis; above with footprint overlap. P/T/D/O/R on rigid source/target/mouth frames. | Material exits selected source and enters selected target; account for source residue and spills. Pose/axis error at first transfer and over transfer interval, transferred mass/count, spill fraction. | Whole-ball finite containment and first-target-entry sampling implemented; source-exit provenance is still a gap. Cup mesh centre is explicitly a centre slot, not a mouth landmark. Liquid native predicates filter scattered particles: record raw total mass and ignored mass before using them as benchmark metrics. |
| **actuate**; `press_by_number`, toaster lever, laptop lid | Mechanism/control identity, actual moving-link contact point, joint state, approach axis. Geometric types on point/frame slots; desired joint ratio/state is an action parameter, not SE(3). | Contact-coupled joint transition in correct direction; press/release hysteresis and sequence counts. Contact error, approach angle, joint displacement/state residual, duration and impulse. | Native joint transitions/endpoints exist; contact-to-articulated-child selector and independent actuation recognizer absent. Calibrate joint limits/sign (`press`, `toast_botton`, `GetParentLink`, `laptop_hinge`). A closed joint without robot contact is not a recognized actuation. |
| **twist**; `insert_key`, `fasten_screws` | Moving part, joint/thread axis, pivot, target rotation and grip/approach frame. P/D/R on pivot/contact; T/O on actual axis/part frames. | Rotation occurs while gripped and constrained to the pivot/axis; insertion depth maintained where required. Unwrapped signed rotation, axial tilt, pivot drift, depth change; threaded progress/torque if represented. | Generic quaternion error is an endpoint score, not twist recognition. Key native checks final orientation; screw native checks only depth/alignment. Add temporal relative rotation and constraint evidence. Quaternion shortest angle cannot distinguish a complete turn from zero turns. Verify which screw/nut member moves in the asset. |
| **insert**; `plug_in_charger`, `deposit_coin`, tubes/pegs | Object tip/hole frame, opening/peg frame, entry pose, insertion axis and bounded depth. P/T/D/O/R for actual annotated frames; scalar depth remains a parameter. | Tip crosses opening plane with lateral fit and correct axis, then reaches bounded depth; peg through hole for stacking toy. Entry position/orientation error, signed depth, lateral error and clearance violations. | Charger-specific annotated entry/depth predicates implemented, but insertion was not reached in pilot. No generic tip/opening adapter for every task. Coin bank root is not its slot; deposit program deliberately has no misleading insertion geometry. Whole final containment cannot prove entry path or fit. |
| **touch_with_tool**; `play_Xylophone` | Held tool, active beat/tip landmark, target key/contact point, approach frame. P/D/R for impact location; T/O for actual tool/target frames. | Tool-target contact/impulse with correct key identity and sequence; rebound/lift for separate strikes. Impact-location error, normal/approach angle, impulse and timing/order. | Native beat point in key bbox/height band is not physical impact. Add mallet/key contact-body selector, velocity/impulse and debounce. Tool grasp and impact contacts are different pairs; finger-contact scorer alone is insufficient. |
| **handover**; `insert_key`, `sweep_blocks` | Object, giver/receiver arms, each grasp region/frame, transfer pose. All five types on object/arm frames, P/D/R on contact regions. | Giver holds, receiver establishes contact/hold, giver releases, receiver continues supporting; object never drops. Transfer pose error, each contact-region error, overlap duration and unsupported displacement. | Arm-resolved finger data can support an adapter, but current pick chooses one arm and does not recognize the transfer sequence. Native instructions request handover; rewards do not verify it. Simultaneous proximity of hands is insufficient. Dustbin handover is optional. |
| **fold**; `fold_clothes` and `_random` | Material corner/edge grasp points, fold line (two material landmarks), moving/fixed garment regions, final landmark/layer relations. P/D/R on deforming material points; T/O only on defined local tangent frames. A line needs two points plus direction, not one point/pose. | Material patch is grasped and moved across a defined crease; intended layer overlap/order and stable release. Landmark distance, crease line error, material-region overlap, layer order and self-penetration. | Native sleeve/chest/hem/shoulder material-point ranges and line angle provide useful phases. Atomic selectors currently address rigid objects, not current deformable material topology. Add a garment adapter using live vertices/material IDs and contact correspondence. Mesh-bound centres cannot measure a fold. |

## Audit rules shared by every family

1. **Declare semantics before scoring.** Record units, scalar-first quaternion
   order, coordinate frame, root versus mesh centre versus functional landmark,
   affected axes, symmetry, event and timing tolerance. An initial selection
   constraint must not be scored on a moved object's final pose.
2. **Use synchronized physical evidence.** Read pose and contacts from the same
   actual physics substep, transform by the current physical body frame, and
   resolve contact bodies to the intended object/link. Preserve points, normals,
   impulses, identities and backend health. Contact-processing failure is an
   infrastructure failure, not poor policy adherence.
3. **Treat relations as geometry with declared scope.** Above/below for objects
   requires signed relative height **and footprint overlap projected along the
   reference z axis**. Supported-on additionally requires load-bearing contact.
   Holes remain holes; finite containment uses complete geometry. A centre-point
   inside an open/nonconvex container is not object containment. Object-surface
   `near` is currently unsupported; point-to-point distance has different semantics.
4. **Keep orientation meaningful.** Normalize quaternions and account for sign
   equivalence. Use axis alignment for justified rotational symmetry, full frame
   error otherwise; do not invent a contact orientation. Articulated links and
   deformable tangent frames need live adapters, not initial USD root transforms.
5. **Recognize the action independently of requested geometry.** Targets must not
   alter success checks inside an A/B pair. Missed events, unavailable contact
   and unreached stages remain unobserved; closest approach is diagnostic only.
   Score contact points individually rather than letting a centroid mask errors.
6. **Preserve dependencies.** Retain native task success, order/game rules,
   conveyor timing, other-arm stabilization, source material identity and cleanup.
   Save stage-local baselines when measuring motion; episode-start displacement
   can be already true when a later stage starts.
7. **Calibrate feasibility and restart fidelity.** Inspect per-layout asset
   geometry and landmarks; never declare candidate targets reachable solely
   because the schema loads. Prefix replay reproduces actions, not a simulator
   snapshot. Compare rigid poses/joints, velocities, material state and contact
   conditions before trusting later-stage A/B comparisons.

## What was fixed, and what is not yet implemented

Existing instrumentation fixes are documented in
[INSTRUMENTATION_AUDIT.md](INSTRUMENTATION_AUDIT.md): actual finger contacts,
per-substep synchronization, enabled/checked PhysX reports, worst-point contact
scoring, explicit mesh centres, height plus footprint relations, support contact,
finite convex containment, annotated charger frames and physically correct T
goal height. The legacy cup variants and variation generator now describe their
actual contact/object measurements and axes rather than an EEF proxy.

This wider audit establishes requirements and source evidence for every family;
it does not claim that the missing adapters above have been implemented. The
next implementation examples are button actuation (`press_by_number`), tool
impact (`play_Xylophone`), tool pushing/handover (`sweep_blocks`), constrained
twisting (`insert_key`), supported placement (`stack_blocks`) and material folding
(`fold_clothes`). Each needs one live contact/state trace before claiming coverage.

**Taxonomy gap:** `put_bottles_into_dustbin` explicitly says to throw. Release
velocity and contact-free ballistic flight are not covered by place. Throw is
flagged in the catalogue, not silently relabeled or added to the current schema.
