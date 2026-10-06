# Audit of all atomic action families

All **11 families**, **54 taxonomy slots**, **270 factor cells**, and **54 native
source modules** are indexed in [CONDITIONING_AUDIT.md](CONDITIONING_AUDIT.md),
[TAXONOMY.md](TAXONOMY.md), [TASK_MAP.md](TASK_MAP.md), and
[SEGMENTATION.md](SEGMENTATION.md). The eval manifest determines the evaluable task
set; a source module is not automatically an eval entry. A source plan is not an
observed trace or a runnable atomic program.

## Current boundary

Physical runtime adapters now exist for all eleven family names. Coverage differs
by binding and by observed evidence. Action success, geometric error and complete
native task success are separate outputs. Final task state does not establish
which actions occurred. See [EXPANSION_STATUS.md](EXPANSION_STATUS.md) for the
frozen live suites and outstanding validation, and the three detailed references:

- [GEOMETRIC_MEASUREMENT.md](GEOMETRIC_MEASUREMENT.md): factor definitions and units.
- [ATOMIC_SUCCESS.md](ATOMIC_SUCCESS.md): physical action success and limitations.
- [RECOGNITION_SEGMENTATION.md](RECOGNITION_SEGMENTATION.md): boundaries, events and segmentation.

| Family; example | Implemented recognition and conditioning | Remaining evidence or implementation boundary |
| --- | --- | --- |
| **pick**; `general_pickup`, `plug_in_charger` | Same-arm force-bearing two-finger held motion; actual per-contact geometry, initial selection, held endpoint, full/object-axis and contacting-arm TCP orientation. | Selection/TCP probes submitted; opposing bodies alone do not certify force closure. |
| **place**; `stack_blocks`, `stack_bowls` | Held transport, gradual same-arm jaw release, no remaining finger contact, upward support and bounded settling; release/final pose, yaw, overlap and calibrated containment. | Fresh scene-load contact enablement must validate actual object/object support. Hanging needs calibrated hook/handle predicates. |
| **push**; `push_T` | Physical contact-coupled supported object motion; first-motion contact, final pose and attempt-end error even when success fails. | Longer paths and other asset contact surfaces need bindings; no held/lifted transport counted as push. |
| **push_with_tool**; `align_blocks`, `sweep_blocks` | Independent finger/tool hold and tool/target contact, supported target/tool motion; contact points, heading and path/endpoints. | Fresh object contact reporting and active tool edges need live validation. |
| **pour**; `pour_balls_into_vase`, `pour_liquid_into_cup` | Persistent rigid/particle source cohort, held/tilted source exit and sustained target entry; source pose, mouth frames and interpolated opening crossing position/velocity errors. | Actual cavities and mouths must be calibrated from material geometry. Nominal particle mass is not measured liquid volume. Liquid capture suite currently measures pickup only. |
| **actuate**; `press_by_number` | Actual moving cap/joint state and scoped contact, press/release cycles or contact joint motion; cap contact, approach and returned endpoint. | Lever/bidirectional joint adapters need asset-specific bindings and live examples. |
| **twist**; `fasten_screws` | Held part/target contact, pivot radius/depth, signed unwrapped rotation and bounded off-axis motion; pivot endpoint/contact/axis conditions. | Matching nut/bolt shaft-top bindings prepared; mechanical thread engagement is not certified. |
| **insert**; `plug_in_charger`, `insert_key` | Held outside-to-inside tip/opening depth, actual target contact and alignment; entry/end pose, explicit material section/aperture fit and seat/rim metrics. | Physical opening, material mesh and fit/seat bindings need calibration; annotation alone is insufficient. Through/flush are not unrestricted generic relation names. |
| **touch_with_tool**; `play_Xylophone` | Actual held tool/target encounter, target-relative approach and held retraction; impact region, tool orientation and retraction trajectory. | Fresh contacts/landmarks must validate strike and path events. First-strike observers do not establish musical order or timing. |
| **handover**; `insert_key` | Named giver hold, simultaneous overlap, receiver-only sustained contact and bounded object motion; exchange pose and receiving-hand offset. | Receiving-hand probes submitted; gripper proximity cannot replace actual named-arm contact. |
| **fold**; `fold_clothes` | Live persistent cloth vertices/tangent/line frames; newly lifted, closed, bent and settled material deformation; landmark destination, normal, crease drift and pose. | No force-bearing finger/cloth-particle correspondence yet. Whole-patch layer overlap and self-penetration are not certified by landmark gaps. |

## Shared audit corrections

Contact reports are enabled after task objects load, not only when the initial
robot scene is constructed. Fresh stack/tool runs validate this fix. Previous
frozen runs with robot-only enablement retain that limitation. Missing events
remain missing and do not become zero errors or successful actions.

Geometry uses selected physical points/frames, all contact points, live articulated
child poses and actual material vertices. Directional object relations require
signed ordering and projected triangle overlap; supported-on additionally requires
support evidence. Root/centre/functional offsets and live/initial reference times
are explicit. P/D/R contact positions carry no orientation; T/O need a separate
real frame. Distances, angles, area, volume and fractions are reported separately.

Selected material meshes exclude duplicate visual/collision proxies when computing
closed-solid volume or aperture fit. Missing/nonclosed meshes fail certification.
Finite nonconvex interior-box unions are independently calibrated cavities; outer
object bounds are never silently interpreted as interiors.

`put_bottles_into_dustbin` explicitly requests throwing. Place does not certify
release velocity and ballistic flight. Throw remains a flagged taxonomy gap.
