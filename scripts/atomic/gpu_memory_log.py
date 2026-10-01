"""Keep initial GPU memory observations and counts across capture placements."""

from datetime import datetime, timezone
import json
from pathlib import Path


def append_observation(ledger, observation):
    ledger = Path(ledger)
    ledger.parent.mkdir(parents=True, exist_ok=True)
    records = [json.loads(line) for line in ledger.read_text().splitlines()] if ledger.exists() else []
    key = (observation["job_id"], observation.get("replica_id"), observation["gpu_uuid"])
    if not any((r["job_id"], r.get("replica_id"), r["gpu_uuid"]) == key for r in records):
        with ledger.open("a") as stream:
            stream.write(json.dumps(observation) + "\n")
        records.append(observation)
    affected = [r for r in records if r["existing_allocation"]]
    summary = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "observed_placements": len(records),
        "affected_placements": len(affected),
        "observed_unique_gpus": len({r["gpu_uuid"] for r in records}),
        "affected_unique_gpus": len({r["gpu_uuid"] for r in affected}),
        "affected_gpu_uuids": sorted({r["gpu_uuid"] for r in affected}),
    }
    ledger.with_suffix(".summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    lines = [
        "# Initial GPU memory observations", "",
        f"**{summary['affected_unique_gpus']} distinct GPUs** had existing allocations across "
        f"**{summary['affected_placements']} placements**, out of "
        f"**{summary['observed_placements']} placements with initial memory evidence**.", "",
        "A placement is counted when initial usage exceeds its recorded driver-memory allowance "
        "(currently 512 MiB), or an existing compute process is observed. Historical samples "
        "without process lists establish usage, not allocation ownership. Counts cover the "
        "placements with saved initial measurements; earlier replicas without samples are excluded.", "",
        "| Job | Node | GPU UUID | Initial used MiB | Highest admission sample MiB | Existing allocation |",
        "| --- | --- | --- | ---: | ---: | --- |",
    ]
    for row in records:
        lines.append(
            f"| `{row['job_id']}` | `{row.get('node') or 'unknown'}` | `{row['gpu_uuid']}` | "
            f"{row['initial_used_mib']} | {row['max_initial_used_mib']} | "
            f"{'Yes' if row['existing_allocation'] else 'No'} |"
        )
    lines.extend(["", f"Updated: {summary['updated_at']}", "",
                  "The adjacent JSONL log retains timestamps, replica IDs, and evidence paths/URIs."])
    ledger.with_suffix(".md").write_text("\n".join(lines) + "\n")
    return summary


def record_admission(ledger, job_id, replica_id, node, admission, evidence):
    snapshots = admission.get("samples", [])
    uuids = sorted({gpu["uuid"] for sample in snapshots for gpu in sample["gpus"]})
    summary = None
    for uuid in uuids:
        measured = [(sample, gpu) for sample in snapshots for gpu in sample["gpus"] if gpu["uuid"] == uuid]
        first_sample, first_gpu = measured[0]
        highest = max(gpu["used_mib"] for sample, gpu in measured)
        processes = [p for sample in snapshots for p in sample["compute_processes"] if p["gpu_uuid"] == uuid]
        summary = append_observation(ledger, {
            "job_id": job_id, "replica_id": replica_id, "node": node, "gpu_uuid": uuid,
            "observed_at": first_sample["observed_at"],
            "initial_used_mib": first_gpu["used_mib"], "max_initial_used_mib": highest,
            "total_mib": first_gpu["total_mib"], "max_allowed_used_mib": admission["max_used_mib"],
            "compute_processes_observed": bool(processes),
            "existing_allocation": highest > admission["max_used_mib"] or bool(processes),
            "admitted": admission["admitted"], "evidence": evidence,
        })
    return summary
