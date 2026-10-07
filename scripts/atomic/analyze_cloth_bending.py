#!/usr/bin/env python3
"""Audit captured full garment endpoints for new mesh bending in physical units."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from task.atomic.cloth_bending import ClothBendingTopology, measure_bending_persistence
from scripts.atomic.storage import atomic_write_json

DEFAULTS={'min_bend_rad':math.pi/4,'min_increase_rad':math.pi/6,'min_component_length_m':.01}


def analyze_report(report, thresholds=None):
    rows=[]
    for native in report.get('native_results',[]):
        details=native.get('details',{})
        for episode,detail in (details.items() if isinstance(details,dict) else enumerate(details)):
            seq=detail.get('atomic_sequence',{});capture=seq.get('cloth_bending_capture')
            if capture is None:continue
            if not capture.get('garments'):
                rows.append({'episode':str(episode),'status':capture['status']});continue
            for label,current in capture['garments'].items():
                row={'episode':str(episode),'label':label,'layout_id':detail.get('layout_id'),
                     'native_success':detail.get('success'),'status':current['status']}
                try:
                    if current['status']!='captured':row['reason']=current.get('reason')
                    else:
                        initial=seq['scene_calibration']['objects'][label]['material']
                        topology=ClothBendingTopology(initial['ids'],initial['initial_positions'],initial['triangles'])
                        if topology.topology_sha256!=current['topology_sha256']:
                            raise ValueError('retained endpoint topology fingerprint differs from initial mesh')
                        row.update(topology.measure(current['ids'],current['positions_world'],**(thresholds or DEFAULTS)))
                        row['physics_step']=current['physics_step'];row['policy_action_index']=current['policy_action_index']
                        lookup={int(v):i for i,v in enumerate(current['ids'])}
                        endpoint_positions=[current['positions_world'][lookup[int(v)]] for v in topology.ids]
                        row['temporal_persistence']=measure_bending_persistence(topology,
                            {**row,'endpoint_positions':endpoint_positions},capture.get('temporal_history'),label)
                except (KeyError,ValueError,RuntimeError,TypeError) as error:
                    row.update(status='invalid_or_incomplete_mesh_witness',reason=str(error))
                rows.append(row)
    return rows


def compact_diagnostics(rows):
    output=[]
    for row in rows:
        qualified=[c for c in row.get('components',[]) if c['meets_length_threshold']]
        connectivity=dict(Counter(c['connectivity'] for c in qualified))
        chains=[c for c in qualified if c['connectivity']=='open_chain']
        output.append({k:v for k,v in row.items() if k not in ('components','temporal_persistence')} | {
        'temporal_persistence':{k:v for k,v in row.get('temporal_persistence',{}).items() if k!='components'},
        'max_candidate_vertex_drift_m':max((c['max_vertex_drift_m'] for c in row.get('temporal_persistence',{}).get('components',[])),default=None),
        'max_candidate_bend_change_rad':max((c['max_bend_change_rad'] for c in row.get('temporal_persistence',{}).get('components',[])),default=None),
        'component_count':len(row.get('components',[])),
        'length_qualified_components':sum(c['meets_length_threshold'] for c in row.get('components',[])),
        'qualified_connectivity_counts':connectivity,
        'candidate_selection_status':'no_qualified_candidates' if not qualified else
            'single_open_chain_candidate' if len(qualified)==1 and len(chains)==1 else 'ambiguous_bending_components',
        'largest_component_total_edge_length_m':max((c['total_edge_length_m'] for c in row.get('components',[])),default=None),
        'longest_qualified_open_chain_m':max((c['total_edge_length_m'] for c in chains),default=None),
        'max_new_bend_rad':max((v for c in row.get('components',[]) for v in c['bend_increase_rad']),default=None)})
    return output


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--report',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--min-bend-deg',type=float,default=45);p.add_argument('--min-increase-deg',type=float,default=30)
    p.add_argument('--min-component-mm',type=float,default=10)
    a=p.parse_args();data=a.report.read_bytes()
    thresholds={'min_bend_rad':math.radians(a.min_bend_deg),'min_increase_rad':math.radians(a.min_increase_deg),
                'min_component_length_m':a.min_component_mm/1000}
    rows=analyze_report(json.loads(data),thresholds)
    atomic_write_json(a.output,{'report':str(a.report.resolve()),'report_sha256':hashlib.sha256(data).hexdigest(),
                              'thresholds':thresholds,'garments':rows})
    print(json.dumps({'output':str(a.output),'diagnostics':compact_diagnostics(rows)}))
