# Audit of all atomic action families

All **11 families**, **54 taxonomy slots**, **270 factor cells**, and **54 native
source modules** are indexed in [CONDITIONING_AUDIT.md](CONDITIONING_AUDIT.md),
[TAXONOMY.md](TAXONOMY.md), [TASK_MAP.md](TASK_MAP.md), and
[SEGMENTATION.md](SEGMENTATION.md). The eval manifest determines the evaluable task
set; a source module is not automatically an eval entry. A source plan is not an
observed trace or a runnable atomic program.

## Current boundary

Physical runtime adapters and observed-prerequisite diagnostics now exist for all
eleven family names. Coverage differs
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
| **place**; `stack_blocks`, `stack_bowls` | Held transport, gradual same-arm jaw release, no remaining finger contact, upward support and bounded settling; release/final pose, yaw, overlap and calibrated containment. | The fresh stack-block baseline validates actual block/block and block/table support: all three place observers emitted release/settled and passed. Other assets remain pending. Hanging needs calibrated hook/handle predicates. |
| **push**; `push_T` | Physical contact-coupled supported object motion; first-motion contact, final pose and attempt-end error even when success fails. | Longer paths and other asset contact surfaces need bindings; no held/lifted transport counted as push. |
| **push_with_tool**; `align_blocks`, `sweep_blocks` | Independent finger/tool hold and tool/target contact, supported target/tool motion; contact points, heading and path/endpoints. | Independent table-level strokes no longer require lifted-tool pickup. Fresh tool-push baseline reports no qualified stroke; active tool edges still need calibration. |
| **pour**; `pour_balls_into_vase`, `pour_liquid_into_cup` | Persistent rigid/particle source cohort, held/tilted source exit and sustained target entry; source pose, mouth frames and interpolated opening crossing position/velocity errors. | Fresh calibrated actual-mouth liquid A/B validates 10/3 destination particle-center crossings with consistent held/tilted source evidence. Ball A/B has pickup but no pour crossing. Whole-fluid volume and whole-ball mouth fit remain uncertified. |
| **actuate**; `press_by_number` | Actual moving cap/joint state and scoped contact, press/release cycles or contact joint motion; cap contact, approach and returned endpoint. | Button press/release prerequisites now have live ratio/contact diagnostics; a fresh matched button pair is running. Lever/bidirectional joint bindings still need live examples. |
| **twist**; `fasten_screws` | Held part/target contact, pivot radius/depth, signed unwrapped rotation and bounded off-axis motion; pivot endpoint/contact/axis conditions. | Matching nut/bolt shaft-top bindings prepared; mechanical thread engagement is not certified. |
| **insert**; `plug_in_charger`, `insert_key` | Held outside-to-inside tip/opening depth, actual target contact and alignment; entry/end pose, explicit material section/aperture fit and seat/rim metrics. | Physical opening, material mesh and fit/seat bindings need calibration; annotation alone is insufficient. Through/flush are not unrestricted generic relation names. |
| **touch_with_tool**; `play_Xylophone` | Actual held tool/target encounter, target-relative approach and held retraction; impact region, tool orientation and retraction trajectory. | Fresh eight-strike A/B validates sixteen compatible impact/retraction windows and scalar scores. This does not establish musical order or timing. |
| **handover**; `insert_key` | Named giver hold, simultaneous overlap, receiver-only sustained contact and bounded object motion; exchange pose and receiving-hand offset. | Fresh bottle/bowl A/B validates five physical boundary windows; absent handovers remain missing. Gripper proximity cannot replace named-arm contact. |
| **fold**; `fold_clothes` | Live persistent cloth vertices/tangent/line frames; newly lifted, closed, bent and settled material deformation; landmark destination, normal, crease drift and pose. | Full endpoint mesh readback is live: one native-success baseline has 149 qualifying open chains and 70 branched bending networks, while landmark observers fail. Temporal candidate stability is implemented and running. No finger/particle force, unique crease, whole-layer or self-penetration certificate. |

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
