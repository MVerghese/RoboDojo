# Expanding the geometric A/B baseline

The October 4 matrix selects 49 of the 54 RoboDojo eval modules for the reserved
L40S workflow. Each checkpoint gets 98 full-task episodes: baseline and
conditioned, both seed/layout 0. One episode per arm is an initial baseline
screen, not a statistically powered estimate of steerability.

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

## Outputs and validity

- `EVAL_MATRIX_REPORT.md`: compact checkpoint/task/action/prompt counts.
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
