# Expanding the geometric A/B baseline

The October 4 matrix selects 49 of the 54 RoboDojo eval modules for the reserved
L40S workflow. Each checkpoint gets 98 full-task episodes: baseline and
conditioned, both seed/layout 0. One episode per arm is an initial baseline
screen, not a statistically powered estimate of steerability.

## Collected baseline: October 5, 2026

The `eval-matrix-1004` sweep finished at 22:14 PDT (October 6, 05:14 UTC).
Checkpoint `robodojo_25k` completed all **98 episodes across 49 tasks**.
All episodes passed collection/contact-health checks; this is pipeline validity,
not policy action or task success. **48/49 pairs** passed the A/B matching checks.
`stack_blocks_by_language` is excluded from matched comparisons: the native
environment chose layout 2 for baseline and layout 1 for conditioned, changing
the underlying task instruction. The geometric append was delivered to the
conditioned policy, but these episodes do not establish an A/B comparison.

The offline audit reproduced **287 geometric event scores with zero mismatches**;
285 belong to matched pairs. After excluding the node responsible for earlier
admission failures, **all 98 replacement/current episode allocations passed GPU
admission**, with no new existing-memory incidents. Native task success was
**6/49 baseline and 6/49 conditioned** (6/48 each within matched pairs).

The table reports continuous physical errors over the **48 matched pairs**.
Each conditioning type retains its units. Means use observed events only;
missing events are N/A. A/B deltas compare the same stage/condition events
observed in both arms, so they can differ from the difference of all-event means.

| Action / conditioning | Unit | Baseline mean | Conditioned mean | Observed events B / C | Shared-event mean Δ(C−B) |
| --- | --- | ---: | ---: | --- | ---: |
| Pick / grasp local-z error | mm | 14.468 | 14.635 | 111 / 116 | -0.044 |
| Place / preserved local-z direction error | degrees | 26.623 | 42.656 | 21 / 20 | 6.631 |
| Handover / preserved local-z direction error | degrees | 25.153 | 8.973 | 3 / 3 | -5.661 |
| Actuate / button contact planar error | mm | 3.252 | 4.033 | 5 / 4 | 0.412 |
| Push / contact offset error | mm | 19.782 | N/A | 2 / 0 | N/A |
| Push / goal position error | mm | N/A | N/A | 0 / 0 | N/A |
| Push / goal rotation error | degrees | N/A | N/A | 0 / 0 | N/A |
| Push with tool / contact height error | mm | N/A | N/A | 0 / 0 | N/A |
| Touch with tool / key contact planar error | mm | N/A | N/A | 0 / 0 | N/A |

There is no consistent observed improvement from adding geometric instructions
in this single-episode screen. Release geometry can be measured without a
successful supported placement; the placement success counts remain zero.
Tool push and tool touch have no observed conditioning events, so this sweep
does not establish their policy steerability or live recognition accuracy.
Push has sparse event coverage. These limits remain separate from successful
collection and the independent reproduction of geometric calculations.

Per-task continuous errors, prompts, event coverage and exclusion reasons are in
`EVAL_MATRIX_REPORT.md`, `REPORT.md`, `eval-matrix-results.json` and
`benchmark_results.json` under:

```text
/lustre/fsw/portfolios/cosmos/projects/cosmos_base_cap/users/mverghese/robodojo-atomic-runs/eval-matrix-1004/
```

This sweep covers one checkpoint, one episode per arm and partial first-instance
observers. It does not cover additional checkpoints, every taxonomy factor,
complete task segmentation, or uncalibrated insertion/twist/pour/fold bindings.

## Integrated original and expansion report: October 6

The original `EVAL_MATRIX_REPORT.md`, `EVAL_MATRIX_REPORT.html` and
`eval-matrix-continuous.json` paths now include the original screen and all 17
additional-conditioning suites. At the 20:59 UTC snapshot this is 93 frozen task
comparisons, 50 unique eval tasks represented, 149 valid episodes, 68 verified
A/B pairs, 471 independently reproduced event scores and zero mismatches.
Pending comparisons remain visible. Counts change as controllers collect results.

Each task entry includes its suite, evidence directory, collection outcome,
native task success, actual delivered prompts, runtime/source hashes, tested
definitions and separate physical measurements. Matched summaries retain a
suite column; different targets or runtimes are never averaged across suites.
The historical October 5 screen results above describe only `eval-matrix-1004`.

The combined report also lives on writable home storage:

```text
/home/mverghese/robodojo-expansion-state/integrated-report/EVAL_MATRIX_REPORT.html
/home/mverghese/robodojo-expansion-state/integrated-report/EVAL_MATRIX_REPORT.md
```

The report monitor refreshes those files and the original report paths when
collected evidence changes. The initial original report is preserved in
`integrated-report/original-report-backup/`; raw manifests/results and immutable
programs remain in their original evidence directories. The expansion index
links this combined report and retains individual suite links.

To regenerate the combined report without running the simulator:

```bash
python -m scripts.atomic.report_integrated \
  --original /absolute/path/to/original-matrix \
  --expansion-root /absolute/path/to/expansion-state \
  --output-dir /absolute/path/to/integrated-report
```

Add `--publish-original` to update the original report paths after preserving
their initial contents under the output directory. Publication prefers atomic
replacement. If Lustre rejects new inodes with `EDQUOT`, it updates only the
three existing report files; the original backup and complete new copy remain
on the output filesystem. Permission and other errors are not bypassed.

## Coverage

`generate_eval_matrix.py` reads reviewed object roles from
`segmentation_plans.json`; it does not compile the complete native action graph.
The generated `suite.json` lists included and missing families for every task.
Coverage includes pick, place, push, push with tool, actuate, touch with tool and
handover. Most tasks have partial pick/place observers. Stronger programs are
retained for align blocks, language stacking, buttons, xylophone, T pushing and
general pickup.

Candidate observers are independent graph roots with `required: false`. Each
measures the first recognized action for one reviewed object/direction; unused
candidates are not required native action failures. Source prefixes expand
against the actual layout with explicit count bounds and rigid category checks.
Expanded labels and instance IDs are saved as binding evidence. This does not
resolve the correct language/game target or enumerate every repeat.

Four random variants routed to H200 by imaginaire4 are excluded from the L40S
runner. `fold_clothes` lacks physical fold recognition. Generic insertion, twist
and material transfer recognizers exist, but task-specific opening, axis, pivot,
material and cavity bindings require live calibration before inclusion. Tasks
containing those actions may still be included for their pickups.

## Added targets

| Observer | Physical success | Geometric score and prompt |
| --- | --- | --- |
| Candidate pick | Two fingers of one arm, at least two contact steps, 25 mm held rise and native lift predicate | At first 25 mm lift, maximum absolute local-z offset of eligible finger contacts from mesh-bounds center; target 0 ±10 mm. Other axes unrestricted. |
| Candidate place | Held transport ≥20 mm, complete release, reviewed support contact and 24 stable physics steps | At first release, object local-z direction within 30° of its episode-initial direction; yaw unrestricted. |
| Handover | Giver/receiver grip transfer with overlap and receiver-only hold | At receiver-only event, same 30° initial-z-direction condition. Both directions are optional observers. |
| Sweep | Held broom, broom/block contact, tool and target horizontal motion ≥10 mm, reviewed support and bounded vertical motion | At stroke, every broom/block contact has local-z offset from block mesh center 0 ±10 mm. |

Candidate placement confirms placement on an allowed reviewed support, not the
native correct target assignment. Native task success is separate. Stronger
programs retain their geometric targets; the matrix adds the same grasp-height
condition to their pickups. Numerical definitions and matching prose are saved
in generated programs. Mesh-center and initial-direction targets are explicit
prototype targets; review live feasibility and event coverage before adopting
them as a final benchmark design.

## Generate and run

Create a checkpoint map outside Git. Every compatible base must contain an
imaginaire4 one-episode, seed-0 plan and source archive with a matching checkpoint:

```json
{
  "robodojo_25k": {
    "checkpoint": "s3://bucket/path/checkpoints/iter_000025000",
    "base_run": "/absolute/path/to/compatible-base-run"
  }
}
```

Using the workflow environment from `CONDITIONING_AB.md`:

```bash
python scripts/atomic/generate_eval_matrix.py \
  --checkpoints /absolute/path/checkpoints.json \
  --output-dir /absolute/path/new-matrix

python scripts/atomic/run_suite.py \
  --suite /absolute/path/new-matrix/suite.json \
  --base-run /absolute/path/to/compatible-base-run \
  --credentials-file /absolute/path/to/storage-credentials \
  --gpu-memory-ledger /absolute/path/gpu-memory-observations.jsonl \
  --name rb-eval-matrix --max-concurrent 8 --max-busy-retries 2 --dry-run
```

Inspect prepared specs before running the same command without `--dry-run`,
under a suite-local lock in a persistent controller. Checkpoint, inference,
reservation and source come from the compatible base. Each wall timeout is
bounded to 1–10 hours, using native step limit ×12 seconds/step, without changing
the native step limit. Overall timeout includes the startup budget and another
hour of overhead. Long wall time allowances do not guarantee episode completion.

Preparation freezes overlay/program/spec/source hashes and execution controls.
Each A/B pair differs only in `geometric_instruction`. Baseline gets the native
resolved task instruction; conditioned gets exactly that text plus the append,
throughout the episode. Observers do not switch prompts. Resume verifies frozen
inputs. Additional checkpoints require their matching base-run mappings.

Admission requires ≤512 MiB existing memory and no compute processes in two
samples. Rejected allocations get at most two fresh-name retries with identical
overlay/source/program, preserving originals in `attempts/<case>/attempt-*/`.
Memory and neighbor ledgers stay enabled. After two other collected failed
cases the controller stops new submissions for diagnosis. Archived jobs are
terminal; collected report status determines collection success.

`--max-concurrent` counts queued and executing jobs together (default 4;
supported range 1–128). Set it to the experiment's authorized submission window.
`--priority-class high-9000` records a scheduling amendment for future submissions
without rebuilding frozen simulator inputs. Exact submitted specs and hashes are
retained separately. Lepton rejects priority changes on existing jobs: only
`stopped` is mutable. To change queued jobs, stop them, archive their preparation
and scheduler records, and requeue fresh names with identical experimental inputs.
Restarting with this flag alone does not update existing jobs. Stop the suite
controller and collectors before replacing a
controller, leaving remote jobs intact, then resume the same frozen suite.

Use `--exclude-node NODE_ID` (repeatable) when admission evidence repeatedly
identifies a node with existing GPU memory. This filters the prepared node
allowlist for future submissions and retries, retains the reservation, and records
the effective allowlist in the separate submission spec and scheduling metadata.
It fails before submission if no prepared node remains. Existing jobs retain
their original placement constraints; frozen policy inputs are unchanged.

## Outputs and validity

Regenerate both report formats from collected evidence without simulator reruns:

```bash
python -m scripts.atomic.report_eval_matrix --run-dir /absolute/path/to/matrix
```

The reports give separate continuous means and medians for each conditioning
type: distances in mm, angles in degrees, footprint areas in mm² and overlap
fractions. They contain no combined tolerance-normalized score. A/B deltas use
the same stage/condition events observed in both arms of a verified pair.
Missing events remain N/A. Every task includes its exact conditioning append,
measurement selectors, reference, target, axes, tolerance, event and delivered
policy prompts. Tasks not run are listed with the exclusion reason.

- `EVAL_MATRIX_REPORT.md`: per-task continuous geometric measurements in actual
  units, with the tested conditioning definitions and exact delivered prompts.
- `EVAL_MATRIX_REPORT.html`: self-contained searchable version of the report.
- `eval-matrix-continuous.json`: separate means/medians in original measurement
  units, observation counts and deltas for shared observed action events.
- `eval-matrix-results.json`: component means/medians, declared/observed counts,
  missing-event statuses and separate matched-only metrics.
- `REPORT.md`: individual scores, captured prompts, contact health and layouts.
- `benchmark_results.json`: case summaries and provenance.
- `runs/<case>/`: immutable inputs, native report, geometry audit, traces, GPU
  admission and neighbor evidence. Retain outside Git.

A verified match requires completed episodes, equal checkpoint/runtime/source/
inference controls, actual layout 0, delivered append, real contact reports,
no callback errors and no geometric mismatch. Valid single episodes are reported
descriptively while partners are pending. A quiet startup scene with no reports
is `awaiting_contact_evidence`; its contact health remains unverified until real
reports arrive. Callback errors fail instrumentation.

Missing events have no error or pass. Geometry pass counts use observed events
and report coverage alongside them. Optional observer counts are not required
native action counts. Native success, physical recognition and geometry remain
separate. Offline audit reproduces geometry from raw measurements, not action
recognition. The existing compatible checkpoint alone does not cover all
checkpoints; the experiment owner must identify the additional checkpoint set.
