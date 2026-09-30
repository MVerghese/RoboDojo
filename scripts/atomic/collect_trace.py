#!/usr/bin/env python3
"""Stream a Lepton result archive and extract validated atomic action traces."""

import argparse
import json
from pathlib import Path
import sys
import tarfile
from urllib.parse import urlparse

import boto3

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from task.atomic.spec import AtomicTrace


def s3_location(url: str) -> tuple[str, str]:
    parsed = urlparse(url)
    if parsed.scheme != "s3" or not parsed.netloc or not parsed.path.strip("/"):
        raise ValueError("results URL must be a full s3://bucket/key prefix")
    return parsed.netloc, parsed.path.strip("/")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-s3", required=True, help="Task/seed result prefix")
    parser.add_argument("--credentials-file", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    credentials = json.loads(args.credentials_file.read_text())
    client = boto3.client(
        "s3", endpoint_url=credentials["endpoint_url"],
        aws_access_key_id=credentials["aws_access_key_id"],
        aws_secret_access_key=credentials["aws_secret_access_key"],
        region_name=credentials["region_name"],
    )
    bucket, prefix = s3_location(args.results_s3)
    report = json.loads(client.get_object(Bucket=bucket, Key=f"{prefix}/eval_report.json")["Body"].read())
    print("evaluation:", report["status"], "completed episodes:", report["completed_episodes"])

    body = client.get_object(Bucket=bucket, Key=f"{prefix}/results.tar.gz")["Body"]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    with tarfile.open(fileobj=body, mode="r|gz") as archive:
        for member in archive:
            path = Path(member.name)
            in_traces = bool(path.parts) and (
                path.parts[0] == "traces" or path.parts[:2] == (".", "traces")
            )
            if not member.isfile() or not in_traces:
                continue
            if path.suffix != ".json":
                continue
            source = archive.extractfile(member)
            if source is None:
                continue
            payload = json.load(source)
            if not isinstance(payload.get("layout_id"), int) or not isinstance(payload.get("actions"), list):
                raise ValueError(f"invalid trace in {member.name}")
            if not isinstance(payload.get("stage_starts"), dict):
                raise ValueError(f"trace is missing stage boundaries: {member.name}")
            output = args.output_dir / path.name
            output.write_text(json.dumps(payload, indent=2) + "\n")
            trace = AtomicTrace.load(output)
            print("trace:", output, "layout:", trace.layout_id, "actions:", len(trace.actions),
                  "stage starts:", trace.stage_starts, "episode success:", payload.get("episode_success"))
            count += 1
    if count < 1:
        print("the result archive contains no atomic traces", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
