# System 1 and System 2 interaction slot reference

This is the **action-taxonomy and geometric-conditioning contribution** to the team's interaction template. It supplies options already described in [TAXONOMY.md](TAXONOMY.md) and [TAXONOMY_AUGMENTED.md](TAXONOMY_AUGMENTED.md). Slots outside that contribution remain open for the team; partially covered slots contain only the taxonomy-derived portion.

The augmented taxonomy contains 20 proposed action families. Referencing that vocabulary here does not establish robot/runtime support or settle the rest of the System 1 / System 2 interface. This reference adds no new capability schema, observation schema, controller policy, completion protocol, or recovery policy.

## Team interaction template

> The robot has [embodiment]. Currently, [current state]. Given [relevant context], perform [local task] on [grounded entities], using [effector-role assignments] and making contact according to [contact specification], to achieve [local effect].
> Follow [motion constraints] and [interaction constraints]. Coordinate the effectors through [coordination constraints], avoid [forbidden effects], and maintain [preserved conditions].
> Proceed according to [conditional transitions], finish when [completion criteria], and respond to interruptions or unsuccessful execution according to [interruption and recovery rules].

## Contribution by template slot

**Options provided** means a vocabulary is available from the taxonomy, not a complete API field definition. **Partial** means only the listed action-specific content is supplied. **Open** means this contribution supplies no options or policy for that slot.

| Template slot | Coverage here | Taxonomy-derived content |
| --- | --- | --- |
| `[embodiment]` | Open | — |
| `[current state]` | Open | — |
| `[relevant context]` | Open | — |
| `[local task]` | Options provided | The 20 action families, their instruction templates and physical modes, and compositions already described in the augmented taxonomy. |
| `[grounded entities]` | Options provided | The object/tool/target/material/feature roles in each action template, with applicable initial geometric selection. Grounding machinery remains outside this contribution. |
| `[effector-role assignments]` | Partial | Giver/receiver, operating/stabilizing arms, joint grasp, and material anchor/tension roles already used by the taxonomy's arm patterns. |
| `[contact specification]` | Partial | Action-specific contact/grasp/tool features, associated physical events, and applicable P/T/D/O/R conditions. |
| `[local effect]` | Options provided | Family-specific observable success events, target states, and geometric/material outcomes already described in the taxonomy. |
| `[motion constraints]` | Partial | Approach, contact/entry, endpoint, alignment, axis/crease, and path geometry in existing slot matrices. |
| `[interaction constraints]` | Partial | Family-specific engagement and intrinsic/material parameters explicitly named in the taxonomy; no general controller policy. |
| `[coordination constraints]` | Partial | A1–A6 arm patterns and the action composition/maintained-hold notation already described in the augmented taxonomy. |
| `[forbidden effects]` | Open | — |
| `[preserved conditions]` | Open | — |
| `[conditional transitions]` | Open | — |
| `[completion criteria]` | Partial | The action family's observable success event and specified goal measurements; the overall command-completion protocol remains open. |
| `[interruption and recovery rules]` | Open | — |

The seven Open slots are retained as placeholders for collaborators. Conditions inherent in an action—such as retained grasp during Pick or support during Push—remain part of that action's description. They do not define a general vocabulary or policy for the Open slots.

## Local task, grounded roles, contact, and local effect

Select a family and fill its instruction slots. The table summarizes existing taxonomy content; descriptive modes are not new API enums. The first 11 families come from the original taxonomy, with additional modes/conditions in the augmented taxonomy; the last nine are its added families.

Sources: [original templates and slot matrices](TAXONOMY.md#templates-and-applicable-slots), [added families](TAXONOMY_AUGMENTED.md#augmentation-nine-new-action-families), [new slot matrices](TAXONOMY_AUGMENTED.md#new-slot-by-modifier-matrices), and [extensions to inherited families](TAXONOMY_AUGMENTED.md#extensions-to-inherited-families-and-shared-execution-slots).

| Family ID | Local task options / instruction skeleton | Grounded roles | Contact pattern | Local effect options |
| --- | --- | --- | --- | --- |
| `pick` | Pick object at grasp region; one-arm or coordinated bimanual lift. | Object/material region, grasp region(s), lift landmark. | Secure effector-object grasp; retained load during lift. | Controlled grasp plus required held lift/pose; terminal grip retained. |
| `place` | Place object on/in/at target; stack, nest, hang, cover; tool-supported or flexible-object placement where specified. | Object, target support/volume, object goal, release feature. | Initial retained control, target support, then controlled release/withdrawal of tool support. | Released, supported/contained/hanging/covering object at goal, settled for required interval. |
| `push` | Push object to goal; slide, supported pivot/topple, or roll. | Object, hand contact region, goal, support/pivot. | Sustained direct effector contact plus task-specific support; no grasp if required. | Supported displacement/rotation to goal via the requested mode, with no-grasp history. |
| `push_with_tool` | Sweep/push/drag selected objects with tool to collector or goal. | Tool and active feature, objects/debris, start contact, support, collector/goal. | Effector-tool grasp; tool-object engagement during displacement. | Objects moved to goal/collector via tool contact; required fraction collected. |
| `pour` | Pour contents from source into destination; rigid-item dump, granular or liquid transfer. | Material cohort, source, destination, spout, opening. | Source held/tilted; optional receiver brace; material exits source and enters target. | Required source-attributed quantity transferred, with residue/spill limits and requested source terminal state. |
| `actuate` | Press/toggle, pull/push lever, open/close hinge/slider, release latch, move zipper or articulated flap. | Mechanism, control/link, contact, desired state. | Contact-coupled control/joint motion; optional mechanism stabilization. | Joint/device state transition, trigger event/cycle, or coupled lock/closure change. |
| `twist` | Turn knob/key/part about axis; threaded turns; tool leverage about fulcrum. | Part/tool, axis/pivot, contact, orientation/joint/thread target. | Grasp/contact and constrained axis/engagement; braced base or fulcrum as needed. | Signed unwrapped angular progress and orientation/setpoint; thread/lock/leverage effect when requested. |
| `insert` | Insert via opening; keyed plug, sleeve, press/snap-fit, hole-over-shaft, flexible leading-end entry. | Moving object/section, receptacle, opening, tip/alignment, seat/depth landmark. | Held/aligned moving part engages mating guide/receiver surfaces; optional receiver brace. | Actual entry crossing then specified depth/seat/attachment/routing segment, with controlled terminal state. |
| `touch_with_tool` | Touch/tap/strike target using active tool feature. | Tool, tip/head/edge, target, contact region. | Held tool makes a new target encounter; impact if requested. | Specified contact/impact event plus target effect, if required. |
| `handover` | Transfer held object from giver to receiver at exchange. | Object, giver/receiver, both grasp regions, exchange frame. | Giver hold → stable overlap → giver release → receiver-only hold. | Control transferred without unsupported drop; receiver grasps specified region/orientation. |
| `fold` | Fold deformable along crease so moving region lands on target region. | Deformable, material crease, moving/fixed regions, grasp regions, targets. | Material-region grasp and bending across crease; stabilization where required. | Intended crease, material landmark/layer alignment and overlap in folded state. |
| `extract` | Withdraw retained object through exit to clearance; unplug, tight removal, joined-pair separation. | Object, retainer, exit/corridor, grasp region, clearance goal. | In-situ grasp and constrained withdrawal; retainer/neighbors stabilized as required. | Previously retained object disengaged and cleared while controlled; neighbors within disturbance limits. |
| `scoop` | Collect material/item from supply onto/into tool via collection stroke. | Tool and active surface, material/item, supply, stroke, loaded goal. | Tool engages supply material or undercuts item, then supports a retained load. | Source-attributed load on/in tool and clear of supply, within amount/spill bounds. Deposit is a later action. |
| `stir` | Stir/whisk/mix materials using immersed tool until mix goal. | Material populations, container, tool/tip, path. | Immersed tool-material engagement over cycles; container stabilization. | Declared mixing measure reaches threshold with bounded spill. |
| `dispense` | Deliver contents through outlet; shake, squeeze, pump, trigger. | Dispenser, contents, outlet, target footprint, drive control/patch. | Grasp/drive contact or shaker motion; drive-coupled outlet flow and target deposition. | Target dose/coverage within band, source provenance, bounded off-target loss. |
| `spread` | Spread material over substrate to layer goal. | Material, substrate region, tool/edge, spreading path. | Tool-material-substrate engagement over spreading strokes. | Required deposited layer coverage/thickness/uniformity; bounded substrate disturbance/damage. |
| `wipe` | Wipe/mop/scrub selected surface region to clean goal. | Surface/dirt region, cleaning tool/patch, contaminant, path. | Sustained force-bearing tool-surface contact; repeated strokes for scrub. | Contaminant actually removed to residual threshold; visited area alone is insufficient. |
| `reshape` | Change material layout: curve-shape, tension/open, flatten/unfold, wind. | Deformable, material regions/anchors, support, path, shape/winding goal. | One/two-point material grasp, anchor/support interaction, prescribed tension/manipulation. | Material curve/layout, aperture, flatness, or retained winding target within strain/connectivity limits. |
| `cut` | Cut/slice with blade along material line/plane. | Workpiece, blade/active edge, cut line/plane, support region. | Blade-induced material engagement and separation, workpiece stabilization. | Required new connectivity change/pieces/through-cut along intended line, within damage limits. |
| `tear` | Pull sheet along tear line against anchored region. | Sheet, material line, moving/anchored regions, pull path. | Opposed material tension and fracture propagation; roll/anchor restrained. | Intended new material separation, retained piece, bounded off-line damage. |

A category that requires several interactions is composed from these families. Existing examples include sorting = repeated Pick → Place(class bin), ladling = Scoop → Pour, and regrasping = Handover or Place → Pick. Tool acquisition is a separate Pick when it includes the required lift; an already held tool is an action precondition. See the [60-category crosswalk](TAXONOMY_AUGMENTED.md#complete-crosswalk-catalog-c01c60).

### Grounded entity options

Grounded entities fill the action's identity and feature slots. The taxonomy supplies these roles, rather than a general scene-grounding data model:

| Role group | Options already used in action templates |
| --- | --- |
| Manipulated entity | Object, part, deformable, moving material region, selected object set. |
| Instrument | Tool, active tip/head/edge/patch, source vessel, dispenser/outlet. |
| Target/retainer | Receptacle, opening, support surface, target region, collector, retainer, shaft/hook, substrate. |
| Material | Contents, supply material, materials to mix, paste, contaminant, source subset. |
| Functional/material feature | Grasp/contact region, entry tip, pivot/axis, crease, seam/corner, rope end, bag lip, cut/tear line, anchor region. |
| Goal | Lift/object goal, placement/release point, insertion depth, clearance, loaded-tool goal, material/shape/coverage goal. |

Applicable P/T/D/O/R conditions can select an initial referent, such as “the cup left of the bowl.” Execution geometry constrains an interaction or goal, such as “grasp below the handle center.” Preserve this distinction. Material identities do not have one rigid-body pose; deformable T/O uses a defined local material frame.

## Contact specification and geometric conditioning

Use the family's contact-related slots and their modifier applicability. A contact point has no orientation: P/D/R can constrain actual contact locations; T/O must refer to a physical gripper/tool/part/patch frame with independent contact evidence.

| Contact content | Taxonomy options | Source |
| --- | --- | --- |
| Grasp location/frame | `[grasp region]`, `[grasp point]`, per-arm grasp regions. | Pick, Fold, Extract; augmented shared grasp slots. |
| Direct contact and approach | `[contact]`, `[hand approach]`, `[control/contact]`, `[approach]`. | Push, Actuate, Twist. |
| Tool feature and encounter | `[tool tip]`, `[active surface/edge/patch]`, `[start contact]`, `[drive contact]`. | Tool push/touch, Scoop, Spread, Wipe, Dispense. |
| Constrained entry/withdrawal | `[opening]`, `[alignment]`, `[exit]`, `[withdrawal path]`. | Insert, Extract. |
| Transfer | Giver/receiver grasp and `[exchange]`. | Handover. |
| Material engagement | Immersed tip, tool-supported load, material grasp/anchor, blade/cut region. | Stir, Scoop, Reshape, Fold, Cut, Tear. |

The action specifies the relevant physical event: grasp/lift, effective contact/stroke, strike, entry crossing, withdrawal/disengagement, material transfer, receiver grasp/giver release, or release/settling. A final geometric match alone does not prove that contact or interaction occurred.

### Five geometric modifier options

| Modifier | Value and interpretation | Example |
| --- | --- | --- |
| **P** | Point in a named frame, with position tolerance. | Strike at a point on a target surface. |
| **T** | SE(3) pose of an actual oriented frame, with separate position/angular tolerances. | Match the plug entry pose to the socket opening. |
| **D** | Offset from a named landmark, expressed in its frame; specify reference time for initial displacement. | Grasp 0.02 m below a handle landmark; lift relative to the initial pose. |
| **O** | Orientation relative to a named orientation landmark; respect task-relevant symmetry. | Align a key axis to its slot axis. |
| **R** | Spatial relation with explicit target/landmark, reference frame where relevant, finite geometry, and tolerance. | Place inside a bin, supported on a tray, or behind a named object. |

These are the five existing modifier types. Their applicability is determined by the family slot matrix, rather than assumed for every slot. Two points can define a line/segment; ordered points/poses/offsets can describe a path. A point alone does not define an axis, line, or finite region. Spatial relations such as support, containment, coverage, and aiming retain the geometric/physical meanings and implementation caveats in the taxonomy.

## Motion constraints supplied by the taxonomy

This contribution covers motion **geometry** and action-specific paths. It does not add a controller vocabulary, default limits, or motion-selection policy.

| Motion content | Options from existing slots |
| --- | --- |
| Approach | Precontact point/pose, offset, relative heading; named hand/tool approach. |
| Contact/entry geometry | Contact location, opening/entry pose, alignment, approach/withdrawal axis. |
| Goal geometry | Final point/pose, relative displacement/orientation, spatial relation, release or clearance goal. |
| Rotation/crease geometry | Pivot point plus axis direction; relative final orientation; crease endpoints/directed line. |
| Ordered tool/material path | Sweep segment, scoop collection stroke, stirring loop, spreading/wiping stroke, material manipulation, blade/pull/withdrawal path. |
| Maintained geometry | Orientation of a loaded vessel/tool, held/transport pose, maintained contact/anchor location, aim pose. |

For paths, use the existing modifiers on ordered samples or intervals. Specify the relevant physical feature, reference landmark/frame, tolerances, and observation event/interval. Path adherence requires trajectory evidence; endpoint agreement is insufficient. Source: [shared geometry and execution slots](TAXONOMY_AUGMENTED.md#geometry-and-time-shared-by-all-action-instances).

## Interaction parameters already named by the taxonomy

The taxonomy names certain non-geometric parameters alongside each family. They can contribute to `[interaction constraints]`, but their controller realization and general interaction policy remain open. No numerical defaults or compliance/control-law options are supplied here.

| Families | Existing interaction/material parameters |
| --- | --- |
| Pick, Place, Push, tool push/touch, Handover | Required grasp/support/contact/release/transfer sequence; sustained vs strike contact; retained control and action-specific support. |
| Actuate | Joint endpoint/travel or trigger/cycle state. |
| Twist | Signed angle, multi-turn progress, axis engagement, helical advance/pitch where applicable. |
| Insert, Extract | Alignment, entry/exit, fit/depth/clearance, engagement or disengagement; attachment/retention where requested. |
| Pour, Scoop | Material identity and amount/count, retained/transferred fraction, residue and spill. |
| Stir | Mixing metric/threshold, cycle count, speed and spill allowance. |
| Dispense | Shake/squeeze/pump/trigger drive; stroke/amplitude, frequency/cycles, compression or joint travel, force limits, dose/rate/coverage and off-target loss. |
| Spread, Wipe | Coverage, layer thickness/uniformity or residual dirt, pressure/contact-force band, material amount, stroke/dwell parameters, damage allowance. |
| Fold, Reshape | Material landmark/layer/shape goals; anchoring, tension/strain, aperture/extent, winding direction/turns/pitch where applicable. |
| Cut, Tear | Material connectivity/piece count, cut/tear line and depth/deviation, designated separation and damage allowance; pull force/strain for Tear. |

These entries summarize the family definitions and accompanying notes in [the augmented slot matrices](TAXONOMY_AUGMENTED.md#new-slot-by-modifier-matrices). Intrinsic parameters such as amount, angle, force, count, or strain are not additional P/T/D/O/R modifiers.

## Effector assignments and coordination already represented

The taxonomy's arm patterns provide the following partial contribution to `[effector-role assignments]` and `[coordination constraints]`. They do not define the robot embodiment or a general scheduling protocol.

| Pattern | Effector assignment | Coordination meaning |
| --- | --- | --- |
| A1 single arm | One operating arm. | One action using the assigned effector. |
| A2 parallel | Separate arms act on separate objects. | Independent item/action branches can run concurrently. |
| A3 hold-and-operate | Operating arm and stabilizing arm. | Maintain the base/workpiece/receiver hold during the operating action. |
| A4 joint grasp | Both arms grasp designated regions of one object. | Coordinated lift/carry/place of the same load. |
| A5 handover | Named giver and receiver with their grasp regions. | Receiver establishes control before giver release, followed by receiver-only hold. |
| A6 material tension | Effectors act on named material regions, with anchor/moving roles. | Two-point material manipulation with the specified tension/strain/shape conditions. |

Existing composition notation includes `A → B`, `A ∥ B`, `ForEach(items, A)`, `Repeat(A, stop)`, `During(A, hold(B, constraints))`, and `Maintain(object/tool, constraints, until)`. These are design notation from the augmented taxonomy, not additional families or runnable API syntax. This reference does not specify the separate `[conditional transitions]` slot.

A maintained hold occupies its effector. A composition cannot assume a third simultaneous gripper when both arms are committed; the augmented taxonomy calls for a fixture/support or feasible grasp allocation in such cases. Source: [composition and coordination](TAXONOMY_AUGMENTED.md#composition-and-coordination-contract-for-system-2).

## Action-specific completion contribution

For `[completion criteria]`, this contribution supplies only the family success events and goal measurements already listed in the action table and taxonomy. It does not prescribe the command-level completion logic, returned statuses, timeout, or interruption handling.

Examples of existing success semantics:

| Action | Taxonomy-derived success event |
| --- | --- |
| Pick | Stable grasp and required lift, retaining control. |
| Place | Release and stable support/containment at the target. |
| Insert | Pass the opening and reach the specified depth while aligned. |
| Actuate | Required joint/state/trigger threshold crossed. |
| Twist | Required rotation about the specified axis; angular progress where specified. |
| Handover | Receiver gains stable grasp before giver releases; receiver retains control. |
| Pour | Required source contents enter the destination. |
| Fold | Named material landmarks/layers reach the intended folded relationship. |
| Added families | Their observable completion events and material/shape outcomes in the 20-family table above. |

Keep recognized action success and geometric adherence distinct, as the taxonomy specifies. Whether and how the larger System 1 / System 2 command combines them is left for the team's completion-criteria work.

## Example using only this contribution

The values below are illustrative geometric conditions, not calibrated execution parameters. Only supported portions of the template are filled; the Open slots remain available for team contributions.

| Template slot | Example supplied by the taxonomy |
| --- | --- |
| `[local task]` | Insert the plug into the socket via its opening. |
| `[grounded entities]` | Object: `plug_7`; receptacle: `socket_2`; opening: `socket_2.entry_frame`; tip: `plug_7.entry_tip`; grasp region: annotated plug-body region. |
| `[effector-role assignments]` | Right arm operates on the plug; left arm stabilizes the socket housing, as an A3 instance. |
| `[contact specification]` | Retained plug grasp, stabilizer contact on the housing, and plug/receptacle engagement; opening and alignment geometry use the Insert slot matrix. |
| `[local effect]` | Plug passes the opening and reaches 0.020 m depth relative to the named seat/opening landmark, within 0.002 m. |
| `[motion constraints]` | O: plug keyed frame aligned with socket entry frame within 0.05 rad. D: plug tip follows the inward entry axis, with specified lateral tolerance. |
| `[interaction constraints]` | Constrained entry, alignment, and depth as specified by Insert. |
| `[coordination constraints]` | `During(Insert(plug_7, socket_2), hold(socket_2.housing))`. |
| `[completion criteria]` | Taxonomy contribution: observed opening crossing and specified depth/alignment. Overall command completion remains for the team to define. |

`[embodiment]`, `[current state]`, `[relevant context]`, `[forbidden effects]`, `[preserved conditions]`, `[conditional transitions]`, and `[interruption and recovery rules]` are deliberately unfilled here.
