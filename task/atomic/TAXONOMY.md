# RoboDojo atomic action taxonomy (draft v1)

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
- **Push vs. push with tool:** The effective contact body is the robot hand in the first case and a held tool in the second. A lifted-tool acquisition is a separate pick. A supported tool may be grasped in place; its sustained force-bearing hold is checked within the tool action without requiring a prior lift.
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
