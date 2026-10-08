#!/usr/bin/env python3
"""Independently audit retained source/flow witnesses and native cloth probe evidence."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from scripts.atomic.audit_scores import audit_flow,apply_flow_validation,audit_material_bounds
from scripts.atomic.storage import atomic_write_json
from scripts.atomic.validate_recognition_windows import validate_report


def validate_report_materials(report):
    episodes=[]
    for native in report.get('native_results',[]):
        details=native.get('details',{})
        for ident,detail in (details.items() if isinstance(details,dict) else enumerate(details)):
            probe=detail.get('contact_instrumentation',{}).get('cloth_contact_probe')
            cloth=None
            if probe is not None:
                counts=probe.get('counts',{})
                cloth={'enabled_mesh_paths':probe.get('enabled_mesh_paths',[]),'counts':counts,
                    'status':'no_native_cloth_callbacks_observed' if counts.get('headers',0)==0
                             else 'native_callbacks_without_verified_material_correspondence',
                    'native_samples_count':len(probe.get('native_samples',[])),
                    'force_grasp_supported':False,
                    'scope':'diagnostic callback evidence; no per-vertex finger-force calibration'}
            stages=[]
            for stage in [*detail.get('atomic_sequence',{}).get('stages',[]),
                          *([detail['atomic']] if 'atomic' in detail else [])]:
                audited={'material_flow':audit_flow(stage.get('material_flow'))}
                apply_flow_validation(stage,audited);flow=audited.get('material_flow') or {}
                stages.append({'stage_id':stage['stage_id'],'action_success':stage['action_success'],
                    'crossings':len(flow.get('crossings',{})),
                    'source_witness_summary':flow.get('witness_summary',{}),
                    'flow_statuses':dict(Counter(r['status'] for r in flow.get('crossings',{}).values()))})
                stages[-1]['material_bounds']=audit_material_bounds(stage.get('material_bounds'))
            episodes.append({'episode':str(ident),'layout_id':detail.get('layout_id'),
                'native_success':detail.get('success'),'cloth_probe':cloth,'stages':stages})
    return {'episodes':episodes,'boundary_windows':validate_report(report)}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--report',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();raw=a.report.read_bytes();result=validate_report_materials(json.loads(raw))
    atomic_write_json(a.output,{'report':str(a.report.resolve()),'report_sha256':hashlib.sha256(raw).hexdigest(),**result})
    print(json.dumps({'output':str(a.output),'episodes':result['episodes']}))
