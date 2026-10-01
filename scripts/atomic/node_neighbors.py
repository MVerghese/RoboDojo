"""Record scheduler neighbors of a GPU incident without attributing GPU memory."""

from datetime import datetime, timezone
import json
from pathlib import Path


GPU_SCOPE_ENVS = {"CUDA_VISIBLE_DEVICES", "NVIDIA_VISIBLE_DEVICES", "CUDA_DEVICE_ORDER"}


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def summarize_job(job):
    """Select contact and scheduling fields; never save commands or arbitrary envs."""
    metadata = job.get("metadata") or {}
    spec = job.get("spec") or {}
    security = spec.get("user_security_context") or {}
    return {
        "owner": metadata.get("owner"), "created_by": metadata.get("created_by"),
        "job_name": metadata.get("name"), "job_created_at": metadata.get("created_at"),
        "state": (job.get("status") or {}).get("state"),
        "resource_shape": spec.get("resource_shape"),
        # Missing is unknown, rather than evidence that privileged mode is disabled.
        "privileged": security.get("privileged"),
        "gpu_scope_envs_in_job_spec": {
            env["name"]: env.get("value") for env in spec.get("envs") or []
            if env.get("name") in GPU_SCOPE_ENVS
        },
    }


def error_summary(error):
    # API error bodies can contain a full job spec; retain only the failure type/status.
    response = getattr(error, "response", None)
    code = getattr(response, "status_code", None)
    return f"{type(error).__name__}" + (f" (HTTP {code})" if code else "")


def collect_node_neighbors(client, node_group_ids, node, job_id, replica_id, admission,
                           collection_mode="live_admission"):
    result = {
        "schema_version": 1, "collection_started_at": utc_now(),
        "collection_mode": collection_mode, "job_id": job_id, "replica_id": replica_id,
        "node": node, "incident_observed_at": admission["samples"][0]["observed_at"],
        "gpu_uuids": sorted({g["uuid"] for s in admission["samples"] for g in s["gpus"]}),
        "admission_samples": admission["samples"],
        "workloads": [], "errors": [],
        "attribution": "Scheduler colocation only; no process-to-job or GPU UUID ownership mapping.",
    }
    found = None
    for group in node_group_ids:
        try:
            response = client._get(f"/dedicated-node-groups/{group}/nodes")
            response.raise_for_status()
            found = next((n for n in response.json() if n["metadata"]["id"] == node), None)
            if found is not None:
                result["node_group_id"] = group
                result["node_snapshot_at"] = utc_now()
                break
        except Exception as error:
            result["errors"].append({"node_group_id": group, "error": error_summary(error)})
    if found is None:
        result["errors"].append({"error": "node not found in accessible node groups"})
    else:
        for workload in found.get("status", {}).get("workloads", []):
            row = {key: workload.get(key) for key in (
                "type", "id", "name", "replica_id", "workspace", "gpu_count", "shape")}
            row["is_our_job"] = workload.get("id") == job_id
            if row["type"] == "job":
                try:
                    job = client.job.get(row["id"]).model_dump(
                        mode="json", by_alias=True, exclude_none=True)
                    row.update(summarize_job(job))
                except Exception as error:
                    row["lookup_error"] = error_summary(error)
                    result["errors"].append({"job_id": row["id"], "error": row["lookup_error"]})
            result["workloads"].append(row)
    result["collection_finished_at"] = utc_now()
    result["incident_to_snapshot_seconds"] = (
        datetime.fromisoformat(result.get("node_snapshot_at", result["collection_finished_at"]))
        - datetime.fromisoformat(result["incident_observed_at"].replace("Z", "+00:00"))
    ).total_seconds()
    return result


def save_node_neighbors(path, snapshot):
    """Deduplicate monitor restarts and write a contact report next to the JSONL."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    records = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
    def key(row):
        return (row["job_id"], row["replica_id"], row["incident_observed_at"], row["collection_mode"])
    if not any(key(row) == key(snapshot) for row in records):
        with path.open("a") as stream:
            stream.write(json.dumps(snapshot) + "\n")
        records.append(snapshot)
    lines = ["# Jobs sharing nodes with GPU memory incidents", "",
             "Owners and privileged flags come from Lepton job metadata. These are scheduler "
             "neighbors, not confirmed owners of the unexpected memory. GPU UUID assignments "
             "and process-to-job mappings are unavailable through these APIs. Missing GPU scope "
             "environment variables in a job spec do not prove missing runtime isolation. "
             "Historical entries reconstruct overlap from retained replica metadata/events; "
             "they are not contemporaneous node snapshots. Missing historical neighbors "
             "means records could not be recovered, not that the node was otherwise empty.", ""]
    def cell(value):
        return str(value if value is not None else "unknown").replace("|", "\\|").replace("\n", " ")
    for record in records:
        lines.extend([f"## {record['node']} — {record['job_id']}", "",
                      f"Incident: {record['incident_observed_at']}. Snapshot: "
                      f"{record.get('node_snapshot_at', record['collection_finished_at'])}. "
                      f"Mode: {record['collection_mode']}. Delay: "
                      f"{record['incident_to_snapshot_seconds']:.1f} seconds.", "",
                      "Affected GPU UUID(s): " + ", ".join(record["gpu_uuids"]) + ".", "",
                      "| Neighbor job | Owner / creator | Replica | GPU count | Privileged requested | Declared GPU scope | Placement evidence |",
                      "| --- | --- | --- | ---: | --- | --- | --- |"])
        for workload in record["workloads"]:
            if workload.get("is_our_job") or workload.get("type") != "job":
                continue
            scope = workload.get("gpu_scope_envs_in_job_spec")
            scope_text = "not retrieved" if scope is None else (json.dumps(scope) if scope else "none declared")
            count = workload.get("gpu_count")
            if workload.get("gpu_count_source") == "resource_shape":
                count = f"{count} (job shape)"
            values = [workload["id"], workload.get("owner") or workload.get("created_by"),
                      workload.get("replica_id"), count,
                      workload.get("privileged"), scope_text,
                      workload.get("overlap_evidence", "node workload snapshot")]
            lines.append("| " + " | ".join(cell(v) for v in values) + " |")
        if record.get("history_evidence"):
            lines.extend(["", "Historical evidence: " + record["history_evidence"]])
        if record["errors"]:
            lines.extend(["", "Collection errors: " + json.dumps(record["errors"])])
        lines.append("")
    path.with_suffix(".md").write_text("\n".join(lines) + "\n")
