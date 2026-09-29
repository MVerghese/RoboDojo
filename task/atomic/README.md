# Atomic geometry benchmark prototype

This branch adds a separate evaluation mode on top of RoboDojo's existing full-task eval. Its [taxonomy](TAXONOMY.md) defines 11 manipulation families and five geometric modifier types. The [task map](TASK_MAP.md) sketches how all 54 task modules decompose. Three executable programs are included in `programs/`.

## What runs today

- A program JSON defines named atomic stages, an instruction, existing RoboDojo success predicates, and geometric conditions on typed slots.
- Geometry conditions report continuous error and pass/fail for a point, SE(3) pose, landmark-relative displacement, landmark-relative orientation, or spatial relation.
- `AtomicSession` measures conditions at specified events: first object lift, first object motion, or atomic-stage success. The result keeps **action success** and **geometry adherence** separate in `eval_result.details[*].atomic`.
- A normal evaluation can record policy action traces. A trace can be annotated with action indices at stage starts. Atomic mode resets the original layout, replays the action prefix, starts a fresh stage scoring window, and stops when the selected atomic success checks pass or its step limit expires.
- A variant JSON changes expected geometry, tolerances, references, event, and instruction while keeping the same stage success checks. This permits paired counterfactual trials.

## Program format

See [`deposit_coin.json`](programs/deposit_coin.json) for a two-stage example. Each stage has an `id`, `family`, `instruction`, `success_checks`, and `geometry`. A geometry entry has an `id`, `slot`, one of the five `kind` values, an `expected` value, `tolerance`, `measurement`, optional `reference`, and an `event`. All poses are environment-local with scalar-first quaternions. `relative_displacement` is expressed in the reference object's frame. Spatial directional relations use x right, y forward, z up in that frame. Values must be selected from feasible geometry for the task and calibrated against the chosen object asset.

The included grasp and push examples measure the **nearest robot TCP as a proxy** at first lift/motion. They do not claim to recover the exact finger-object contact patch. A benchmark cell requiring exact contact needs PhysX contact reporting and a contact-point resolver.

## Record, annotate, run

Run a normal RoboDojo evaluation with the usual policy server and append `--atomic_record_dir /path/to/traces` to `scripts/eval_policy.sh`. This writes one JSON trace per episode. Use a successful episode and add stage boundaries as action indices; for `deposit_coin`, for example:

```json
"stage_starts": {"pick_coin": 0, "insert_coin": 37}
```

The index `37` means replay actions `0..36`, then ask the policy to perform `insert_coin`. The trace's `layout_id` must match the saved RoboDojo layout. The first stage can run without a trace. For a later stage, supply all three arguments to the normal eval launcher:

```text
--atomic_spec task/atomic/programs/deposit_coin.json
--atomic_stage insert_coin
--atomic_trace /path/to/annotated_trace.json
```

To vary a geometric target, add `--atomic_variant /path/to/variant.json`. The example [`push_T_right_contact.json`](programs/variants/push_T_right_contact.json) changes the requested TCP contact offset and atomic instruction. The launcher forwards these flags to `src/eval_client/main.py` and forces one environment and one trial in atomic mode.

## Remaining work and validation needs

- The map is complete as an inventory, but only the three listed programs are executable. Each remaining task needs grounded labels, independent stage predicates, and action-boundary annotations. Some tasks require auxiliary states, such as an opponent move or a held stabilizing object.
- Recorded action prefixes are replayed through the simulator. Determinism and state fidelity, especially for garments and fluids, must be checked in Isaac Sim. This workspace has no Isaac Sim, NVIDIA driver, or `Assets`, so only schema, math, and mock session tests run here.
- Exact grasp and tool-contact geometry requires simulator contact points; the current TCP estimate is a named proxy in each result (`tcp_contact_proxy: true`).
- Geometric variants must remain physically feasible. A final-pose variant that conflicts with a stage's fixed success predicate is invalid; choose a success predicate that represents the action independently of the changed geometry.

Run the local tests with `python3 -m unittest discover -s tests -p 'test_atomic_benchmark.py' -v`.
