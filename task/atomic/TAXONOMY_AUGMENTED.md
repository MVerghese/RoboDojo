# RoboDojo augmented action taxonomy for System 1 / System 2 (proposal v2)

This standalone proposal extends [TAXONOMY.md](TAXONOMY.md) to cover the **60 task categories C01–C60** in the [SDG catalog](http://10.111.67.22:3000/assets/sdg-task-categories-20260930/index.html). It preserves the original 11 families and their slot matrices, adds **nine novel interaction families**, and maps every catalog category to actions, composition operators, and physical constraints. The original file is unchanged.

The inherited taxonomy appears first, followed by [new families and slot matrices](#augmentation-nine-new-action-families), [extensions and shared execution slots](#extensions-to-inherited-families-and-shared-execution-slots), and the [complete task crosswalk](#complete-crosswalk-catalog-c01c60). The inherited text describes the original RoboDojo benchmark; the augmentation describes the broader proposed action API.

**Status:** this is a conceptual taxonomy and composition design, not an implementation or a claim of policy capability. Current schema/runtime/conditioning audits remain scoped to the original taxonomy. New families, modes, predicates, and slots need schema, controller, asset-binding, recognition, and measurement work before they become executable calls. A catalog category being “atomic” does not establish that it is one atomic interaction under this taxonomy.

## Sources and decision rules

- Baseline: local `task/atomic/TAXONOMY.md`, read 2026-10-05; SHA-256 `24eca0dd1915859e96c8b797c42d4f85fde79861993e02b41005bf0b46cd40ac`.
- Catalog: the supplied index and its linked [data.json](http://10.111.67.22:3000/assets/sdg-task-categories-20260930/data.json), retrieved 2026-10-05; JSON SHA-256 `489443fa2137a4357ec3a97a43c0884d7b139dbac990df9a77fd89ce62e8e629`. All 60 category definitions, constraints, examples, and arm patterns were reviewed. The source date is 2026-09-30; the URL is an internal service and may change.
- Repository boundaries: [ACTION_AUDIT.md](ACTION_AUDIT.md), [INSTRUMENTATION_AUDIT.md](INSTRUMENTATION_AUDIT.md), [CONDITIONING_AUDIT.md](CONDITIONING_AUDIT.md), and [FIX_STATUS.md](FIX_STATUS.md). The external catalog describes robotsim-v2 source/asset status; that status must not be transferred to this RoboDojo runtime.

A new object, target relation, orientation, amount, timing constraint, arm assignment, or repetition is not by itself a new family. Add a family when a bounded physical interaction is missing: constrained disengagement, tool loading, bulk mixing, driven material discharge, deposition/removal of a surface layer, non-fold deformable shaping, or new material fracture. Catalog names and goal predicates are evidence for a proposed design, not proof of observed execution. In particular, material, attachment, routing, and device effects must not be inferred from final rigid poses alone.

## Inherited taxonomy: original 11 families

## Scope and unit of analysis

This is a proposed **atomic-action benchmark derived from RoboDojo**, not an official RoboDojo taxonomy. It uses the public RoboDojo task repository at commit `726e9aa` as its task source. A primitive is one bounded, observable interaction with a clear success event. Existing RoboDojo tasks often chain several primitives, such as pick → handover → insert → turn. For an atomic trial, initialize the scene at the primitive's precondition (for example, the tool is already held for a sweep). Otherwise, score the necessary setup actions separately.

Use the nine proposed families as the core. Add **handover** and **fold** to cover RoboDojo tasks that cannot be described cleanly by those nine. `Place` covers stack, hang, cover, and put-in when there is no constrained insertion path. `Actuate` covers pressing, pulling, opening, and closing an articulated mechanism. `Touch with tool` covers a strike or tap; `push with tool` requires a sustained contact that displaces the object. `Twist` requires rotation around a specified axis; it may follow `insert`, but is a separate event. Sorting, arranging, building, playing, and making toast are task programs built from primitives, not primitive types.

## Geometric modifier vocabulary

| Code | Modifier | Typed value | Example |
| --- | --- | --- | --- |
| **P** | 3D point | `point(frame, x, y, z)` | Press at a point on the button face. |
| **T** | SE(3) pose | `pose(frame, position, orientation)` | Release a block at a specified object pose. |
| **D** | Relative displacement to a task landmark | `landmark + vector_in_landmark_frame` | Contact the block 2 cm left of its center. |
| **O** | Relative orientation to an orientation landmark | `landmark_orientation ⊗ rotation_offset` | Align a key's long axis with the slot. |
| **R** | Spatial relation | `relation(object, landmark, reference_frame)` | Place the cup behind the bowl; put the egg inside its holder. |

`P` and `T` may describe either an observed initial location (object selection) or a commanded interaction/goal. These must be distinct fields. For example, “pick the object at `(x,y,z)`” selects an object, while “grasp the object at `(x,y,z)`” constrains the grasp. A `D` value is an offset from a named landmark, not a free world-space coordinate. A relation such as *left of* needs an explicit viewpoint or frame; *inside* and *on* need an explicit target volume or support surface. Every modifier needs a tolerance. Respect rotational symmetries when scoring orientation (for example, the yaw of a round cup may be irrelevant).

The five modifiers can be composed. Two `P` values define a fold line or sweep segment; a `T` plus `D` defines an approach pose offset from a target. These constructions avoid introducing a separate path or line modifier in v1, although motion along the segment must still be checked from a trajectory.

## Templates and applicable slots

Bracketed terms are fillable slots. The “geometry on slots” column names *where* each modifier attaches; it is not a claim that every modifier makes sense on every slot. `P/T/D/O/R` use the definitions above.

| Family | Atomic instruction template | Geometry on slots, with a concrete example | Observable success event | RoboDojo example |
| --- | --- | --- | --- | --- |
| **Pick** | `Pick [object] at [grasp region]` | `[object]`: P or R for referent selection (“the cup left of the bowl”); `[grasp region]`: P, T, or D (“2 cm below handle center”), optionally O for gripper orientation. `[lift goal]`: P or D (“raise 10 cm from initial pose”). | Stable grasp and required lift. | `general_pickup` |
| **Place** | `Place [object] at/on/in [target]` | `[target]`: P, T, D, or R (“inside the box”); `[object goal]`: T or O (“front faces left”); `[release point]`: P or D. | Object released and supported in target region/pose. | `pack_objects_into_box`, `stack_blocks`, `hang_mugs` |
| **Push** | `Push [object] at [contact] to [goal]` | `[contact]`: P or D (“contact 2 cm right of center”), optionally T/O for hand approach; `[goal]`: P, T, D, or R (“move behind pad”). | Object reaches goal through sustained direct contact. | `push_T` |
| **Push with tool / sweep** | `Using [tool], sweep/push [object(s)] from [start contact] to [goal]` | `[tool tip/contact]`: P, T, or D; `[start contact]`: P or D; `[goal]`: P, T, D, or R (“into dustpan”). Two P values can define intended sweep segment; O can constrain tool heading. | Tool makes contact and displaces object(s) to goal. | `sweep_blocks` |
| **Pour** | `Pour [contents] from [source] into [destination]` | `[source spout]`: P or D; `[destination opening]`: P, T, D, or R (“inside cup”); `[source tilt]`: T or O (“tilt toward cup”). | Required material enters destination. | `pour_liquid_into_cup`, `pour_balls_into_vase` |
| **Actuate** | `Actuate [mechanism] at [control] to [state]` | `[control/contact]`: P, T, or D (“press top half of button”); `[approach]`: T or O; `[state]`: usually a joint endpoint or displacement, optionally expressed as R (“lid closed against base”). | Joint crosses specified state/threshold. | `press_by_number`, `make_toast`, `fill_egg_holder` |
| **Twist** | `Twist [part] about [axis/pivot] to [orientation]` | `[axis/pivot]`: P plus O/T for axis direction; `[contact]`: P, T, or D; `[orientation]`: T or O relative to a keyed landmark. | Part achieves prescribed rotation about its axis. | `fasten_screws`; `insert_key` instruction |
| **Insert** | `Insert [object] into [receptacle] via [opening]` | `[opening]`: P, T, or D; `[alignment]`: O or T (“key axis aligned to slot”); `[goal]`: T, D, or R (“inside slot to 2 cm depth”). | Object passes opening and reaches depth while aligned. | `insert_key`, `insert_tubes`, `plug_in_charger` |
| **Touch with tool** | `Touch/strike [target] at [contact] using [tool]` | `[contact]`: P or D (“center of third key”); `[tool tip]`: P or T; `[approach]`: T or O, optionally D (“approach from 3 cm above”). | Correct target receives tool contact/strike. | `play_Xylophone` |
| **Handover** *(extension)* | `Hand [object] from [giver] to [receiver] at [exchange]` | `[exchange]`: P or T, possibly D/R (“above center of table”); `[object orientation]`: T or O relative to receiver gripper. | Receiver gains stable grasp before giver releases. | `insert_key`, `sweep_blocks`, `put_bottles_into_dustbin` instructions |
| **Fold** *(extension)* | `Fold [deformable] along [crease] so [moving region] lands at [target region]` | `[crease]`: two P values or T for line location/direction; `[grasp point]`: P/D; `[target region]`: P, D, or R (“sleeve over chest”); `[final orientation]`: O where meaningful. | Named garment landmarks overlap/align in the intended folded state. | `fold_clothes` |

### Exhaustive slot-by-modifier matrix

Each row below is a slot in the compact template above or an **optional** slot that makes an implicit geometric instruction explicit. Each column gives the condition that modifier can express for that slot; `—` means that modifier is not a natural condition for that slot. Object, tool, mechanism, and target **identity slots** use geometry to *select a referent in the initial scene*. Interaction and goal slots use geometry to *constrain execution*. This distinction must be preserved in the benchmark record. A `T` condition contains position and orientation; use P/D for position-only constraints or O for orientation-only constraints. `O` is orientation **relative to a named orientation landmark**, not an absolute angle. Spatial relations `R` must name both the landmark and reference frame when relevant.

These are conceptual slot capabilities. The [conditioning coverage audit](CONDITIONING_AUDIT.md) separately records the implementation and live evidence for **every slot × modifier cell**. T/O in a contact row requires a separately named physical gripper/tool frame plus independent contact evidence; a contact point itself has no orientation. Selection, release, continuous paths, articulated links and garment frames need the adapters specified in that audit.

**Pick —** `Pick [object] at [grasp region]` (optional `[lift goal]`).

| Slot | P: 3D point | T: SE(3) pose | D: landmark offset | O: relative orientation | R: spatial relation |
| --- | --- | --- | --- | --- | --- |
| `[object]` | Select object whose initial center is at P. | Select by initial pose T. | Select object offset from a named landmark. | Select object rotated relative to a landmark. | Select object left of/inside another object. |
| `[grasp region]` | Grasp at a surface point. | Match gripper contact pose. | Grasp at offset from handle/center. | Align gripper with handle orientation. | Grasp above/below/around a named feature. |
| `[lift goal]` *(optional)* | Bring object center to P. | Bring held object to T. | Lift by vector from initial object pose. | Maintain object orientation relative to a landmark. | Hold object above a named surface. |

**Place —** `Place [object] at/on/in [target]` (optional `[object goal]`, `[release point]`).

| Slot | P | T | D | O | R |
| --- | --- | --- | --- | --- | --- |
| `[object]` | Select by initial center P. | Select by initial pose T. | Select by offset from a landmark. | Select by orientation relative to a landmark. | Select the object behind/on/inside another. |
| `[target]` | Place at target point. | Match target pose. | Place at offset from target landmark. | Orient placed object relative to target axis. | Place on/in/next to/behind target. |
| `[object goal]` *(optional)* | Set final object center to P. | Set final object pose to T. | Set final center relative to target. | Align final object orientation to target. | Require final object on/in/covering target. |
| `[release point]` *(optional)* | Release when object/gripper is at P. | Release at specified object/gripper pose. | Release at offset from target. | Release with object aligned to target. | Release above/inside target region. |

**Push —** `Push [object] at [contact] to [goal]` (optional `[hand approach]`).

| Slot | P | T | D | O | R |
| --- | --- | --- | --- | --- | --- |
| `[object]` | Select by initial center P. | Select by initial pose T. | Select by offset from landmark. | Select by relative orientation. | Select object beside/in front of landmark. |
| `[contact]` | First effective contact at surface point P. | Match hand contact pose T. | Contact at offset from object center/feature. | Hand orientation relative to object face. | Contact on left/right/back side of object. |
| `[hand approach]` *(optional)* | Pass through pre-contact point P. | Match pre-contact pose T. | Approach from offset from contact/center. | Align hand heading to object axis. | Approach from behind/above object. |
| `[goal]` | Final object center at P. | Final object pose T. | Translate object relative to initial pose/landmark. | Final orientation relative to pad. | End on/behind/next to goal region. |

**Push with tool / sweep —** `Using [tool], sweep/push [object(s)] from [start contact] to [goal]` (optional `[tool tip]`, `[sweep segment]`).

| Slot | P | T | D | O | R |
| --- | --- | --- | --- | --- | --- |
| `[tool]` | Select tool by initial center P. | Select tool by initial pose T. | Select tool by offset from landmark. | Select tool by orientation relative to landmark. | Select tool on/next to rack. |
| `[object(s)]` | Select objects at points/within point regions. | Select rigid objects by initial poses. | Select objects offset from landmark. | Select oriented rigid objects. | Select objects left of/inside region. |
| `[tool tip]` *(optional)* | Specify contact point on tool. | Specify tool-tip contact pose. | Specify tip offset from tool handle. | Align tip orientation to target surface. | Keep tip below/behind object center. |
| `[start contact]` | First tool-object contact at P. | First tool-object contact pose T. | Start at offset from object center. | Tool heading relative to object/edge. | Start behind/in front of objects. |
| `[sweep segment]` *(optional)* | Two P values define start and end. | Start/end tool poses define segment. | Start/end offsets from landmarks. | Tool orientation along segment relative to target axis. | Segment goes through/along/around region. |
| `[goal]` | Final object center(s) at P/points. | Final rigid object pose(s) T. | Final offset from target landmark. | Final rigid object orientation relative to target. | Objects end inside dustpan/on target. |

**Pour —** `Pour [contents] from [source] into [destination]` (optional `[spout]`, `[opening]`, `[tilt]`, `[source pour pose]`).

| Slot | P | T | D | O | R |
| --- | --- | --- | --- | --- | --- |
| `[contents]` | — | — | — | — | — |
| `[source]` | Select vessel at P. | Select vessel at initial pose T. | Select vessel offset from landmark. | Select vessel oriented relative to landmark. | Select vessel left of/on landmark. |
| `[destination]` | Select vessel at P. | Select vessel at initial pose T. | Select vessel offset from landmark. | Select vessel oriented relative to landmark. | Select vessel behind/on landmark. |
| `[spout]` *(optional)* | Spout exit at P during flow. | Spout exit pose T during flow. | Spout offset from destination opening. | Spout axis relative to opening axis. | Spout above/inside opening. |
| `[opening]` *(optional)* | Aim stream at opening point P. | Match opening pose T. | Aim at offset within opening. | Stream direction relative to opening normal. | Stream enters interior of destination. |
| `[tilt]` *(optional)* | — | Source pose at pour event T. | — | Source rotation relative to destination/vertical. | Spout above destination during tilt. |
| `[source pour pose]` *(optional)* | Source vessel centre at P during transfer. | Source vessel frame at T during transfer. | Vessel centre offset from destination landmark. | Vessel orientation relative to destination frame. | Vessel above destination with projected footprint overlap. |

`[source pour pose]` names the vessel frame/mesh centre explicitly. It is distinct from the spout and stream. The current ball pilot measures this slot; it does not measure a spout position or stream impact point.

`[contents]` denotes material identity (liquid, balls, etc.), not a rigid body with a single pose. Volume, count, flow rate, and amount are non-geometric parameters outside these five modifiers. Geometry of the contents **after** the action is specified through `[opening]` or the destination's `inside` relation.

**Actuate —** `Actuate [mechanism] at [control] to [state]` (optional `[contact]`, `[approach]`).

| Slot | P | T | D | O | R |
| --- | --- | --- | --- | --- | --- |
| `[mechanism]` | Select mechanism by initial center P. | Select by initial pose T. | Select by offset from landmark. | Select by orientation relative to landmark. | Select mechanism left of/inside assembly. |
| `[control]` | Select button/lever at P. | Select control by initial pose T. | Select control offset from mechanism center. | Select control by relative orientation. | Select top/left control of mechanism. |
| `[contact]` *(optional)* | Press/pull at point P on control. | Match hand contact pose T. | Contact offset from control center. | Hand orientation relative to control axis. | Contact above/below/at end of control. |
| `[approach]` *(optional)* | Pass through pre-contact point P. | Match pre-contact hand pose T. | Approach from offset from control. | Align hand with joint motion axis. | Approach from above/side of control. |
| `[state]` | Control/link ends at point P. | Control/link ends at pose T. | Link endpoint displaced relative to frame. | Link orientation relative to mechanism base. | Lid against base; lever below stop. |

`[state]` can also be specified by a scalar joint angle or button travel. That scalar is an intrinsic action parameter, not one of the five geometric modifiers; its geometric versions are listed above.

**Twist —** `Twist [part] about [axis/pivot] to [orientation]` (optional `[contact]`).

| Slot | P | T | D | O | R |
| --- | --- | --- | --- | --- | --- |
| `[part]` | Select part by center P. | Select by initial pose T. | Select part offset from landmark. | Select by orientation relative to landmark. | Select part on/inside assembly. |
| `[axis/pivot]` | Pivot point P (a point alone does not define axis). | Pose T defines pivot and directed axis. | Pivot offset from part/landmark. | Axis direction relative to landmark axis. | — |
| `[contact]` *(optional)* | Grasp/contact point P. | Hand contact pose T. | Contact offset from pivot/handle. | Hand orientation relative to twist axis. | Grasp outside rim/at end of handle. |
| `[orientation]` | — | Final part pose T. | — | Final orientation relative to slot/base (e.g. mark facing front). | — |

The twist **angle** is an intrinsic scalar parameter. When the task specifies it, score angular change about the chosen axis as well as the final orientation.

**Insert —** `Insert [object] into [receptacle] via [opening]` (optional `[alignment]`, `[goal]`).

| Slot | P | T | D | O | R |
| --- | --- | --- | --- | --- | --- |
| `[object]` | Select by initial center P. | Select by initial pose T. | Select by offset from landmark. | Select by orientation relative to landmark. | Select object beside/on landmark. |
| `[receptacle]` | Select by center P. | Select by initial pose T. | Select by offset from landmark. | Select by orientation relative to landmark. | Select receptacle on/behind assembly. |
| `[opening]` | Entry point P. | Entry pose T with approach axis. | Entry point offset from opening center. | Entry axis relative to receptacle axis. | Enter through named side/opening. |
| `[alignment]` *(optional)* | — | Object entry pose T. | Object centerline offset from receptacle centerline. | Object axis aligned to receptacle axis. | Object centered in opening. |
| `[goal]` *(optional)* | Final object feature at P. | Final object pose T. | Insertion depth/offset relative to rim or seat. | Final orientation relative to receptacle. | Fully inside/seated/flush with receptacle. |

**Touch with tool —** `Touch/strike [target] at [contact] using [tool]` (optional `[tool tip]`, `[approach]`).

| Slot | P | T | D | O | R |
| --- | --- | --- | --- | --- | --- |
| `[target]` | Select target at P. | Select by initial pose T. | Select target offset from landmark. | Select by relative orientation. | Select third key/left of another target. |
| `[contact]` | Strike surface point P. | Tool-target contact pose T. | Strike offset from target center. | Tool orientation relative to target normal. | Strike center/left side of target. |
| `[tool]` | Select tool at P. | Select by initial pose T. | Select tool offset from landmark. | Select by relative orientation. | Select tool on rack. |
| `[tool tip]` *(optional)* | Name impact point on tool. | Specify tip contact pose T. | Tip offset from tool handle/head center. | Tip orientation relative to target. | Tip above/inside target region at contact. |
| `[approach]` *(optional)* | Pass through pre-impact point P. | Match pre-impact tip pose T. | Approach from offset above contact. | Tool axis relative to target normal. | Approach from above/side. |

**Handover —** `Hand [object] from [giver] to [receiver] at [exchange]` (optional `[object orientation]`).

| Slot | P | T | D | O | R |
| --- | --- | --- | --- | --- | --- |
| `[object]` | Select by initial center P. | Select by initial pose T. | Select by offset from landmark. | Select by relative orientation. | Select object left of/on table. |
| `[giver]` | — | — | — | — | — |
| `[receiver]` | — | — | — | — | — |
| `[exchange]` | Object/gripper exchange at P. | Exchange object pose T. | Exchange offset from table/robot landmark. | Object orientation relative to receiver gripper. | Exchange above table/between arms. |
| `[object orientation]` *(optional)* | — | Object pose at transfer T. | — | Handle/graspable feature oriented toward receiver. | — |

`[giver]` and `[receiver]` identify robot arms/grippers. Their identity is categorical; exchange geometry belongs in `[exchange]` rather than in those slots.

**Fold —** `Fold [deformable] along [crease] so [moving region] lands at [target region]` (optional `[grasp point]`, `[final orientation]`).

| Slot | P | T | D | O | R |
| --- | --- | --- | --- | --- | --- |
| `[deformable]` | Select garment by initial landmark P. | Select by initial garment frame T if defined. | Select garment offset from landmark. | Select orientation of garment frame relative to table. | Select garment left of/on table. |
| `[crease]` | Two P values define crease endpoints. | T defines crease center and directed line. | Crease offset from seam/hem landmark. | Crease direction relative to garment axis. | Crease between named garment regions. |
| `[moving region]` | Name garment point/patch at P. | Patch pose T if local frame exists. | Region offset from seam/landmark. | Patch orientation relative to garment frame. | Left sleeve/region above crease. |
| `[target region]` | Moving landmark ends at P. | Patch goal pose T if frame exists. | Target offset from chest/shoulder landmark. | Final patch orientation relative to torso. | Sleeve over chest; hem near shoulder. |
| `[grasp point]` *(optional)* | Grasp garment point P. | Gripper contact pose T. | Grasp offset from seam/corner. | Gripper orientation relative to garment edge. | Grasp corner/edge of garment. |
| `[final orientation]` *(optional)* | — | Final patch/garment pose T if defined. | — | Folded edge aligned with shoulder line. | — |

For deformables, a `T` condition is valid only when the specified patch has a reproducible local frame. Whole-garment pose alone does not measure whether a fold is correct. A line can be encoded with two points or a line-centered pose, but verifying the fold still requires garment landmark or shape measurements.

### Boundary rules

- **Pick vs. place:** Pick ends with retained control of a lifted object. Place ends with release and stable support.
- **Place vs. insert:** Use insert when a constrained opening, entry axis, and depth are essential. A bottle dropped into a bin is place; a plug seated in a socket is insert.
- **Push vs. push with tool:** The effective contact body is the robot hand in the first case and a held tool in the second. Tool acquisition is a separate pick.
- **Actuate vs. twist:** Actuate changes a mechanism's joint state, typically with one contact motion; twist specifically requires rotation about an axis and can be evaluated by angular change. A key turn can be tagged both `twist` and `actuate` if it also changes a lock state, but use `twist` as its primary primitive.
- **Touch with tool vs. push with tool:** A strike or tap is scored by a contact event; a sweep is scored by sustained contact plus object displacement.
- **Place vs. fold:** Fold changes shape and landmark relationships within a deformable object. Placing a rigid cup over a block is a place action with a `covers` relation.

## Template instances showing the five modifiers

These examples illustrate how to turn a category into a scoreable instruction. Coordinates are illustrative; actual values need valid scene geometry.

1. **P:** `Strike [xylophone key 3] at [point (0.02, 0.00, 0.01) in key frame] with [mallet tip]`.
2. **T:** `Place [T block] so its final pose equals [pose of gray T pad in world frame]`.
3. **D:** `Push [T block] by contacting [point 0.02 m to the right of its center in block frame] toward [pad]`.
4. **O:** `Insert [key] with its long axis [aligned to slot axis, yaw offset 0° ± 5°]`.
5. **R:** `Place [headphones] [on the stand cradle]` or `place [bottle] [inside the bin]`.

## Benchmark implications for the next step

Report **action success** and **geometry adherence** separately. An object can reach its goal even if the robot ignores a requested contact point. For pick, push, sweep, touch, insert, and handover, record the relevant **interaction event** (first grasp, first effective contact, entry crossing, tool strike, receiver grasp); final state alone cannot verify contact geometry. For place and twist, measure pose at release or after motion settles. For pour, assess both material transfer and the spout/stream geometry while pouring. For fold, assess garment landmark relationships after settling.

An instance record should contain `family`, `object/target/tool` identities, `precondition`, typed `modifier(s)`, `frame`, `reference landmark`, `tolerance`, `event to observe`, and an `outcome predicate`. A useful first benchmark cell varies **one** geometry modifier while holding object identities, task success condition, and difficulty approximately fixed. Include feasible counterfactual values, such as two valid grasp regions or two valid push contact offsets, so geometric adherence cannot be inferred from mere task completion.

## Source anchors and caveats

- [RoboDojo repository](https://github.com/RoboDojo-Benchmark/RoboDojo/tree/726e9aa) and [README](https://github.com/RoboDojo-Benchmark/RoboDojo/blob/726e9aa/README.md) (task code is evaluation oriented).
- [General pickup](https://github.com/RoboDojo-Benchmark/RoboDojo/blob/726e9aa/task/RoboDojo/tasks/general_pickup.py), [push T](https://github.com/RoboDojo-Benchmark/RoboDojo/blob/726e9aa/task/RoboDojo/tasks/push_T.py), [sweep blocks](https://github.com/RoboDojo-Benchmark/RoboDojo/blob/726e9aa/task/RoboDojo/tasks/sweep_blocks.py), [pour liquid](https://github.com/RoboDojo-Benchmark/RoboDojo/blob/726e9aa/task/RoboDojo/tasks/pour_liquid_into_cup.py).
- [Insert key](https://github.com/RoboDojo-Benchmark/RoboDojo/blob/726e9aa/task/RoboDojo/tasks/insert_key.py), [fasten screws](https://github.com/RoboDojo-Benchmark/RoboDojo/blob/726e9aa/task/RoboDojo/tasks/fasten_screws.py), [press by number](https://github.com/RoboDojo-Benchmark/RoboDojo/blob/726e9aa/task/RoboDojo/tasks/press_by_number.py), [play xylophone](https://github.com/RoboDojo-Benchmark/RoboDojo/blob/726e9aa/task/RoboDojo/tasks/play_Xylophone.py).
- [Fold clothes](https://github.com/RoboDojo-Benchmark/RoboDojo/blob/726e9aa/task/RoboDojo/tasks/fold_clothes.py) explicitly checks garment landmarks. [Store laptop and headphones](https://github.com/RoboDojo-Benchmark/RoboDojo/blob/726e9aa/task/RoboDojo/tasks/store_laptop_and_headphones.py) illustrates hanging and articulation.
- Current RoboDojo rewards often verify outcome rather than the entire instructed maneuver. For example, `insert_key` says “then turn it,” but its reward checks insertion depth/alignment rather than a key-turn event. This taxonomy treats instruction verbs and reward code as evidence of candidate primitives, not proof that each primitive already has a standalone success detector.

## Augmentation: nine new action families

The augmented vocabulary has **20 families: the 11 inherited families plus nine additions**. Family names in code below are proposed System 1 API identifiers, not additions to the current `AtomicProgram` schema.

The inherited identifiers are `pick`, `place`, `push`, `push_with_tool`, `pour`, `actuate`, `twist`, `insert`, `touch_with_tool`, `handover`, and `fold`. The added identifiers are `extract`, `scoop`, `stir`, `dispense`, `spread`, `wipe`, `reshape`, `cut`, and `tear`.

| New family / proposed ID | Atomic instruction template | Why the inherited families do not suffice | Observable completion; catalog anchors |
| --- | --- | --- | --- |
| **Extract** / `extract` | `Extract [object] from [retainer] through [exit] to [clearance goal]` | Pick requires lift, while withdrawal may be horizontal and contact-constrained. Insert describes engagement, not disengagement. A negative insertion depth alone does not define release from friction, clips, or neighbors. | Previously retained object crosses the exit, clears the specified engagement, and remains controlled; retainer/neighbors obey disturbance limits. C07; reverse C23/C25; C27. |
| **Scoop** / `scoop` | `Using [tool], scoop [material/object] from [supply] via [collection stroke] to [loaded goal]` | Sweep displaces material along a support; pour empties a source by gravity. Scoop acquires a load onto/into a tool from a bulk supply or underneath an item. | Identified source material/item becomes supported or contained by the held tool, leaves the supply, and remains on the tool at the collection boundary. C29. Deposit is a later action. |
| **Stir** / `stir` | `Stir [materials] in [container] using [tool] along [stirring path] until [mix goal]` | Repeating rigid-object pushes does not specify bulk agitation, material mixing, or continuous immersed tool motion. | Tool actually engages the materials over the prescribed cycles; a declared mixing measure reaches its threshold with bounded spill. C30. |
| **Dispense** / `dispense` | `Dispense [contents] from [dispenser] through [outlet] onto/into [target] by [drive] until [dose goal]` | Controlled outlet delivery by shaking, squeezing, pumping, or triggering has drive-to-flow coupling. Actuate alone detects control motion; pour alone does not establish outlet drive or delivery onto a surface. | Source-attributed contents exit the selected outlet under the selected drive and reach the target in the dose/coverage band, with bounded off-target loss. C31/C32. |
| **Spread** / `spread` | `Spread [material] over [substrate region] using [tool] along [spreading path] to [layer goal]` | Sweep transfers discrete debris; spread redistributes an adhering material into a surface layer. | Tool-material-substrate contact produces the required deposited coverage and, if specified, layer thickness/uniformity, without forbidden substrate damage. C40. |
| **Wipe / scrub** / `wipe` | `Wipe/scrub [surface region] with [tool] along [wiping path] until [clean goal]` | Merely moving a tool or debris does not establish removal of a stain, film, or liquid from the treated surface. | Physical contact with the named region removes the required contamination; contact coverage and residual dirt are measured separately. C41/C42. Scrub is a repeated-stroke mode. |
| **Reshape** / `reshape` | `Reshape [deformable] by moving [material regions] along [manipulation path] to [shape goal]` | Pick/place change support or location; fold creates a specified crease/layer relation. Neither defines unfolding, stretching, opening a soft mouth, changing a rope's curve, or winding it around a support. | Material landmarks/shape satisfy the declared target while required anchoring, tension, crossing order, and non-tearing constraints hold. C43/C46/C47; opening/preparation in C49/C51/C53. |
| **Cut** / `cut` | `Cut [workpiece] along [cut line] with [blade/tool] to [separation goal]` | Contact, pushing, and folding preserve material connectivity. A blade-induced split requires a material topology event. | Blade engagement creates the required disconnected pieces or through-cut along the designated material line, within cut error and collateral-damage limits. C39. |
| **Tear** / `tear` | `Tear [sheet] along [tear line] by pulling [moving region] against [anchored region] to [separation goal]` | Opposed tension breaks continuous material; extracting two already separate components does not describe fracture. | A fracture propagates along the required line, leaving the intended separated sheet/pieces controlled; anchor/roll and off-line damage remain within limits. C55. |

These are deliberately broad families with physically meaningful modes. There are no separate families for *ladle*, *whisk*, *sprinkle*, *pump*, *spray*, *scrub*, *unfold*, *open a soft bag*, or *coil*. Their drive, material, stroke, and outcome slots determine the mode. Cut and tear remain separate because blade-driven fracture and tension-driven fracture require different interaction evidence.

### Illustrative geometric instances

Values below illustrate slot attachment; calibrate them to the actual assets. All positions are metres and angles are radians. Each example still requires its family's physical completion evidence.

| Family | Filled instruction and geometric condition |
| --- | --- |
| Extract | Extract the USB plug from the socket: `[exit]` O aligns the plug axis to the socket's outward axis within 0.05 rad; `[clearance goal]` D puts the plug tip 0.04 m beyond the socket mouth, ±0.005 m. |
| Scoop | Scoop rice with the spoon: `[collection stroke]` P gives ordered entry/undercut/lift points in the supply frame, ±0.005 m; `[loaded goal]` O keeps the spoon bowl normal within 0.10 rad of world up. |
| Stir | Stir the beaker: `[stirring path]` D gives loop points 0.02 m above the annotated bottom and inside the verified interior, ±0.003 m; `[active tip]` R requires immersion throughout each cycle. |
| Dispense | Spray the marked panel: `[outlet]` D sets 0.15 m standoff from the panel frame, ±0.01 m; `[outlet]` O aims along its inward normal within 0.05 rad; `[target footprint]` R restricts deposition to the marked region. |
| Spread | Spread jam over the toast: `[spreading path]` P gives contact stroke endpoints in the toast surface frame; `[active edge]` O aligns the knife edge with the toast's long edge within 0.10 rad; `[layer goal]` R selects the top face. |
| Wipe | Wipe the cup's inner wall: `[wiping path]` T specifies brush-frame samples relative to the live cup frame, with 0.005 m and 0.10 rad tolerances; independent contact and residual-dirt checks establish cleaning. |
| Reshape | Open the bag: `[shape goal]` D separates two named material lip landmarks by 0.12 m along the bag-mouth frame x axis, ±0.01 m; also require measured aperture area and item clearance. |
| Cut | Slice the loaf: `[cut line]` uses two material P landmarks defining the slice plane's intersection with the top surface; `[blade path]` O aligns the blade plane with the annotated cut plane within 0.05 rad. |
| Tear | Tear the paper towel: `[tear line]` uses two material P endpoints on the perforation; `[pull path]` D moves the free-end patch 0.08 m away from the anchored roll frame, while fracture and line deviation are independently checked. |

### New slot-by-modifier matrices

All inherited P/T/D/O/R rules still apply. The following tables enumerate every slot in the new templates plus explicitly listed optional slots. **S** means initial referent selection; **E** means execution/goal geometry. Selection geometry must not become a final-state selector. A dash means the modifier is not natural for that slot, not that the entire action lacks geometric conditions.

**Shared identity rule:** a rigid object's/tool's/retainer's identity slot accepts P/T/D/O/R at stage start: initial point, initial frame, offset from a landmark, orientation relative to a landmark, or spatial relation. A deformable identity uses initial material landmarks, and T/O only if a reproducible initial patch frame is defined. A material population has no single rigid pose. A selected surface/volume is finite and explicitly named; T/O on it require an annotated frame.

**Extract —** `Extract [object] from [retainer] through [exit] to [clearance goal]` (optional `[grasp region]`, `[withdrawal path]`).

| Slot / role | P | T | D | O | R |
| --- | --- | --- | --- | --- | --- |
| `[object]` S | Initial landmark. | Initial frame. | Initial landmark offset. | Initial relative orientation. | Initially in/attached to retainer. |
| `[retainer]` S | Initial landmark. | Initial frame. | Initial landmark offset. | Initial relative orientation. | Holder beside/in assembly. |
| `[exit]` E | Exit-plane crossing point. | Exit frame and outward axis. | Crossing offset from exit center. | Withdrawal axis relative to retainer. | Through named opening/corridor. |
| `[clearance goal]` E | Object feature at clearance point. | Controlled object at clearance pose. | Withdrawal distance from seat/exit. | Object orientation after clearing. | Disengaged/outside retainer, with separation margin. |
| `[grasp region]` E optional | Actual grasp point. | Physical gripper frame plus contact. | Grasp offset from object feature. | Gripper orientation relative to feature. | Grasp exposed end/side. |
| `[withdrawal path]` E optional | Ordered feature points. | Ordered object/gripper poses. | Ordered offsets from corridor landmarks. | Orientation along corridor. | Inside corridor; clear of neighbors. |

Extraction starts with the object retained and a grasp acquired in situ. Do not prepend a successful Pick when the object cannot yet lift. Grasp acquisition can be part of the extractor's control routine; if scene setup includes an actual separate lift, score that as Pick. For C27, one component is the retainer and the other is extracted while the opposing arm stabilizes the retainer. Both components must be controlled or subsequently placed. Extraction of a free, unconfined object is ordinarily Pick instead.

**Scoop —** `Using [tool], scoop [material/object] from [supply] via [collection stroke] to [loaded goal]` (optional `[active surface]`).

| Slot / role | P | T | D | O | R |
| --- | --- | --- | --- | --- | --- |
| `[tool]` S | Initial landmark. | Initial frame. | Initial landmark offset. | Initial relative orientation. | Tool on/beside supply. |
| `[material/object]` S | Initial feature for a discrete item only. | Initial frame for a rigid item only. | Item offset from supply landmark. | Rigid item relative orientation only. | Source subset inside supply/on tray. |
| `[supply]` S | Initial landmark. | Initial frame. | Initial landmark offset. | Initial relative orientation. | Supply on/inside workstation. |
| `[collection stroke]` E | Entry, undercut, and lift points. | Ordered tool poses. | Entry/exit offsets from supply. | Tool inclination relative to material surface. | Enter material/under item, then leave supply. |
| `[loaded goal]` E | Loaded tool at endpoint. | Loaded tool pose, e.g. level ladle. | Tool offset above supply. | Tool orientation relative to gravity frame. | Material/item in/on active tool surface. |
| `[active surface]` E optional | Physical point on scoop edge. | Scoop bowl/edge frame. | Edge offset from handle/tool frame. | Bowl normal relative to supply. | Edge below item/in material at collection. |

Amount loaded, retained fraction, and spill are intrinsic/material parameters. Scoop ends with a retained tool-supported load, not necessarily delivery to the final receiver. A full ladling task uses Scoop → Pour, repeated as needed. For a cookie on a spatula, use Scoop → Place in the tool-supported placement mode described below.

**Stir —** `Stir [materials] in [container] using [tool] along [stirring path] until [mix goal]` (optional `[active tip]`).

| Slot / role | P | T | D | O | R |
| --- | --- | --- | --- | --- | --- |
| `[materials]` S | — | — | — | — | Select source populations in named volume. |
| `[container]` S | Initial landmark. | Initial frame. | Initial landmark offset. | Initial relative orientation. | Container on/beside landmark. |
| `[tool]` S | Initial landmark. | Initial frame. | Initial landmark offset. | Initial relative orientation. | Tool beside/on rack. |
| `[stirring path]` E | Ordered immersed tip points/loop points. | Ordered tool poses. | Path offsets from vessel center/bottom. | Tool axis relative to vessel axis. | Within fluid/material; clear of forbidden walls. |
| `[mix goal]` E | — | — | — | — | — |
| `[active tip]` E optional | Physical tip location during agitation. | Physical tip frame. | Immersion offset from surface/bottom. | Tip direction relative to container. | Tip immersed in contents. |

The mixing metric, observation cells, threshold, cycle count, speed, and spill allowance are intrinsic parameters. A circular path alone is not a successful mixing event. Tool paths may be circular, reciprocating, or otherwise specified; no rotation count can substitute for the declared material metric.

**Dispense —** `Dispense [contents] from [dispenser] through [outlet] onto/into [target] by [drive] until [dose goal]` (optional `[drive contact]`, `[target footprint]`).

| Slot / role | P | T | D | O | R |
| --- | --- | --- | --- | --- | --- |
| `[contents]` S | — | — | — | — | — |
| `[dispenser]` S | Initial landmark. | Initial frame. | Initial landmark offset. | Initial relative orientation. | Dispenser on/next to workstation. |
| `[outlet]` E | Outlet point during flow. | Annotated nozzle/outlet frame. | Standoff offset from target. | Nozzle direction relative to target normal. | Above/facing/inside target opening. |
| `[target]` S | Initial region landmark. | Initial annotated target frame. | Initial offset from landmark. | Initial target-frame orientation. | Surface/interior of named receiver. |
| `[drive]` E | — | — | — | — | — |
| `[dose goal]` E | — | — | — | — | — |
| `[drive contact]` E optional | Squeeze/control contact point. | Physical gripper/control frame plus contact. | Contact offset from trigger/pump/body feature. | Gripper orientation relative to drive axis. | Contact on selected control/deformable patch. |
| `[target footprint]` E optional | Named finite footprint anchored at point. | Annotated target patch frame. | Impact/deposition region offset. | Footprint-frame orientation relative to substrate. | Deposition inside/on specified region. |

`[drive]` is `shake`, `squeeze`, `pump`, or `trigger` with stroke/amplitude, cycle count/frequency, compression or joint travel, and force limits as applicable. `[dose goal]` specifies amount, rate/stopping tolerance, coverage if requested, and off-target loss. The geometry of a region anchored at P does not come from a point alone: supply its finite extent separately. A mechanical-only C32 test can be Actuate, but cannot be reported as material-dispensing success. A full pump/trigger Dispense includes that actuation as its internal drive; do not score the same drive twice unless separately requested.

**Spread —** `Spread [material] over [substrate region] using [tool] along [spreading path] to [layer goal]` (optional `[active edge]`).

| Slot / role | P | T | D | O | R |
| --- | --- | --- | --- | --- | --- |
| `[material]` S | — | — | — | — | Source material on tool/in source region. |
| `[substrate region]` S | Initial region anchor. | Annotated surface frame. | Initial region offset from substrate landmark. | Surface-frame orientation relative to landmark. | Named top/inner surface region. |
| `[tool]` S | Initial landmark. | Initial frame. | Initial landmark offset. | Initial relative orientation. | Tool beside/on rack. |
| `[spreading path]` E | Ordered contact points. | Ordered tool poses. | Stroke offsets from substrate landmarks. | Blade/pad angle relative to surface. | Strokes over/within substrate region. |
| `[layer goal]` E | Layer region anchored at point. | Annotated layer/substrate frame. | Layer footprint offset from substrate. | Layer direction relative to substrate, if meaningful. | Material covers named substrate region. |
| `[active edge]` E optional | Physical edge contact point. | Edge frame plus contact. | Edge offset from tool landmark. | Edge heading relative to substrate. | Edge on substrate, engaging paste. |

Coverage fraction, thickness distribution, material amount, and pressure/force band are intrinsic parameters. P/T/D/O on the layer constrain its annotated footprint, not a fictional rigid-body pose for paste. A single tool stroke is bounded; a large-area task repeats strokes and checks cumulative coverage. Material acquisition can be Scoop or Dispense when that operation is required.

**Wipe / scrub —** `Wipe/scrub [surface region] with [tool] along [wiping path] until [clean goal]` (optional `[active patch]`, `[contaminant]`).

| Slot / role | P | T | D | O | R |
| --- | --- | --- | --- | --- | --- |
| `[surface region]` S | Initial surface anchor. | Annotated surface frame. | Initial region offset. | Initial surface-frame orientation. | Named exterior/interior face. |
| `[tool]` S | Initial material/rigid landmark. | Initial rigid/patch frame if defined. | Initial landmark offset. | Initial relative frame orientation if defined. | Tool beside/on rack. |
| `[wiping path]` E | Ordered surface-contact points. | Ordered physical pad/brush poses. | Stroke offsets from surface landmarks. | Pad normal/heading relative to surface. | Stroke within/on region, including curved inner faces. |
| `[clean goal]` E | Cleaned region anchored at point. | Annotated clean-region surface frame. | Region offset from surface landmark. | Region direction relative to surface, if meaningful. | Required surface region is cleaned. |
| `[active patch]` E optional | Actual pad/brush contact points. | Physical rigid/patch frame plus contact. | Contact offset from tool landmark. | Pad normal relative to surface. | Tool patch in contact with surface. |
| `[contaminant]` S optional | — | — | — | — | Selected dirt population/mask on surface. |

Specify contaminant identity, initial dirty mask, residual threshold, dwell or stroke count, contact force band, and surface damage allowance separately. A dirt-removal mask is distinct from the tool's contact-coverage mask: an arbitrary visited area does not prove cleaning. If the goal is instead discrete crumbs moved into a collector, use Push with tool / sweep.

**Reshape —** `Reshape [deformable] by moving [material regions] along [manipulation path] to [shape goal]` (optional `[anchor regions]`, `[support]`, `[winding axis]`).

| Slot / role | P | T | D | O | R |
| --- | --- | --- | --- | --- | --- |
| `[deformable]` S | Initial material landmark. | Initial patch frame if defined. | Initial landmark offset. | Initial patch-frame relative orientation. | Cloth/rope/bag initially on/in region. |
| `[material regions]` E | Named material points/patches. | Physical local patch frames if defined. | Material region offset from seam/end. | Material tangent relative to landmark. | Corners/ends/opposite lips to manipulate. |
| `[manipulation path]` E | Ordered material/gripper points. | Ordered physical patch/gripper poses. | Ordered offsets from support landmarks. | Patch/tangent orientation along motion. | Through clip; around post; above support. |
| `[shape goal]` E | Target positions for specified material landmarks. | Target local patch frames, not one whole-object pose. | Target offsets from seam/fixture landmarks. | Rope tangents/cloth normals relative to landmarks. | Flat/open/on support/around post with explicit extents. |
| `[anchor regions]` E optional | Named held material points. | Anchored local patch frames if defined. | Anchor offsets from support/fixture. | Anchor tangent relative to fixture. | Endpoint/corner/lip stays held at anchor. |
| `[support]` S optional | Initial support landmark. | Initial support frame. | Initial landmark offset. | Initial relative orientation. | Named table/rail/post/fixture. |
| `[winding axis]` E optional | Point on axis; direction required separately. | Axis-centered directed frame. | Pivot offset from post landmark. | Axis direction relative to post/support. | — |

Modes are `curve_shape`, `tension/open`, `flatten/unfold`, and `wind`. Their goals additionally declare:

- **Curve shape:** material correspondence and target curve; ordered node/curve error and tolerances. A mean nearest-curve distance alone can accept a collapsed cable; check extent and material order.
- **Tension/open:** separation of specific material regions, aperture area/clearance, tension/strain band, and anchoring. Opening a flexible bag is not an articulated Actuate unless a real mechanism is being operated.
- **Flatten/unfold:** projected area relative to known flat material area, landmark layout, residual folds/layer overlap, and strain limits. A prescribed fling may be an internal manipulation path; this is not a rigid-object Throw.
- **Wind:** support axis, signed turn count, pitch if required, material order, winding direction, tension, and retained winding after release. Final end pose alone does not measure turns.

One atomic instance is a bounded manipulation of named material regions, such as one unfolding pull or one winding turn. Repeated regrasping/winding is a program. Shape change must be measured using live material state; initial bounding boxes cannot prove a reshaped outcome. Fold remains the primary family when the requested result is a specified crease and layer arrangement. Drape/hang can use Place when release and support are the interaction; add Reshape only when a separately required shape preparation or deformation cannot be achieved by that placement alone.

**Cut —** `Cut [workpiece] along [cut line] with [blade/tool] to [separation goal]` (optional `[blade path]`, `[support region]`).

| Slot / role | P | T | D | O | R |
| --- | --- | --- | --- | --- | --- |
| `[workpiece]` S | Initial material/rigid landmark. | Initial physical frame if defined. | Initial landmark offset. | Initial relative frame orientation. | Item on/inside support region. |
| `[cut line]` E | Two material endpoints, or ordered material points. | Directed line/plane frame. | Line offset from workpiece landmark. | Cutting direction/plane relative to material. | Across/between named material regions. |
| `[blade/tool]` S | Initial landmark. | Initial frame. | Initial landmark offset. | Initial relative orientation. | Tool beside/on rack. |
| `[separation goal]` E | — | — | — | — | Specified material regions disconnected. |
| `[blade path]` E optional | Ordered blade-contact points. | Ordered physical blade poses. | Blade offsets from cut line. | Blade angle relative to workpiece. | Blade follows/crosses named cut region. |
| `[support region]` E optional | Stabilizing contact points. | Physical holder frame plus contact. | Contact offsets from cut region. | Holder orientation relative to workpiece. | Hold away from cut; support near cut. |

The line needs material coordinates/correspondence, extent, and depth; a T line frame still needs length and, for slicing, a defined plane. `[separation goal]` also declares connectivity, piece count, completion depth, cut error, and collateral-damage allowance. Scissors' joint Actuate can be an internal cutting drive; a fixed punch/press can instead be modeled as device Actuate with a workpiece outcome. A breakable-joint surrogate must be labeled as a surrogate for cutting.

**Tear —** `Tear [sheet] along [tear line] by pulling [moving region] against [anchored region] to [separation goal]` (optional `[pull path]`).

| Slot / role | P | T | D | O | R |
| --- | --- | --- | --- | --- | --- |
| `[sheet]` S | Initial material landmark. | Initial patch frame if defined. | Initial landmark offset. | Initial patch orientation relative to landmark. | Sheet on roll/backing/support. |
| `[tear line]` E | Two material endpoints or ordered material points. | Directed local line frame if defined. | Line offset from perforation/edge. | Line direction relative to material. | Along perforation/across named region. |
| `[moving region]` E | Named material grasp points. | Physical patch/gripper frame. | Grasp offset from edge/line. | Patch/gripper orientation relative to line. | Grasp free sheet end. |
| `[anchored region]` E | Anchored material/roll points. | Physical anchor frame. | Anchor offset from roll/line. | Anchor orientation relative to line. | Opposing region/roll stays held. |
| `[separation goal]` E | — | — | — | — | Named regions disconnected; intended piece retained. |
| `[pull path]` E optional | Ordered moving-region points. | Ordered patch/gripper poses. | Pull displacement relative to anchor. | Pull heading relative to tear-line frame. | Move away from anchor while roll remains restrained. |

Pull force, strain/fracture threshold, piece count, tear-line deviation, and anchor disturbance are intrinsic parameters. Peeling an already detached backing or separating a joined pair is not necessarily Tear: this family requires new fracture of continuous material. If C27's Velcro example is represented as an adhesive joint, use Extract with a peel trajectory and detachment outcome, not Tear unless the strap itself breaks.

## Extensions to inherited families and shared execution slots

The inherited templates/matrices above remain the baseline. These **additive semantic extensions** cover catalog cases without inventing a separate family for every verb:

| Inherited family | Additional mode or condition | Boundary and evidence |
| --- | --- | --- |
| Pick / Place | One object may have two assigned grasp regions/arms; Place may transport and release an object supported by a held tool. Flexible-object placement uses material-region support/coverage goals. | Both grasps must bear load for required bimanual intervals. Tool-supported Place ends when the carrier tool withdraws and the item remains stably supported by the target. Do not pretend the item was directly finger-grasped. Whole-cloth rigid pose does not prove draping or hanging. |
| Push | `slide`, `pivot/topple`, or `roll`, under sustained direct hand contact. | Slide retains surface support; pivot retains the prescribed edge/support during rotation; roll requires rotation coupled to translation and a declared slip tolerance. Score no-grasp history and contact, not just final pose. Intentional unsupported ballistic motion is outside Push. |
| Push with tool / sweep | Signed `push` or `drag/pull` force through a held tool; explicit hook/engagement feature. | C36's hook pulls from the near-facing side. The existing contact-and-displacement family covers it if sustained engagement and support are measured. Its name does not imply all force must point away from the robot. |
| Pour | Bulk rigid items, particles, or liquid; target amount and source-upright endpoint when required. | C08 is Pick(vessel) → Pour(contents) → Place(vessel upright). Ordinary dumping does not create an Empty family. Material lineage, transfer, and loss remain required. |
| Actuate | Linked controls, momentary trigger events, repeated flap joints, zipper-slider track motion. | Preserve latch-before-door dependencies and momentary press events. An articulated carton flap is Actuate; an unhinged sheet crease is Fold. Pulling a zipper slider must change closure state, not merely its world position. |
| Twist | Multi-turn unwrapped signed angle; optional helical axial advance; tool rotation about a contact-defined fulcrum. | Thread progress couples angle to translation/pitch and engagement. C37 is Insert(tool into gap) → Twist(tool about fulcrum) with simultaneous part/body/fulcrum contacts and a lifted/detached-part outcome. A decorative tool rotation without leverage is insufficient. |
| Insert | Male moving part into female receiver, or female moving part over fixed shaft; press/snap-fit; flexible leading end through an aperture. | The slot roles name the moving body and mating geometry explicitly. Check entry, alignment, depth, and attachment/retention when requested. For flexible threading, track the material end and crossing direction; a final endpoint beyond the hole does not prove threading. |
| Handover | Receiver grasp region/orientation may differ from giver's. | C59 hand-to-hand regrasp is Handover with grasp targets. Receiver can hold a different material region when threading, but a catch of a cable end is not automatically a rigid-object Handover of the entire cable. |
| Touch with tool | Minimum impact/impulse and task-specific target effect if requested. | C34 already fits Strike. Contact alone does not prove a driven peg, stamp mark, or cracked walnut. Such outcome predicates are separate from impact evidence. |

### Geometry and time shared by all action instances

Paths and maintained constraints do not introduce a sixth geometric modifier. They attach the existing types to **ordered samples or intervals**. A path must additionally define interpolation/sampling, allowed corridor, motion direction where relevant, and tolerances between samples; visiting endpoints alone cannot prove path adherence. Force, speed, acceleration, joint travel, count, amount, area fraction, dwell, and topology are typed intrinsic/process parameters, not P/T/D/O/R.

| Additional slot | P | T | D | O | R |
| --- | --- | --- | --- | --- | --- |
| `[execution path]` | Ordered named physical points. | Ordered object/tool/gripper/patch poses. | Ordered landmark-relative offsets. | Relative orientations over path. | Stay within corridor/avoid or pass through region. |
| `[held/transport goal]` | Controlled object feature at point. | Controlled object at pose. | Displacement from frozen start/landmark. | Maintained object orientation. | Object held above/in named region. |
| `[maintained hold]` | Held feature remains in point band. | Held physical frame stays in pose band. | Relative offset stays bounded. | Relative orientation stays bounded. | Part remains supported/taut/in contact with named region. |
| `[grasp regions by arm]` | Per-arm physical grasp points. | Per-arm gripper frames plus contact. | Each grasp offset from object/material feature. | Each gripper orientation relative to feature. | Each arm grasps designated side/end/patch. |
| `[aim pose]` | Functional emitter origin at point. | Annotated tool/emitter frame. | Standoff offset from target landmark. | Working axis relative to target frame. | Working ray/cone intersects finite target region with clear line of sight. |

These slots are optional only where meaningful. `[grasp regions by arm]` applies to gripping/holding actions; `[aim pose]` to directional tools; `[held/transport goal]` to actions with retained control. A maintained hold may be a stationary stabilizer or a moving co-supporter. T/O always address an actual oriented frame; force-bearing point contacts are independently observed.

The ray/cone relation in `[aim pose]`, open soft aperture, attachment, routing, coverage, and winding relations are **proposed semantic predicates**. They are not asserted to be implemented by the current R checker. Each needs explicit finite geometry, physical state, frame, and tolerance; some also require non-geometric evidence such as connectivity or tension.

For C33, keep level and retain contents over the **entire loaded lift, transit, and lowering**, rather than checking only the final pose. For C38, keep the working axis aimed and line of sight clear over a continuous dwell interval; contact is forbidden if requested. A pose-only scan/illumination task does not prove scanner readout, heating, drying, or spraying. Add the actual device/material outcome if the instance requires it.

## Composition and coordination contract for System 2

A category is a task schema; an action family is a physical interaction schema. An API endpoint named after each of C01–C60 would conflate the two. Use the 20 action families with their typed slots, plus explicit program operators and continuous constraints.

The expressions below are **design notation**, not loadable `AtomicProgram` JSON:

- `A → B`: B starts after A's specified completion event. Intermediate object state and retained grip pass to B.
- `A ∥ B`: independent actions can run concurrently with explicit resources and dependencies. This is parallel execution, not a new family.
- `ForEach(items, A)` / `Repeat(A, stop)`: expand or repeat bounded actions. Define item selection and the stopping predicate.
- `During(A, hold(B, constraints))`: a named arm maintains B's physical grip/contact and stated geometry throughout A. The hold starts before A's effective contact, has no gaps, and ends after A's completion boundary. It is an execution constraint/operator, not a new family.
- `Maintain(object/tool, constraints, until)`: retain already established control and enforce continuous constraints until a finite event/dwell. This exposes a bounded hold to the executor without treating every hold as a separate taxonomy family.
- `If(precondition, A, B)`: select an explicit branch from observed state. Do not flatten branch choices into an unconditional sequence.

Arm patterns from the catalog map directly: A1 = one assigned arm; A2 = independent parallel item branches; A3 = `During(operation, hold(base/workpiece))`; A4 = synchronized two-arm Pick/Place of **one** object; A5 = Handover; A6 = two-point material manipulation with tension/strain constraints. A4 is not two independent Pick actions on the same object; A6 is not necessarily a handover.

**Setup:** tools may already be held and fixtures already braced at an atomic trial's precondition, as in the inherited taxonomy. In full tasks, acquire tools/objects with Pick when that acquisition includes the required lift; include in-situ grip establishment inside the appropriate action when there is no lift. Handover/regrasp, tool acquisition, material loading, device activation, and return/cleanup are included only when requested or required. They must not be assumed accomplished by an unrelated atomic action.

**Resource rule:** each stage binds its arms, held objects, and controls. A hold consumes its arm(s). If the operating stage and stabilizer exhaust both arms, the scene needs a support/fixture or an explicit grasp plan; a third simultaneous gripper cannot be implied. This matters for opening a bag with two lips while inserting an item, bimanual pouring, and feed/catch/pull cable tasks. State the feasible grasp allocation or flag the instance as requiring a fixture; do not declare an impossible two-arm composition covered by prose alone.

### Complete crosswalk: catalog C01–C60

**Existing** uses only inherited families plus the shared constraints/operators. **New** requires at least one of the nine added families for the catalog's full physical definition. **Pattern** is a reusable program/coordination pattern rather than a family. Names below are verbatim from the fetched catalog; conditional examples are retained where a category has more than one physical realization. Unmentioned cleanup is not implied.

| Catalog ID | Category | Classification | Component actions / composition | Required conditions and boundary |
| --- | --- | --- | --- | --- |
| C01 | Pick and place into / onto a target | Existing | Pick(source) → Place(source, target). | Release and settle; distinguish unconstrained containment from insertion. |
| C02 | Stack / nest | Existing | ForEach(items, Pick → Place(on/in base)). | Stable support/containment and alignment; use Insert only for a constrained mating opening. |
| C03 | Sort by class | Existing | ForEach(items, Pick(item) → Place(item, bin[class(item)])). | Class-based selection and all-item completeness are program rules; A2 allows independent branches in parallel. |
| C04 | Arrange in a pattern (row, grid, facing) | Existing | ForEach(items, Pick → Place(pattern pose)); or Push to pose. | Use final relative P/T/O/R goals for row, grid, facing, or table setting; choose the physical manipulation route explicitly. |
| C05 | Load a slotted rack | Existing | Pick(item) → Insert(item, selected rack slot); broad open holders may use Place. | Named slot, alignment, entry depth, and stable support; orientation alone does not force Insert. |
| C06 | Reorient: upright / flip / rotate in place | Existing | Pick → Place(same region, new orientation); or Push(mode=pivot/roll). | Final O/T and bounded position change; include C59 regrasp when needed. No separate Reorient family. |
| C07 | Extract from a tight place | New | Extract(object, holder/cavity) with an in-situ grip. | Constrained exit and controlled clearance; bound neighbor movement. During extraction, hold neighbors/base if A3 is needed. |
| C08 | Empty / dump a container of rigid items | Existing | Pick(vessel) → Pour(rigid contents, receiver) → Place(vessel upright). | Transferred item fraction, spill, and final upright support. A4 uses coordinated two-arm grasp, not two independent pours. |
| C09 | Push / slide to a goal | Existing | Push(object, contact, goal). | Never-grasped history, sustained hand contact, and surface support; final shaped-object yaw if required. |
| C10 | Pack tight by pushing | Existing | ForEach(selected items, Push(item, flush/packing goal)). | Bounds, gap/flush tolerances, and remaining free area; tight packing is a joint task outcome. |
| C11 | Slide to edge, then grasp | Existing | Push(flat object, overhang goal) → Pick(object, exposed grasp region). | Support persists throughout slide; establish controlled grasp at edge before lift. Do not label the slide as Pick. |
| C12 | Pivot / topple against a support | Existing | Push(object, mode=pivot/topple, new-face goal); optional Pick at end. | Prescribed support edge/fulcrum and rotational history, with no grasp during pivot. Ordinary supported planar sliding is insufficient. |
| C13 | Roll a round object | Existing | Push(round object, mode=roll, goal). | Rotation coupled to translation, bounded slip, support contact, and never grasped; pure sliding fails the roll requirement. |
| C14 | Open / close a revolute door or lid | Existing | Actuate(hinged link, handle/edge, open/closed state). | Follow hinge arc; stationary base or During(Actuate, hold(base)); measure moving-link state and contact. |
| C15 | Open / close a prismatic drawer, rack or slider | Existing | Actuate(slider/drawer, handle/contact, extension state). | Along rail axis, with bounded lateral error; push-to-close may be the contact mode of Actuate. |
| C16 | Press a button / toggle a switch | Existing | Actuate(selected button/switch, control, triggered state). | Latch momentary crossing/press event; a spring-return button need not remain depressed at the endpoint. |
| C17 | Turn a knob or dial to a set point | Existing | Twist(knob, axis, setpoint). | Joint/device setpoint plus signed angular change; repeated turns use regrasp. Push-to-turn knobs add Actuate or a maintained press condition. |
| C18 | Pull / push a lever or handle | Existing | Actuate(lever/handle, control, engaged state). | Directed joint travel, required force, and latched device event if spring-return; brace light base when required. |
| C19 | Operate a latch or lock | Existing | Actuate(latch, unlocked/locked); key variant: Pick(key) → Insert(key) → Twist(key); optionally Actuate(door). | Release latch before door motion; actual lock state is required, not just key orientation. |
| C20 | Open → place inside / take out → close (compound) | Pattern | Actuate(open) → Pick(item) → Place(item, interior) → Actuate(close). Removal: open → Pick/Extract → Place → close. | Maintain spring door open during transfer. Tight removal needs Extract (New); routine loose removal is Pick. Preserve open-transfer-close ordering. |
| C21 | Insert into a matching sleeve (no rotation) | Existing | Pick(insert) → Insert(insert, matching sleeve). | Entry crossing, keyed alignment if relevant, and depth/seat; the no-rotation instance does not add Twist. |
| C22 | Hang a rigid object on a hook, rod or peg | Existing | Pick(item) → Place(item, hook/rod); use Insert for essential constrained threading. | Hook through opening, controlled release, weight supported by hanger, and no lower-surface support; pose alone is insufficient. |
| C23 | Plug a connector into a socket | Existing / New reverse | Pick(plug) → Insert(plug, socket). Unplug: Extract(plug, socket) → Place. | Match key and depth; preserve cable slack/drag limits. Brace device if required. Reverse removal needs disengagement evidence. |
| C24 | Screw / unscrew a threaded part | Existing / New reverse | Fasten: engage thread with Insert → Repeat(Twist, seated). Unfasten: Repeat(Twist(reverse), disengaged) → Extract/clear part → Place. | During turns, hold body; require helical pitch/progress, thread engagement, unwrapped angle, and grip continuity across regrasp. If the thread itself carries the part fully clear, no extra Extract is needed. |
| C25 | Snap / press-fit a cap or lid | Existing / New reverse | Insert(cap/lid, body, mode=press-fit/snap); rim closure may repeat local press/Actuate. Remove with Extract. | Braced body, insertion force/seat, actual clip/friction attachment and retention test. Plain Place is insufficient for snap-fit. |
| C26 | Slide onto a shaft (ring, gear, wheel) | Existing | Pick(ring/gear/wheel) → Insert(moving holed part over shaft). | Moving hole vs fixed male shaft; depth, clearance, and tooth phase/mesh for gears. |
| C27 | Pull apart a joined pair | New | During(Extract(part A, retainer B), hold(B)); then Place parts if requested. | Opposing retained control, disengagement, separation, and final controlled/support state of both parts. Velcro detachment may use a peel withdrawal path without material fracture. |
| C28 | Pour from one container to another | Existing | Pick(source) → Pour(contents, destination) → Maintain(source upright) / Place upright as requested. | Dose, provenance, spill, source-upright endpoint, and continuous spout/opening geometry; hold light receiver if required. |
| C29 | Scoop / ladle with a tool | New | Pick(tool) → Repeat(Scoop(supply → tool) → Pour(tool → receiver), dose goal). For rigid spatula loads, Scoop → Place(tool-supported item). | Supply/material engagement, retained loaded-tool transport, delivery, and spill; hold supply/receiver where needed, with feasible arm assignment. |
| C30 | Stir / mix | New | Pick(tool) → During(Stir(materials, container, path, mix goal), hold(container)). | Immersion/material engagement, cycles, actual mixing measure, and spill. Container cannot be assumed fixed in A3 instances. |
| C31 | Shake-dispense / sprinkle | New | Pick(dispenser) → Dispense(contents, outlet, target, drive=shake). | Outlet pose plus oscillation, dose, coverage and off-target loss. A shake-only demonstration is not sprinkling success. |
| C32 | Squeeze / pump / trigger-dispense | New; Existing mechanism-only | Dispense(contents, outlet, target, drive=squeeze/pump/trigger). Mechanism-only surrogate: Actuate(control). | Physical drive-to-flow coupling and delivered amount; target/substrate hold and dispenser brace consume explicit resources. |
| C33 | Carry a filled or loaded container level | Existing | Pick(carrier) → Place(carrier, destination), with continuous level/retention constraints through lift, transit, and lowering. | Tilt and acceleration bounds over whole loaded motion; all contents retained or bounded spill. A4 adds coordinated two-arm carrying. |
| C34 | Strike with a tool (hammer, stamp, mallet) | Existing | Pick(tool) → Touch with tool(target, contact, tool); repeat strikes if requested. | Correct active tool part, impact speed/impulse, and actual target effect (peg depth, stamp, note, fracture); brace light workpiece as needed. |
| C35 | Sweep into a collector | Existing | Pick(sweep tool) → During(Push with tool / sweep(debris, collector), hold(collector)). | Tool contacts debris, collector lip stays positioned, required debris fraction reaches collector; A1 may use a fixed receiver. |
| C36 | Drag with a hook to bring something into reach | Existing | Pick(hook/tool) → Push with tool / sweep(mode=drag/pull, object, reachable goal); optional Pick(object). | Effective hook engagement and sustained tool-induced displacement; initial object must truly be outside bare-hand reach. |
| C37 | Pry / lever open with a tool | Existing | Pick(pry tool) → Insert(tool, gap) → During(Twist(tool, fulcrum axis, leverage orientation), hold(body)). | Simultaneous tool-part and tool-fulcrum contact, leverage motion, and lifted/detached-part outcome. Catch/place removed part if the full instance requires control after separation. |
| C38 | Aim a tool at a target (scan, spray, dry) | Existing | Pick(tool) → Maintain(tool, aim pose + noncontact, until continuous dwell/device event). Spray adds Dispense; target may be held/turned by the other arm. | Working axis intersects finite target with allowed standoff and line of sight for required dwell. Physical drying/spraying/readout needs its actual outcome; catalog pose-only proxy is labeled separately. |
| C39 | Cut / slice | New | Pick(blade/tool) → During(Cut(workpiece, cut line, separation goal), hold(workpiece)). | Blade-induced connectivity change, cut extent/pieces, restraint, and collateral damage. Fixed cutter variant may use Actuate(device) with the same physical outcome. |
| C40 | Spread a paste on a surface | New | Load tool if needed via Scoop/Dispense → During(Spread(material, substrate region, tool, layer goal), hold(substrate)). | Deposited material coverage/thickness and contact force; substrate restraint. Material acquisition is not automatically accomplished by Spread. |
| C41 | Wipe / mop a flat surface | New | Pick(cleaning tool) → Wipe(surface region, path, clean goal); Repeat if needed. | Actual contaminant removal, sustained force band, visited coverage, and residual dirt; discrete-debris collection can instead be Sweep. |
| C42 | Scrub inside a held container | New | Pick(brush/sponge) → During(Repeat(Wipe(inner region, mode=scrub), clean goal), hold/reorient(container)). | Live inner-surface frames, access to every required face, brush contact and cleaning; container rotation is coordinated with wiping. |
| C43 | Straighten / shape a rope or cable | New | Reshape(rope/cable, selected material regions, target curve). | Material order, curve/extent error and support; A6 uses two-end tension, with strain limits. |
| C44 | Route a cable through clips | New + Existing insertion | ForEach(ordered clips, Insert(selected cable section, clip) → Reshape(span, routed goal)), with maintained cable tension. | Ordered route/crossing and retention in prior clips; support/fixture or feasible two-arm grip allocation. Open channels may use Place of sections before reshaping. |
| C45 | Thread through a hole or ring | New + Existing insertion | Insert(flexible leading end, hole) → acquire receiving-end grip → Reshape(cable, pull-through path, routed goal). | Track material through-hole crossing; feed/catch/pull sequence, opposite-side grip, and maintained routing/tension. Receiving grip acquisition is not an extra rigid-object Handover by default. |
| C46 | Coil / wrap around a post | New | Repeat(Reshape(rope, mode=wind, around post), signed turn-count goal). | Winding axis, material order, pitch/tension, and retained turns; hold post/spool if required. Rigid Twist of an end is insufficient. |
| C47 | Flatten / unfold cloth | New | Reshape(cloth, mode=flatten/unfold, material-corner path, flat goal); Place flat if final released support is requested. | Two-point grip, tension/strain, projected area and landmark layout; bounded fling path when prescribed. Area alone must not reward stretch. |
| C48 | Fold a garment or cloth | Existing | ForEach(ordered creases, Fold(cloth, crease, moving region, target region)). | Prescribed fold order, material landmarks, layer overlap/order and final shape. Crumpled-start setup adds Reshape(flatten) if needed. |
| C49 | Hang a garment on a hanger / hook / rail | Existing; New preparation if needed | Pick/position garment → Insert(hanger through neck, if required) → Place(garment on hanger/bar) → Place(hanger on rail if requested). Add Reshape to open/arrange material regions when necessary. | Garment shoulder/bar support, live neck aperture, layer arrangement, retained hanging, and feasible two-arm allocation. Hanger and garment placement are separate events. |
| C50 | Drape / cover an object with cloth | Existing; New preparation if needed | Pick(cloth/material regions) → Place(cloth over target); optionally Reshape to unfold/prepare. | Released drape with material coverage of finite target from declared viewpoint, support and settling; one whole-cloth pose is insufficient. |
| C51 | Open a bag and put items inside | New + Existing placement | Reshape(bag mouth, open goal) → During(ForEach(items, Pick → Place/Insert into bag), hold(mouth open)). | Maintain aperture clearance, actual bag containment and final upright bag. If two arms must hold the mouth, use a fixture/revised allocation before insertion. |
| C52 | Zip / unzip | Existing; conditional New material alignment | During(Actuate(zipper, pull, track endpoint), hold fabric taut). A press-seal bag without a slider uses Insert(mating profiles) along the seam, with Reshape alignment if needed. | Slider follows live track; verify opened/closed teeth or seal, not just pull endpoint. Catalog zip-lock example is not necessarily a zipper-slider mechanism. |
| C53 | Stuff into a fabric sleeve | New preparation + Existing insertion | Reshape(sleeve opening, open goal) → During(Insert(filler, sleeve opening, depth goal), hold sleeve open). | Live soft aperture and depth landmarks; material strain/containment and controlled filler deformation. Already-fixtured-open sleeve may omit Reshape. |
| C54 | Fold a carton / close flaps | Existing | ForEach(required flap order, Actuate(flap, closed)); During(next flap, hold prior flap). Use Fold for a genuinely deforming unhinged carton crease. | Order, springback restraint, lock/closure outcome. Articulated-joint proxy and true material folding are distinct instances. |
| C55 | Tear off a sheet (paper towel, tape) | New | During(Tear(sheet, tear line, moving region, anchored region, separation goal), hold roll/anchor). | New material fracture, intended piece retained, off-line damage bounded, and roll prevented from simply unwinding. |
| C56 | Two-arm lift and place a large object | Existing | Pick(one object, two assigned grasp regions/arms) → Place(object, support), synchronized. | Both arms carry the same object during required interval; coordinated force/load/pose and stable released support. |
| C57 | Handover between arms | Existing | Pick(object, giver) → Handover(object, giver, receiver, exchange) → Place(object, receiver-side target). | Receiver establishes grip before giver release; object remains supported throughout. Loaded cup adds spill/tilt constraints. |
| C58 | Hold-and-operate (general pattern) | Pattern | During(operating action/program, hold(base/workpiece, constraints)). | Choose operating family from actual physics; continuous stabilizer grip/contact and bounded motion. No additional Hold-and-operate family. |
| C59 | Regrasp to change the grasp side | Pattern | Handover(object, new receiver grasp); or Place(object, support/new pose) → Pick(object, new grasp). | Final grasp region/orientation, not merely object pose; hand-to-hand route preserves uninterrupted support, tabletop route permits release. |
| C60 | Hold a part in place for a fixed tool (stapler, press, scanner) | Pattern | Position and Maintain(workpiece, device working pose) during Actuate(device); then Place if requested. Scale: Place → settle/read event. Fixed scanner: maintain workpiece in beam → read event. | Workpiece stays positioned during operation; verify stapled/punched/clamped/weighed/scanned outcome. Device measurement/computation is an external scene event, not a robot action family. |

## Worked compositions and completion boundaries

1. **Pour soup with a ladle (C29):** start with the ladle held and soup source accessible. Scoop ends when source soup is retained in the ladle and lifted clear. Maintain the loaded tool level during transfer. Pour ends when the specified ladle contents enter the bowl; repeat until the cumulative dose is reached. Bracing the source during scoop and the receiver during pour may use different holds at different times. Ladle pose alone does not establish collection or delivery.
2. **Unscrew a bottle cap (C24):** establish an in-situ cap grip and base hold. Twist tracks unwrapped cap rotation and pitch-coupled axial progress; regrasp as needed while the base hold persists. At thread disengagement, Extract is required only if a distinct constrained withdrawal remains. Place ends with the cap released and supported. Holding the bottle is continuous coordination, not a separately sequenced operation after twisting.
3. **Thread a cord through a ring (C45):** feed the identified material end with Insert and verify the actual hole crossing. The receiving arm acquires that end on the far side; the feeding arm releases or becomes an anchor according to the feasible grasp plan. Reshape pulls the cord through while preserving crossing order and appropriate tension. Two different cord patches held simultaneously do not imply a rigid-object handover event.
4. **Put groceries in a soft bag (C51):** Reshape separates the bag lips to establish an aperture. Maintain that aperture while Pick → Place/Insert transfers each item. If both arms must continuously hold the lips, a support/fixture or revised grasp allocation is required for item transfer. Completion includes containment in the current bag geometry and the requested upright bag state, not item centers inside its initial bounding box.
5. **Scan a box with a handheld scanner (C38):** Pick(scanner), position its functional frame, then Maintain the working ray within the barcode region for the requested dwell. The other arm may hold/turn the box. This is inherited Pick plus geometric and temporal constraints; no Scan family is added. A scan-read outcome, if required, is a separate device event. Spraying uses the same aim constraint on Dispense.

## Proposed action-instance contract

A System 2 request should provide these fields using whichever concrete API encoding is adopted:

| Field | Required meaning |
| --- | --- |
| `family`, `mode` | One of the 20 families and any declared physical mode; no implicit task-category-to-family substitution. |
| `roles` | Resolved object/tool/material/surface/control identities, material subsets, moving part, retainer/support, and arm assignments. |
| `precondition` | Initial holding, engagement, source material, open/closed state, support, and reachable/compatible asset geometry; distinguish scene setup from actions. |
| `selection_conditions` | P/T/D/O/R on the initial referents, evaluated against a declared start snapshot. |
| `execution_conditions` | Slot-specific point/frame/path goals, typed modifiers, reference landmarks, finite region definitions, units, separate position/angular tolerances, and observation events/intervals. |
| `intrinsic_parameters` | Amount/count, joint travel, unwrapped angle/pitch, force/speed/acceleration, dwell/cycles, material metric, strain, topology, and damage limits as applicable. |
| `maintained_constraints` | Continuous holds, load sharing, level/tension/support, line of sight, no-grasp/no-contact history, retained routing, and spill limits; specify when each begins/ends. |
| `completion` | Physical interaction evidence plus outcome predicates and settled/dwell interval; retain action success, geometry adherence, and event coverage separately. |
| `control_flow` | Stage dependencies, repeats/choices, resources, finite stop/timeouts, and branch outcome. A failed/unobserved prerequisite blocks dependent stages. |

For multiple samples or cumulative material goals, record the time interval and aggregation explicitly. Incomplete sensing is `unobserved`, not a successful inferred action. Force-bearing contacts, material provenance, active tool frames, topology change, device state, and deforming landmarks require appropriate synchronized measurements. Benchmarks should continue reporting native task success separately from recognized action success and geometric adherence.

## Implementation implications and open boundaries

This document establishes a proposed vocabulary and a source-linked decomposition for every catalog entry. It does not modify `spec.py`, `task_catalog.json`, generated task/segmentation plans, or the original conditioning audit. The current audit generator reads `TAXONOMY.md` and has explicit family/slot inventories; this proposal is not silently covered by that audit. When adopting it, update and review every newly applicable family/slot/factor cell, including the inherited-family extensions, before regenerating those inventories.

Prioritize recognition of withdrawal/attachment, load acquisition on tools, driven discharge, mixing and surface state, live material geometry, and cut/tear connectivity. Calibrate actual tool/part/clip/thread/zipper geometry and feasible arm allocations. Contact-qualified pivot/roll/drag, helical Twist, press-fit retention, fulcrum leverage, directional dwell, and tool-supported/flexible Place also require new or extended evidence; conceptual reuse of a family does not imply its existing recognizer already supports the mode.

The inherited [action audit](ACTION_AUDIT.md) separately flags RoboDojo's bottle-throwing instruction. **Throw is not added here because none of C01–C60 requires a rigid-object throw.** It remains outside these families: release velocity and contact-free ballistic flight cannot be relabeled Place. Knot tying is likewise explicitly excluded by the external catalog's C46 note; wind/route coverage is not a claim of knot-topology support. These are distinct future extensions if brought into scope.
