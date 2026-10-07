# Conditioning coverage: every action slot and factor

Reviewed **11 action families, 54 family-specific slots and 5 geometric factors**, i.e. **270 individual slot/factor cells** (including inapplicable cells). The [machine-readable audit](conditioning_audit.json) stores the concept, status and reasoning for each cell. Source fingerprints and exact slot coverage make omissions or stale artifacts detectable.

This is a complete **source/semantics coverage audit**, not a claim that every combination has a working adapter or live experiment. See [family recognition audit](ACTION_AUDIT.md), [all task examples](TASK_MAP.md) and [taxonomy matrices](TAXONOMY.md).

## Status meanings

| Code | Meaning | Cells |
| --- | --- | --- |
| **L** | Specific retained simulator measurement observed and independently reproduced; not universal live validation. | 10 |
| **C** | Finger contact location checker available; cell-specific live evidence absent. | 4 |
| **G** | Generic rigid point/frame/relation math and selectors available; calibrated assets/events and family wiring still needed. | 140 |
| **F** | Contact point has no orientation: use a separate physical frame and independent contact evidence. | 8 |
| **S** | Explicit object candidate snapshots/contact identity supported; automatic and landmark-specific selection remain. | 75 |
| **M** | Required measurement, event, trajectory, initial frame or relation adapter missing. | 5 |
| **NA** | Modifier does not apply to this categorical/intrinsic slot. | 28 |

**L/C/G refer to geometric measurement capability, not completed action recognition.** A native predicate can be true without the interaction. L applies only to the exact contact/event/asset described in its JSON evidence; the 10 L cells are not universally validated slots.

## Exhaustive slot × factor matrix

P = 3D point; T = SE(3) pose; D = landmark-relative displacement; O = landmark-relative orientation; R = spatial relation.

| Family | Slot | P | T | D | O | R | Required semantics / limitation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `pick` | `[object]` | S | S | S | S | S | Explicit labels and bounded initial-layout prefix/category/model queries retain immutable object-root/mesh-center snapshots, binding inventories, unique geometric target resolution and first sustained contact identity. Offline binding/geometry reproduction is implemented. Per-control/tip/cloth candidates, categorical language roles and query live validation remain. Moved final poses do not replace initial candidates. |
| `pick` | `[grasp region]` | C | F | L | F | C | Actual same-step finger/object manifold points. P/D/R can score contact location. T/O require a separate physical frame plus contact evidence, not an orientation on a point. Cup/charger pilot and later mallet grasp-band scores observed. The tool-contact mallet baseline retained a contact-held lift and 2.30 mm worst-point height error. Scissors lift event remained unobserved. Applies to these finger contacts, not every pick/asset. |
| `pick` | `[lift goal]` | G | G | G | G | G | Rigid point/frame geometry available. Bind to a calibrated landmark and explicit completion predicate; family recognition and live validation are separate. Reference time=stage_start freezes the actual landmark frame for lift displacement; root/centre pose and historical rigid footprints remain fixed. Local regression tested; no new live snapshot evidence. This is not a referent-selection adapter. |
| `place` | `[object]` | S | S | S | S | S | Explicit labels and bounded initial-layout prefix/category/model queries retain immutable object-root/mesh-center snapshots, binding inventories, unique geometric target resolution and first sustained contact identity. Offline binding/geometry reproduction is implemented. Per-control/tip/cloth candidates, categorical language roles and query live validation remain. Moved final poses do not replace initial candidates. |
| `place` | `[target]` | G | G | G | G | G | Rigid point/frame geometry available. Bind to a calibrated landmark and explicit completion predicate; family recognition and live validation are separate. |
| `place` | `[object goal]` | G | G | G | G | G | Rigid point/frame geometry available. Bind to a calibrated landmark and explicit completion predicate; family recognition and live validation are separate. |
| `place` | `[release point]` | G | G | G | G | G | supported_release emits object-specific release and settled events after held transport, all-finger release, support and bounded pose changes. Live rigid geometry can be sampled at either event. Offline counterexamples; task binding/calibration and live verification remain. |
| `push` | `[object]` | S | S | S | S | S | Explicit labels and bounded initial-layout prefix/category/model queries retain immutable object-root/mesh-center snapshots, binding inventories, unique geometric target resolution and first sustained contact identity. Offline binding/geometry reproduction is implemented. Per-control/tip/cloth candidates, categorical language roles and query live validation remain. Moved final poses do not replace initial candidates. |
| `push` | `[contact]` | C | F | L | F | C | Actual same-step finger/object manifold points. P/D/R can score contact location. T/O require a separate physical frame plus contact evidence, not an orientation on a point. Baseline T first-motion finger-contact score observed; conditioned run lacked finger evidence at that event. |
| `push` | `[hand approach]` | G | G | G | G | G | before_contact retains the synchronized point/frame and reference from the step immediately preceding actual contact. held_tool_strike measures target-relative pre-impact velocity, actual landmark-scoped impact and held separation/retraction. Offline counterexamples; physical frame/normal calibration and live evidence remain. |
| `push` | `[goal]` | G | L | G | G | G | Rigid point/frame geometry available. Bind to a calibrated landmark and explicit completion predicate; family recognition and live validation are separate. Conditioned T goal pose scored; push interaction remained unverified. Goal geometry is not action recognition. Rigid point/frame geometry available. Bind to a calibrated landmark and explicit completion predicate; family recognition and live validation are separate. Stage-start offsets use reference time=stage_start; episode-start state across later stages still requires a separately retained snapshot. |
| `push_with_tool` | `[tool]` | S | S | S | S | S | Explicit labels and bounded initial-layout prefix/category/model queries retain immutable object-root/mesh-center snapshots, binding inventories, unique geometric target resolution and first sustained contact identity. Offline binding/geometry reproduction is implemented. Per-control/tip/cloth candidates, categorical language roles and query live validation remain. Moved final poses do not replace initial candidates. |
| `push_with_tool` | `[object(s)]` | S | S | S | S | S | Explicit labels and bounded initial-layout prefix/category/model queries retain immutable object-root/mesh-center snapshots, binding inventories, unique geometric target resolution and first sustained contact identity. Offline binding/geometry reproduction is implemented. Per-control/tip/cloth candidates, categorical language roles and query live validation remain. Moved final poses do not replace initial candidates. |
| `push_with_tool` | `[tool tip]` | G | G | G | G | G | Actual tool/target collision pairs and calibrated active tip/edge frames are distinct from finger/tool grasp. Object-pair contact locations and functional-frame geometry are implemented; post-scene-load report enablement fixes the missing task-body APIs. Active-part calibration and fresh live recognition/geometry validation remain. |
| `push_with_tool` | `[start contact]` | G | F | G | F | G | Force-bearing object_contact_points resolves explicit tool/target pairs; first_contact records synchronized points/impulses. held_tool_push and held_tool_contact provide held stroke/contact evidence offline. held_tool_strike adds pre-impact approach speed and held retraction after impact; active-part calibration, musical timing and live verification remain. Contacts have no orientation. Actual contact points have no orientation. Use a separately calibrated physical tool/target frame and independently verify the contact event. |
| `push_with_tool` | `[sweep segment]` | G | G | G | G | G | TrajectoryObserver samples an explicit physical landmark each physics substep between declared events; records max/RMS polyline deviation, ordered waypoint witnesses, backtracking and coverage failures. Raw samples reproduce offline. Active sweep-tip calibration, feasibility and live validation remain; no inference between unsampled physics states. |
| `push_with_tool` | `[goal]` | G | G | G | G | G | Rigid point/frame geometry available. Bind to a calibrated landmark and explicit completion predicate; family recognition and live validation are separate. |
| `pour` | `[contents]` | NA | NA | NA | NA | NA | Categorical/material identity; geometry belongs on another named slot. Amount, flow, joint travel and twist angle are separate intrinsic parameters. |
| `pour` | `[source]` | S | S | S | S | S | Explicit labels and bounded initial-layout prefix/category/model queries retain immutable object-root/mesh-center snapshots, binding inventories, unique geometric target resolution and first sustained contact identity. Offline binding/geometry reproduction is implemented. Per-control/tip/cloth candidates, categorical language roles and query live validation remain. Moved final poses do not replace initial candidates. |
| `pour` | `[destination]` | S | S | S | S | S | Explicit labels and bounded initial-layout prefix/category/model queries retain immutable object-root/mesh-center snapshots, binding inventories, unique geometric target resolution and first sustained contact identity. Offline binding/geometry reproduction is implemented. Per-control/tip/cloth candidates, categorical language roles and query live validation remain. Moved final poses do not replace initial candidates. |
| `pour` | `[spout]` | G | G | G | G | G | Rigid functional-frame math available only after verifying a real mouth/spout tag and transfer event. A vessel centre is not a spout; no live spout evidence. |
| `pour` | `[opening]` | G | G | G | G | G | Persistent source-qualified material crossings measure XY opening error, aperture overrun, relative velocity direction and speed. Raw consecutive physics samples reproduce independently; excessive opening rotation or gaps are unscored. Vessel cavity/mouth calibration and fresh liquid USD readback validation remain. Nominal particle mass is not measured liquid volume or density. |
| `pour` | `[tilt]` | NA | G | NA | G | G | Use source vessel orientation for T/O and a verified spout point for R. Generic rigid math exists; no spout or stream measurement was observed live. |
| `pour` | `[source pour pose]` | G | G | G | L | L | Rigid point/frame geometry available. Bind to a calibrated landmark and explicit completion predicate; family recognition and live validation are separate. Cup local-z direction relative to vase observed at first whole-ball entry in conditioned run. Cup/vase height and projected footprint overlap observed at first whole-ball entry in conditioned run. |
| `actuate` | `[mechanism]` | S | S | S | S | S | Explicit labels and bounded initial-layout prefix/category/model queries retain immutable object-root/mesh-center snapshots, binding inventories, unique geometric target resolution and first sustained contact identity. Offline binding/geometry reproduction is implemented. Per-control/tip/cloth candidates, categorical language roles and query live validation remain. Moved final poses do not replace initial candidates. |
| `actuate` | `[control]` | S | S | S | S | S | Explicit labels and bounded initial-layout prefix/category/model queries retain immutable object-root/mesh-center snapshots, binding inventories, unique geometric target resolution and first sustained contact identity. Offline binding/geometry reproduction is implemented. Per-control/tip/cloth candidates, categorical language roles and query live validation remain. Moved final poses do not replace initial candidates. |
| `actuate` | `[contact]` | G | G | G | G | G | PhysX link frames, annotated moving-control joint binding, contact-coupled motion/press-release events and live child mesh geometry implemented. P/D/R use moving-link contacts. T/O require an oriented physical frame plus contact evidence. Link supported-on scopes signed support contacts to exact selected bodies. Per-asset calibration and live verification remain. |
| `actuate` | `[approach]` | G | G | G | G | G | PhysX link frames, annotated moving-control joint binding, contact-coupled motion/press-release events and live child mesh geometry implemented. P/D/R use moving-link contacts. T/O require an oriented physical frame plus contact evidence. Link supported-on scopes signed support contacts to exact selected bodies. Per-asset calibration and live verification remain. |
| `actuate` | `[state]` | G | G | G | G | G | PhysX link frames, annotated moving-control joint binding, contact-coupled motion/press-release events and live child mesh geometry implemented. P/D/R use moving-link contacts. T/O require an oriented physical frame plus contact evidence. Link supported-on scopes signed support contacts to exact selected bodies. Per-asset calibration and live verification remain. |
| `twist` | `[part]` | S | S | S | S | S | Explicit labels and bounded initial-layout prefix/category/model queries retain immutable object-root/mesh-center snapshots, binding inventories, unique geometric target resolution and first sustained contact identity. Offline binding/geometry reproduction is implemented. Per-control/tip/cloth candidates, categorical language roles and query live validation remain. Moved final poses do not replace initial candidates. |
| `twist` | `[axis/pivot]` | G | G | G | G | NA | contact_constrained_twist measures unwrapped signed substep rotation only during verified grip, part/target contact, pivot radius/depth and bounded off-axis motion. Pivot/axis/contact geometry requires calibrated asset frames. Failed attempts retain depth/radius but no fabricated angle; final orientation alone cannot recognize a twist. Live binding remains. |
| `twist` | `[contact]` | G | G | G | G | G | contact_constrained_twist measures unwrapped signed substep rotation only during verified grip, part/target contact, pivot radius/depth and bounded off-axis motion. Pivot/axis/contact geometry requires calibrated asset frames. Failed attempts retain depth/radius but no fabricated angle; final orientation alone cannot recognize a twist. Live binding remains. |
| `twist` | `[orientation]` | NA | G | NA | G | NA | contact_constrained_twist measures unwrapped signed substep rotation only during verified grip, part/target contact, pivot radius/depth and bounded off-axis motion. Pivot/axis/contact geometry requires calibrated asset frames. Failed attempts retain depth/radius but no fabricated angle; final orientation alone cannot recognize a twist. Live binding remains. |
| `insert` | `[object]` | S | S | S | S | S | Explicit labels and bounded initial-layout prefix/category/model queries retain immutable object-root/mesh-center snapshots, binding inventories, unique geometric target resolution and first sustained contact identity. Offline binding/geometry reproduction is implemented. Per-control/tip/cloth candidates, categorical language roles and query live validation remain. Moved final poses do not replace initial candidates. |
| `insert` | `[receptacle]` | S | S | S | S | S | Explicit labels and bounded initial-layout prefix/category/model queries retain immutable object-root/mesh-center snapshots, binding inventories, unique geometric target resolution and first sustained contact identity. Offline binding/geometry reproduction is implemented. Per-control/tip/cloth candidates, categorical language roles and query live validation remain. Moved final poses do not replace initial candidates. |
| `insert` | `[opening]` | G | G | G | G | G | Annotated tip/opening frame math and charger-specific entry predicates exist. Other assets need verified frames/clearance/crossing adapters; charger entry was not reached in the pilot. inside_aperture measures an actual closed-solid cross-section; inside_trace_aperture separately measures closed consistently directed actual material traces at one live calibrated plane, even when remote mesh ends are open. Explicit material paths, directed degree/winding and noncrossing traces are required. Both preserve aperture holes and planar clearance; local traces do not certify whole-solid volume. held_insertion separately requires outside-to-inside depth, hold and target contact. Annotated seat/rim poses measure gap/alignment but do not prove thread engagement or seating force. through/flush are not unrestricted generic relation names; live calibration remains. |
| `insert` | `[alignment]` | NA | G | G | G | G | Annotated tip/opening frame math and charger-specific entry predicates exist. Other assets need verified frames/clearance/crossing adapters; charger entry was not reached in the pilot. inside_aperture measures an actual closed-solid cross-section; inside_trace_aperture separately measures closed consistently directed actual material traces at one live calibrated plane, even when remote mesh ends are open. Explicit material paths, directed degree/winding and noncrossing traces are required. Both preserve aperture holes and planar clearance; local traces do not certify whole-solid volume. held_insertion separately requires outside-to-inside depth, hold and target contact. Annotated seat/rim poses measure gap/alignment but do not prove thread engagement or seating force. through/flush are not unrestricted generic relation names; live calibration remains. |
| `insert` | `[goal]` | G | G | G | G | G | Annotated tip/opening frame math and charger-specific entry predicates exist. Other assets need verified frames/clearance/crossing adapters; charger entry was not reached in the pilot. inside_aperture measures an actual closed-solid cross-section; inside_trace_aperture separately measures closed consistently directed actual material traces at one live calibrated plane, even when remote mesh ends are open. Explicit material paths, directed degree/winding and noncrossing traces are required. Both preserve aperture holes and planar clearance; local traces do not certify whole-solid volume. held_insertion separately requires outside-to-inside depth, hold and target contact. Annotated seat/rim poses measure gap/alignment but do not prove thread engagement or seating force. through/flush are not unrestricted generic relation names; live calibration remains. |
| `touch_with_tool` | `[target]` | S | S | S | S | S | Explicit labels and bounded initial-layout prefix/category/model queries retain immutable object-root/mesh-center snapshots, binding inventories, unique geometric target resolution and first sustained contact identity. Offline binding/geometry reproduction is implemented. Per-control/tip/cloth candidates, categorical language roles and query live validation remain. Moved final poses do not replace initial candidates. |
| `touch_with_tool` | `[contact]` | G | F | L | F | G | Force-bearing object_contact_points resolves explicit tool/target pairs; first_contact records synchronized points/impulses. held_tool_push and held_tool_contact provide held stroke/contact evidence offline. held_tool_strike adds pre-impact approach speed and held retraction after impact; active-part calibration, musical timing and live verification remain. Contacts have no orientation. Actual contact points have no orientation. Use a separately calibrated physical tool/target frame and independently verify the contact event. The geometry-tool-contacts-1006 xylophone baseline retained eight held impacts/retractions and actual mallet/xylophone contact-location errors of 1.23–6.33 mm. Raw contact, approach-speed and retraction-pose witnesses passed a separate consistency validator. Native task failed. The conditioned partner has seven consistent strike windows and one incompatible aborted-impact/completion window, excluded from scalar summaries. Current runtime archives interrupted event scores/paths and binds retries by attempt ID. This covers these impacts, not every tool/asset or musical timing. |
| `touch_with_tool` | `[tool]` | S | S | S | S | S | Explicit labels and bounded initial-layout prefix/category/model queries retain immutable object-root/mesh-center snapshots, binding inventories, unique geometric target resolution and first sustained contact identity. Offline binding/geometry reproduction is implemented. Per-control/tip/cloth candidates, categorical language roles and query live validation remain. Moved final poses do not replace initial candidates. |
| `touch_with_tool` | `[tool tip]` | G | G | G | G | G | Actual tool/target collision pairs and calibrated active tip/edge frames are distinct from finger/tool grasp. Object-pair contact locations and functional-frame geometry are implemented; post-scene-load report enablement fixes the missing task-body APIs. Active-part calibration and fresh live recognition/geometry validation remain. |
| `touch_with_tool` | `[approach]` | G | G | G | G | G | before_contact retains the synchronized point/frame and reference from the step immediately preceding actual contact. held_tool_strike measures target-relative pre-impact velocity, actual landmark-scoped impact and held separation/retraction. Offline counterexamples; physical frame/normal calibration and live evidence remain. |
| `handover` | `[object]` | S | S | S | S | S | Explicit labels and bounded initial-layout prefix/category/model queries retain immutable object-root/mesh-center snapshots, binding inventories, unique geometric target resolution and first sustained contact identity. Offline binding/geometry reproduction is implemented. Per-control/tip/cloth candidates, categorical language roles and query live validation remain. Moved final poses do not replace initial candidates. |
| `handover` | `[giver]` | NA | NA | NA | NA | NA | Categorical/material identity; geometry belongs on another named slot. Amount, flow, joint travel and twist angle are separate intrinsic parameters. |
| `handover` | `[receiver]` | NA | NA | NA | NA | NA | Categorical/material identity; geometry belongs on another named slot. Amount, flow, joint travel and twist angle are separate intrinsic parameters. |
| `handover` | `[exchange]` | G | G | G | G | G | grip_transfer emits giver_hold, overlap and receiver_only transitions from actual named-arm contacts. Live object frames/positions can be sampled at those events. Offline counterexamples; task arm/frame bindings and live verification remain. |
| `handover` | `[object orientation]` | NA | G | NA | G | NA | grip_transfer emits giver_hold, overlap and receiver_only transitions from actual named-arm contacts. Live object frames/positions can be sampled at those events. Offline counterexamples; task arm/frame bindings and live verification remain. |
| `fold` | `[deformable]` | G | G | G | G | G | Stable material IDs support actual cloth points, tagged tangent frames and two-landmark crease frames. CPU readback requires running cloth and Fabric disabled; GPU tensors require initialized PhysX views. cloth_landmark_fold recognizes newly lifted/bent/closed/stable material deformation, not finger contact or full layer/self-intersection correctness. Offline counterexamples passed; selected material patch layer geometry is implemented, with live validation pending. |
| `fold` | `[crease]` | G | G | G | G | L | Stable material IDs support actual cloth points, tagged tangent frames and two-landmark crease frames. CPU readback requires running cloth and Fabric disabled; GPU tensors require initialized PhysX views. cloth_landmark_fold recognizes newly lifted/bent/closed/stable material deformation, not finger contact or full layer/self-intersection correctness. Offline counterexamples passed; selected material patch layer geometry is implemented, with live validation pending. The geometry-crease-segments-1006 baseline retained finite endpoint-chord Hausdorff errors of 73.7–78.8 mm, independently reproduced. Native success did not imply a qualified fold observer. This validates declared finite material chords, not a curved path or discovery of the newly formed physical crease; curve-pair live evidence is pending. |
| `fold` | `[moving region]` | G | G | G | G | L | Stable material IDs support actual cloth points, tagged tangent frames and two-landmark crease frames. CPU readback requires running cloth and Fabric disabled; GPU tensors require initialized PhysX views. cloth_landmark_fold recognizes newly lifted/bent/closed/stable material deformation, not finger contact or full layer/self-intersection correctness. Offline counterexamples passed; selected material patch layer geometry is implemented, with live validation pending. Actual model/topology-bound patches measured coverage and horizontal gap in geometry-cloth-patches-1006 conditioned and geometry-crease-segments-1006 baseline episodes. Zero overlap leaves vertical gaps unobserved; body-patch coverage 0.0553 in the chord baseline had 13.8–38.7 mm overlapping-region gaps. These belong to distinct completed frozen comparisons. No whole-garment layering or grasp-force claim. |
| `fold` | `[target region]` | G | G | G | G | L | Stable material IDs support actual cloth points, tagged tangent frames and two-landmark crease frames. CPU readback requires running cloth and Fabric disabled; GPU tensors require initialized PhysX views. cloth_landmark_fold recognizes newly lifted/bent/closed/stable material deformation, not finger contact or full layer/self-intersection correctness. Offline counterexamples passed; selected material patch layer geometry is implemented, with live validation pending. Actual fixed-ID target material patches served as the live references in the same patch/chord episodes, with coverage, planar distance and overlapping-region gap reproduction. This applies to these selected material regions; full layer order, force-bearing contact and global self-intersection remain unresolved. |
| `fold` | `[grasp point]` | M | M | M | M | M | Actual finger/cloth-particle contact correspondence is unavailable. Material landmarks, EEF proximity and deformation cannot substitute for a measured cloth grasp contact. |
| `fold` | `[final orientation]` | NA | G | NA | L | NA | Stable material IDs support actual cloth points, tagged tangent frames and two-landmark crease frames. CPU readback requires running cloth and Fabric disabled; GPU tensors require initialized PhysX views. cloth_landmark_fold recognizes newly lifted/bent/closed/stable material deformation, not finger contact or full layer/self-intersection correctness. Offline counterexamples passed; selected material patch layer geometry is implemented, with live validation pending. The geometry-surface-gaps-1006 conditioned episode measured actual material tangent-normal direction errors for all three observers, independently reproduced. This covers the declared local normal axes, not every global cloth orientation or physical grasp. Native task and all fold observers failed; scalar final geometry remained observed. |

## Factor-level checker audit

All five factor kernels have local known-geometry and counterexample tests.
Each taxonomy cell above separately records its binding/evidence status; kernel
availability does not establish live coverage of every applicable slot.

| Factor | Measurement and physical units | Runtime and remaining boundary |
| --- | --- | --- |
| **P: 3D point** | Euclidean error on declared XYZ axes, metres (reports use mm). | Live material/functional/contact points and explicit initial candidate snapshots. Initial selection is scored against the actually contacted candidate, not the moved final position. |
| **T: SE(3) pose** | Translation in metres and orientation in radians, reported separately in mm/degrees. | Real live rigid/link/gripper/material frames; calibrated root offsets compose with current PhysX roots. Material crease line frames follow persistent vertices. A contact point has no orientation. |
| **D: relative displacement** | Requested vector in the named reference frame; error on declared axes in metres. | Every force-bearing contact is scored; the worst contact determines acceptance. Live and stage-start references are explicit. Held endpoints, release, receiver-only and attempt-end samples have separate semantics. |
| **O: relative orientation** | Quaternion/full-frame or declared symmetric-axis angular error, radians. | Actual contacting-arm TCP orientation needs force-qualified finger contacts. Material tangent orientation follows deforming vertices. Unwrapped constrained twist is measured by its recognizer rather than endpoint quaternion error. |
| **R: spatial relation** | Separation/gap in metres, footprint area in m², overlap fraction, outside solid volume in m³ and outside fraction. | Directional whole-object relations require projected triangle overlap. Supported-on additionally needs physical support. Explicit interior box unions and opening polygons are calibrated independently of outer bounds. Nonclosed or duplicate/proxy solids cannot certify volume/fit; selected material meshes are explicit. |

Contact reporting is enabled after every task scene is loaded. The initial
simulator scene contains only robots; enabling reporting once at construction
misses object/object contacts. Fresh stack runs validate this lifecycle change;
previous queued packages retain their original instrumentation. Support history
may span quiet steps only while both poses remain unchanged and no contact-lost
notification occurs. Episode resets clear all history.

### Every implemented spatial-relation subtype

| Relation | Point scope | Object scope | Physical limitation |
| --- | --- | --- | --- |
| `above`, `below` | Signed local-z point separation and margin. | Selected landmark separation plus mesh-footprint overlap projected along reference z. | A point-above test is not an object-above test; require `objects` scope for objects. |
| `left_of`, `right_of` | Signed local-x point separation and margin. | Signed local-x ordering plus footprint overlap projected along x. | This is a strict directional relation. Broad language allowing arbitrary perpendicular offsets is not the same definition. |
| `in_front_of`, `behind` | Signed local-y point separation and margin. | Signed local-y ordering plus footprint overlap projected along y. | Reference-frame viewpoint must be named; no hidden camera/world convention. |
| `near` | Point-to-point Euclidean distance; threshold is tolerance. | Exact selected triangle-boundary distance with AABB-tree pruning and intersection tests. | Requires explicit reviewed material mesh paths or live material patch surfaces; no centre proxy. Gap does not establish support, physical touch or collision-free placement. |
| `inside_box` | Point within explicit positive half-extents. | All mesh vertices within that convex finite box. | Not an arbitrary open/nonconvex cavity or a wall-penetration test; `min_overlap_fraction` is irrelevant and rejected. |
| `inside_region` | Unsupported; a point cannot certify a solid. | Closed oriented material volume outside a calibrated finite box union; vertex error separately. | Explicit conservative interiors; nonclosed solids and outer-bound proxies are rejected. |
| `inside_aperture` | Unsupported whole-part certification. | Actual solid cross-section outside calibrated polygon/holes, with requested physical clearance. | One-plane fit does not prove full insertion path, seating force or threads. |
| `layered_over` | Unsupported; one landmark gap cannot certify patch order. | Explicit material faces: moving footprint coverage and all overlapping triangle-pair gap extrema. | Local selected-patch layering; no measured grasp or whole-cloth self-intersection claim. |
| `intersects_segment` / `coincides_with_segment` | Exact finite material-endpoint chord gap / symmetric Hausdorff distance, with separate lengths and unsigned axis angle. | Not an object-mesh relation. | Live or frozen actual cloth-tag endpoints; no infinite-line/midpoint proxy and no curved-crease claim. |
| `on_top` | Point near the upper surface of an explicit box; requires half-extents. | Mesh height gap, projected overlap and force-bearing support-contact evidence. | Object version currently uses global bottom/top extrema, suitable for calibrated planar support; hanging, curved shells and local sloping supports need dedicated geometry. |
| `inside` arbitrary cavity, `covering`, `around`, `between`, `along`, `through`, `against`, `seated`, `flush`, `centred` | **No generic relation adapter.** Compose supported constraints only when they express the actual requested meaning. | **No generic relation adapter.** Task-specific native predicates remain separate evidence. | A taxonomy phrase is not automatically a runnable `expected` relation name. Paths, topology, holes and crossing often require temporal checks. |

### Timing, selectors and non-geometric factors

- Events include `first_lift`, `first_motion`, read-only `first_predicate`,
  `first_contact`, synchronized `before_contact`, physical `recognition_event`,
  `stage_success`, and `attempt_end` before reset. Recognizers emit separate
  release/settled, impact/retraction, giver/overlap/receiver-only, insertion,
  rotation, source-exit/transfer and folded transitions. An absent event remains
  unobserved. Initial selection and trajectory observers have separate schemas.
- Selectors distinguish rigid root/mesh centre, actual finger and object-pair
  contacts, named/contacting-arm TCP, live articulated child/joint frames,
  functional/support annotations, calibrated model-checked root offsets, actual
  cloth/fluid points, material tangent/crease frames and explicit patch faces.
  Contact points have no orientation; TCP origins do not measure grasp/contact
  location. Frozen references use stage-start evidence explicitly.
- Rigid meshes follow live PhysX root poses; articulated child surfaces follow
  link tensors. Cached rigid geometry is rejected for cloth/fluid. Deforming
  material geometry uses synchronized live solver readback and persistent IDs;
  CPU cloth USD readback additionally requires Fabric disabled and running PhysX.
  Explicit material meshes avoid duplicate visual/collision representations.
- Material identity/count/nominal mass, joint travel/state, unwrapped twist angle,
  contact impulse and dwell/stability duration are intrinsic action metrics,
  separate from P/T/D/O/R. Fluid nominal mass does not establish measured density
  or volume. Whole-cloth force contact and curved crease geometry remain gaps.
- Custom slot strings remain allowed; preflight validates measurement semantics
  but does not establish target feasibility. The matrix records the review and
  binding/evidence level; it does not automatically install missing task bindings.

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

### Ordered material-curve relations

`intersects_curve` scores minimum finite edge-pair distance and
`coincides_with_curve` scores symmetric continuous polyline Hausdorff distance,
including edge interiors. They require `curves` scope and two explicit ordered
persistent cloth paths. A path cannot supply a point/pose/orientation selector.
The actual model/file/topology are checked for calibrated paths; all three
garment models are bound before policy execution. Identifying a newly formed
physical crease, physical cloth contact and full self-intersection remain gaps.

Contact setup now installs report APIs before each new body enters tensor
initialization; the later scan is an idempotent audit. Invalid nested body
declarations without transform-stack resets are recorded and excluded from
independent setup. Frozen earlier suites retain their original lifecycle.

### Local section relation

`inside_trace_aperture` measures closed oriented actual material plane traces
against a calibrated opening with preserved holes and planar clearance. Explicit
reviewed material paths and a live calibrated reference are required. Remote
open ends do not prevent this local measurement, but open/duplicate/branching/
inconsistent/crossing/coplanar traces fail. `inside_aperture` and volume checkers
still require a whole closed solid. Both charger prongs are asset-calibrated
for a common pose; simulator validation remains pending.
