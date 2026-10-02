# Conditioning coverage: every action slot and factor

Reviewed **11 action families, 54 family-specific slots and 5 geometric factors**, i.e. **270 individual slot/factor cells** (including inapplicable cells). The [machine-readable audit](conditioning_audit.json) stores the concept, status and reasoning for each cell. Source fingerprints and exact slot coverage make omissions or stale artifacts detectable.

This is a complete **source/semantics coverage audit**, not a claim that every combination has a working adapter or live experiment. See [family recognition audit](ACTION_AUDIT.md), [all task examples](TASK_MAP.md) and [taxonomy matrices](TAXONOMY.md).

## Status meanings

| Code | Meaning | Cells |
| --- | --- | --- |
| **L** | Specific pilot measurement observed and independently reproduced; not universal live validation. | 5 |
| **C** | Finger contact location checker available; cell-specific live evidence absent. | 4 |
| **G** | Generic rigid point/frame/relation math and selectors available; calibrated assets/events and family wiring still needed. | 45 |
| **F** | Contact point has no orientation: use a separate physical frame and independent contact evidence. | 4 |
| **S** | Initial referent-selection snapshot/resolution adapter missing. | 75 |
| **M** | Required measurement, event, trajectory, initial frame or relation adapter missing. | 109 |
| **NA** | Modifier does not apply to this categorical/intrinsic slot. | 28 |

**L/C/G refer to geometric measurement capability, not completed action recognition.** A native predicate can be true without the interaction. L applies only to the exact contact/event/asset described in its JSON evidence; the five L cells are not five universally validated slots.

## Exhaustive slot × factor matrix

P = 3D point; T = SE(3) pose; D = landmark-relative displacement; O = landmark-relative orientation; R = spatial relation.

| Family | Slot | P | T | D | O | R | Required semantics / limitation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `pick` | `[object]` | S | S | S | S | S | Initial referent selection; needs a stage-start snapshot, candidate resolution and ambiguity checks. Fixed labels and later poses do not score selection. |
| `pick` | `[grasp region]` | C | F | L | F | C | Actual same-step finger/object manifold points. P/D/R can score contact location. T/O require a separate physical frame plus contact evidence, not an orientation on a point. Cup and charger grasp-band scores observed; scissors lift event unobserved. Applies to these finger contacts, not every pick/asset. |
| `pick` | `[lift goal]` | G | G | M | G | G | Rigid point/frame geometry available. Bind to a calibrated landmark and explicit completion predicate; family recognition and live validation are separate. Needs a frozen initial-object reference selector. Current object reference poses move with the object; self-relative displacement cannot measure lift. |
| `place` | `[object]` | S | S | S | S | S | Initial referent selection; needs a stage-start snapshot, candidate resolution and ambiguity checks. Fixed labels and later poses do not score selection. |
| `place` | `[target]` | G | G | G | G | G | Rigid point/frame geometry available. Bind to a calibrated landmark and explicit completion predicate; family recognition and live validation are separate. |
| `place` | `[object goal]` | G | G | G | G | G | Rigid point/frame geometry available. Bind to a calibrated landmark and explicit completion predicate; family recognition and live validation are separate. |
| `place` | `[release point]` | M | M | M | M | M | Needs object-specific held-to-released transition, support and a stability interval. Generic open-gripper state is insufficient. |
| `push` | `[object]` | S | S | S | S | S | Initial referent selection; needs a stage-start snapshot, candidate resolution and ambiguity checks. Fixed labels and later poses do not score selection. |
| `push` | `[contact]` | C | F | L | F | C | Actual same-step finger/object manifold points. P/D/R can score contact location. T/O require a separate physical frame plus contact evidence, not an orientation on a point. Baseline T first-motion finger-contact score observed; conditioned run lacked finger evidence at that event. |
| `push` | `[hand approach]` | M | M | M | M | M | Needs an independent pre-contact/approach event and calibrated hand/tool frame; endpoint proximity alone does not establish an approach. |
| `push` | `[goal]` | G | L | G | G | G | Rigid point/frame geometry available. Bind to a calibrated landmark and explicit completion predicate; family recognition and live validation are separate. Conditioned T goal pose scored; push interaction remained unverified. Goal geometry is not action recognition. Rigid point/frame geometry available. Bind to a calibrated landmark and explicit completion predicate; family recognition and live validation are separate. Current landmark references work; episode/stage-start object offsets require a frozen reference adapter. |
| `push_with_tool` | `[tool]` | S | S | S | S | S | Initial referent selection; needs a stage-start snapshot, candidate resolution and ambiguity checks. Fixed labels and later poses do not score selection. |
| `push_with_tool` | `[object(s)]` | S | S | S | S | S | Initial referent selection; needs a stage-start snapshot, candidate resolution and ambiguity checks. Fixed labels and later poses do not score selection. |
| `push_with_tool` | `[tool tip]` | M | M | M | M | M | Needs actual tool-target collision pairs and active tip/edge landmarks; existing finger/object contacts do not observe tool contact. |
| `push_with_tool` | `[start contact]` | M | M | M | M | M | Needs actual tool-target collision pairs and active tip/edge landmarks; existing finger/object contacts do not observe tool contact. |
| `push_with_tool` | `[sweep segment]` | M | M | M | M | M | Needs continuous segment/path samples, phase events and deviation aggregation. Two endpoint values do not prove the intervening sweep. |
| `push_with_tool` | `[goal]` | G | G | G | G | G | Rigid point/frame geometry available. Bind to a calibrated landmark and explicit completion predicate; family recognition and live validation are separate. |
| `pour` | `[contents]` | NA | NA | NA | NA | NA | Categorical/material identity; geometry belongs on another named slot. Amount, flow, joint travel and twist angle are separate intrinsic parameters. |
| `pour` | `[source]` | S | S | S | S | S | Initial referent selection; needs a stage-start snapshot, candidate resolution and ambiguity checks. Fixed labels and later poses do not score selection. |
| `pour` | `[destination]` | S | S | S | S | S | Initial referent selection; needs a stage-start snapshot, candidate resolution and ambiguity checks. Fixed labels and later poses do not score selection. |
| `pour` | `[spout]` | G | G | G | G | G | Rigid functional-frame math available only after verifying a real mouth/spout tag and transfer event. A vessel centre is not a spout; no live spout evidence. |
| `pour` | `[opening]` | M | M | M | M | M | Needs material exit/impact tracking, destination opening geometry and finite containment. No rigid contents pose or generic stream direction selector. |
| `pour` | `[tilt]` | NA | G | NA | G | G | Use source vessel orientation for T/O and a verified spout point for R. Generic rigid math exists; no spout or stream measurement was observed live. |
| `pour` | `[source pour pose]` | G | G | G | L | L | Rigid point/frame geometry available. Bind to a calibrated landmark and explicit completion predicate; family recognition and live validation are separate. Cup local-z direction relative to vase observed at first whole-ball entry in conditioned run. Cup/vase height and projected footprint overlap observed at first whole-ball entry in conditioned run. |
| `actuate` | `[mechanism]` | S | S | S | S | S | Initial referent selection; needs a stage-start snapshot, candidate resolution and ambiguity checks. Fixed labels and later poses do not score selection. |
| `actuate` | `[control]` | S | S | S | S | S | Initial referent selection; needs a stage-start snapshot, candidate resolution and ambiguity checks. Fixed labels and later poses do not score selection. |
| `actuate` | `[contact]` | M | M | M | M | M | Needs live articulated child-link/joint/control selectors and contact-coupled joint events; cached root-anchored meshes cannot represent changing articulation. |
| `actuate` | `[approach]` | M | M | M | M | M | Needs live articulated child-link/joint/control selectors and contact-coupled joint events; cached root-anchored meshes cannot represent changing articulation. |
| `actuate` | `[state]` | M | M | M | M | M | Needs live articulated child-link/joint/control selectors and contact-coupled joint events; cached root-anchored meshes cannot represent changing articulation. |
| `twist` | `[part]` | S | S | S | S | S | Initial referent selection; needs a stage-start snapshot, candidate resolution and ambiguity checks. Fixed labels and later poses do not score selection. |
| `twist` | `[axis/pivot]` | M | M | M | M | NA | Needs live pivot/axis, unwrapped rotation and constrained grip/depth over time. Final orientation cannot recognize a twist. |
| `twist` | `[contact]` | M | M | M | M | M | Needs live pivot/axis, unwrapped rotation and constrained grip/depth over time. Final orientation cannot recognize a twist. |
| `twist` | `[orientation]` | NA | M | NA | M | NA | Needs live pivot/axis, unwrapped rotation and constrained grip/depth over time. Final orientation cannot recognize a twist. |
| `insert` | `[object]` | S | S | S | S | S | Initial referent selection; needs a stage-start snapshot, candidate resolution and ambiguity checks. Fixed labels and later poses do not score selection. |
| `insert` | `[receptacle]` | S | S | S | S | S | Initial referent selection; needs a stage-start snapshot, candidate resolution and ambiguity checks. Fixed labels and later poses do not score selection. |
| `insert` | `[opening]` | G | G | G | G | M | Annotated tip/opening frame math and charger-specific entry predicates exist. Other assets need verified frames/clearance/crossing adapters; charger entry was not reached in the pilot. Through/centred/seated/flush are not generic relation names. Define opening crossing/fit/depth; finite convex inside_box only covers its explicit box semantics. |
| `insert` | `[alignment]` | NA | G | G | G | M | Annotated tip/opening frame math and charger-specific entry predicates exist. Other assets need verified frames/clearance/crossing adapters; charger entry was not reached in the pilot. Through/centred/seated/flush are not generic relation names. Define opening crossing/fit/depth; finite convex inside_box only covers its explicit box semantics. |
| `insert` | `[goal]` | G | G | G | G | M | Annotated tip/opening frame math and charger-specific entry predicates exist. Other assets need verified frames/clearance/crossing adapters; charger entry was not reached in the pilot. Through/centred/seated/flush are not generic relation names. Define opening crossing/fit/depth; finite convex inside_box only covers its explicit box semantics. |
| `touch_with_tool` | `[target]` | S | S | S | S | S | Initial referent selection; needs a stage-start snapshot, candidate resolution and ambiguity checks. Fixed labels and later poses do not score selection. |
| `touch_with_tool` | `[contact]` | M | M | M | M | M | Needs actual tool-target collision pairs and active tip/edge landmarks; existing finger/object contacts do not observe tool contact. |
| `touch_with_tool` | `[tool]` | S | S | S | S | S | Initial referent selection; needs a stage-start snapshot, candidate resolution and ambiguity checks. Fixed labels and later poses do not score selection. |
| `touch_with_tool` | `[tool tip]` | M | M | M | M | M | Needs actual tool-target collision pairs and active tip/edge landmarks; existing finger/object contacts do not observe tool contact. |
| `touch_with_tool` | `[approach]` | M | M | M | M | M | Needs an independent pre-contact/approach event and calibrated hand/tool frame; endpoint proximity alone does not establish an approach. |
| `handover` | `[object]` | S | S | S | S | S | Initial referent selection; needs a stage-start snapshot, candidate resolution and ambiguity checks. Fixed labels and later poses do not score selection. |
| `handover` | `[giver]` | NA | NA | NA | NA | NA | Categorical/material identity; geometry belongs on another named slot. Amount, flow, joint travel and twist angle are separate intrinsic parameters. |
| `handover` | `[receiver]` | NA | NA | NA | NA | NA | Categorical/material identity; geometry belongs on another named slot. Amount, flow, joint travel and twist angle are separate intrinsic parameters. |
| `handover` | `[exchange]` | M | M | M | M | M | Needs giver hold, receiver hold, giver release and continued receiver support events. One-arm contact resolution is not a transfer recognizer. |
| `handover` | `[object orientation]` | NA | M | NA | M | NA | Needs giver hold, receiver hold, giver release and continued receiver support events. One-arm contact resolution is not a transfer recognizer. |
| `fold` | `[deformable]` | M | M | M | M | M | Needs current material vertices/IDs, patch/tangent frames and fold/contact events. Rigid USD meshes cached at setup are not deforming garment geometry. |
| `fold` | `[crease]` | M | M | M | M | M | Needs current material vertices/IDs, patch/tangent frames and fold/contact events. Rigid USD meshes cached at setup are not deforming garment geometry. |
| `fold` | `[moving region]` | M | M | M | M | M | Needs current material vertices/IDs, patch/tangent frames and fold/contact events. Rigid USD meshes cached at setup are not deforming garment geometry. |
| `fold` | `[target region]` | M | M | M | M | M | Needs current material vertices/IDs, patch/tangent frames and fold/contact events. Rigid USD meshes cached at setup are not deforming garment geometry. |
| `fold` | `[grasp point]` | M | M | M | M | M | Needs current material vertices/IDs, patch/tangent frames and fold/contact events. Rigid USD meshes cached at setup are not deforming garment geometry. |
| `fold` | `[final orientation]` | NA | M | NA | M | NA | Needs current material vertices/IDs, patch/tangent frames and fold/contact events. Rigid USD meshes cached at setup are not deforming garment geometry. |

## Factor-level checker audit

Every cell above has a defined status. All five factor **math kernels** have local
known-geometry tests. This does not mean all 242 applicable cells have working
recognition adapters or live policy trials.

| Factor | Required definition and score | Code and local evidence | Live evidence / remaining limits |
| --- | --- | --- | --- |
| **P: 3D point** | Explicit environment/landmark frame, physical point identity, selected axes and metre tolerance. Euclidean error only on requested axes. | `geometry.evaluate_geometry` point branch; rotated-frame P/D tests and preflight numeric/axis checks. Root-versus-mesh-centre selector is explicit. | No standalone P condition observed in the eight-run pilot. Initial object selection, material points, physical tool impact and release timing still need adapters. |
| **T: SE(3) pose** | Real oriented frame, finite position/nonzero quaternion, translation and rotation tolerances separately. Full pose constrains all position/orientation components; use P/D/O for partial requests. | Pose branch reports `position_m` and `orientation_rad`; sign/scaling invariance and T-pad height regression. Point-only selectors and unused position-axis masks are rejected at load. | T-block goal pose observed. Charger entry T was not reached. A contact point does not define a pose. Changing joint/deformable frames are not represented by cached root meshes. |
| **D: relative displacement** | Explicit named reference frame, vector direction, chosen axes and metre tolerance. Every actual contact scored; worst contact decides pass. | Displacement branch and rotated-frame/contact-cancellation tests; schema requires an oriented reference. Object-scope attachment preserves the selected root/centre instead of replacing it. | Cup/charger and baseline T contact bands observed. A current object reference is not its initial pose: lift/motion offsets from initial state need a frozen frame adapter. |
| **O: relative orientation** | Explicit orientation landmark, normalized wxyz quaternion, sign equivalence, full-frame or declared symmetric-axis error. Angular tolerance in radians. | Orientation branch; sign/symmetric-axis/extreme-scale tests. Empty/duplicate/boolean axis lists and point-only frames fail preflight. | Cup local-z direction observed at first whole-ball transfer. Final orientation cannot measure unwrapped twist angle, handover sequence or cloth tangent orientation. |
| **R: spatial relation** | Explicit relation, point-versus-object scope and reference frame; report physical separation, projected overlap, containment/support separately. | Relation branch; all six directions tested in rotated frames with overlap counterexamples, mesh-gap and finite-whole-object tests, supported-on distinction. Unimplemented/ignored relation parameters fail preflight. | Cup above-vase observed. Other relations have local math evidence, not universal live coverage. Subtypes and approximations are listed below. |

### Every implemented spatial-relation subtype

| Relation | Point scope | Object scope | Physical limitation |
| --- | --- | --- | --- |
| `above`, `below` | Signed local-z point separation and margin. | Selected landmark separation plus mesh-footprint overlap projected along reference z. | A point-above test is not an object-above test; require `objects` scope for objects. |
| `left_of`, `right_of` | Signed local-x point separation and margin. | Signed local-x ordering plus footprint overlap projected along x. | This is a strict directional relation. Broad language allowing arbitrary perpendicular offsets is not the same definition. |
| `in_front_of`, `behind` | Signed local-y point separation and margin. | Signed local-y ordering plus footprint overlap projected along y. | Reference-frame viewpoint must be named; no hidden camera/world convention. |
| `near` | Point-to-point Euclidean distance; threshold is tolerance. | **Unsupported** surface distance, explicitly rejected. | Object-centre distance must not claim surface proximity. Margin is not a used parameter. |
| `inside_box` | Point within explicit positive half-extents. | All mesh vertices within that convex finite box. | Not an arbitrary open/nonconvex cavity or a wall-penetration test; `min_overlap_fraction` is irrelevant and rejected. |
| `on_top` | Point near the upper surface of an explicit box; requires half-extents. | Mesh height gap, projected overlap and force-bearing support-contact evidence. | Object version currently uses global bottom/top extrema, suitable for calibrated planar support; hanging, curved shells and local sloping supports need dedicated geometry. |
| `inside` arbitrary cavity, `covering`, `around`, `between`, `along`, `through`, `against`, `seated`, `flush`, `centred` | **No generic relation adapter.** Compose supported constraints only when they express the actual requested meaning. | **No generic relation adapter.** Task-specific native predicates remain separate evidence. | A taxonomy phrase is not automatically a runnable `expected` relation name. Paths, topology, holes and crossing often require temporal checks. |

### Timing, selectors and non-geometric factors

- Available events are `first_lift`, `first_motion`, read-only `first_predicate`
  and `stage_success`. There is no generic initial-selection, first physical
  tool impact, release-and-settle, handover, sustained-path or crease event.
  First-predicate only helps when a correctly grounded independent predicate
  exists. Lift uses environment z; motion uses 3D root displacement from the
  session baseline, not necessarily a task-normal or tangential movement.
- Available selectors are rigid root/centre poses and positions, finger contact
  points, robot EEF frames and annotated functional/support frames. A tool frame
  is not a tool contact; an EEF pose cannot replace finger contact. Contact/body
  membership and event timing are necessary in addition to coordinate math.
  Position-only object selectors may use explicit `points` scope for a root/centre
  point relation, which makes no whole-object claim. Historical EEF contact-proxy
  inputs can opt into the legacy schema flag; that does not meet this audit's
  contact definition and is excluded from the audited pilot/programs.
- Cached `ObjectSurfaces` meshes move with a rigid root. They do not update
  articulated child configurations, garment material vertices or liquid mass.
  Fold and changing-link geometry remain adapter gaps in every affected cell.
- Material identity/count/volume/flow rate, desired joint travel/state, twist
  angle/turn count, force/impulse, dwell/stability duration and categorical arm
  identity are outside the five geometric modifiers. The family audit specifies
  where these are required; their recognizers/measurement adapters are not
  implicitly supplied by a valid P/T/D/O/R condition.
- The JSON schema accepts custom slot strings; it does not enforce the taxonomy
  matrix or physical feasibility. The matrix is an audit contract, not a runtime
  dispatch system that installs missing family adapters.

### Corrections made during this exhaustive conditioning review

1. Validate finite vectors, nonzero quaternions, separate pose angle tolerances, event thresholds,
   axis lists, relation names/scopes/extents and overlap thresholds **before a
   rollout**. Reject irrelevant fields that a checker would silently ignore.
2. Require named frame references for D/O/R and real orientation-bearing
   selectors for T/O. Reject using point/contact selectors as reference frames.
3. Prevent object scope from silently substituting an object's geometry for a
   requested functional landmark. Attach meshes while preserving an explicitly
   chosen root or centre frame.
4. Normalize finite nonzero quaternions without numerical overflow/underflow.
5. Add the explicit `[source pour pose]` slot: the existing live cup-centre and
   axis checks measure the vessel, not a spout or stream.

Historical raw reports can still be recomputed by the low-level scorer. New
programs must pass the stricter preflight checks. Current packaged examples and
both suite generators are validated with these checks.

## Verify coverage

```bash
python scripts/atomic/conditioning_audit.py --check
python scripts/atomic/task_catalog.py --check
# After reviewing altered source, taxonomy or profiles:
python scripts/atomic/conditioning_audit.py --refresh
```

Coverage checks fail if a family, slot or factor is omitted or if source-backed
artifacts are stale. They verify an exhaustive review record; they do not run
all combinations in the simulator or prove policy steering.
