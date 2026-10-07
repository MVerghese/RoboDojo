#!/usr/bin/env python3
"""Audit raw handover/release/insertion boundaries without a simulator."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from task.atomic.recognition_validation import validate_recognition_window


def validate_report(report):
    rows=[]
    for native in report.get('native_results', []):
        details=native.get('details', {})
        for episode,detail in (details.items() if isinstance(details,dict) else enumerate(details)):
            for stage in [*detail.get('atomic_sequence',{}).get('stages',[]),
                          *([detail['atomic']] if 'atomic' in detail else [])]:
                result=validate_recognition_window(stage)
                if result['status'] != 'not_applicable':
                    rows.append({'episode':str(episode),'layout_id':detail['layout_id'],
                        'stage_id':stage['stage_id'],'action_success':stage['action_success'],**result})
    return rows


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(); data=args.report.read_bytes(); rows=validate_report(json.loads(data))
    args.output.write_text(json.dumps({'report':str(args.report.resolve()),
        'report_sha256':hashlib.sha256(data).hexdigest(),'windows':rows},indent=2)+'\n')
    print(json.dumps({'output':str(args.output),'statuses':dict(Counter(r['status'] for r in rows))}))
