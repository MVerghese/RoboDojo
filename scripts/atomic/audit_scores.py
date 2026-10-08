#!/usr/bin/env python3
"""Recompute geometric scores from saved simulator states, optionally for new targets."""

import argparse
import json
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from task.atomic.geometry import evaluate_geometry


TARGET_FIELDS = {"expected", "tolerance", "angle_tolerance_rad", "margin", "half_extents", "min_overlap_fraction", "interior_boxes", "aperture_profile", "required_clearance_m"}


def _same_result(a,b):
    if isinstance(a,dict) and isinstance(b,dict):
        return a.keys()==b.keys() and all(_same_result(a[k],b[k]) for k in a)
    if isinstance(a,list) and isinstance(b,list):
        return len(a)==len(b) and all(_same_result(x,y) for x,y in zip(a,b))
    if type(a) in (float,int) and type(b) in (float,int):
        return bool(np.isclose(a,b,rtol=1e-7,atol=1e-9))
    return a==b


def audit_trajectories(rows):
    from task.atomic.trajectory import aggregate_path
    output={}
    for ident,row in rows.items():
        if not {'condition','samples','failures','complete','result'} <= row.keys():
            output[ident]={'status':'missing_raw_evidence'};continue
        result=aggregate_path(row['condition'],row['samples'],row['failures'],row['complete'])
        output[ident]={'status':'reproduced' if _same_result(result,row['result']) else 'score_mismatch',
                       'recorded_result':result,'condition':row['condition']}
    return output


def audit_flow(flow):
    if not flow:return None
    from task.atomic.flow import score_crossing
    rows={}
    for ident,row in flow['crossings'].items():
        provenance=row.get('source_exit_provenance',{})
        if not provenance.get('eligible') or not provenance.get('exited_while_held_and_tilted'):
            rows[ident]={'status':'missing_source_provenance'};continue
        result=score_crossing(flow['condition'],row['before'],row['after'])
        rows[ident]={'status':'reproduced' if _same_result(result,row['result']) else 'score_mismatch',
                     'recorded_result':result}
    return {'condition':flow['condition'],'crossings':rows,'sampling_failures':flow['failures']}


def apply_flow_validation(atomic, output):
    config=atomic.get('recognition') or {};raw=atomic.get('material_flow')
    audited=output.get('material_flow')
    if not raw or not audited or config.get('kind') not in ('fluid_material_transfer','rigid_material_transfer'):
        return
    from collections import Counter
    from task.atomic.material_validation import initial_fluid_witness,validate_flow_witness
    cohort=None
    if config['kind']=='fluid_material_transfer':
        initial=atomic.get('material_transfer_initial_state') or (atomic.get('interaction_evidence') or {}).get('initial_state')
        cohort=initial_fluid_witness(config,initial)
    statuses=Counter()
    for ident,row in audited['crossings'].items():
        if ident not in raw['crossings']:continue
        witness=validate_flow_witness(ident,raw['crossings'][ident],config,cohort,atomic.get('material_bounds'))
        row['source_witness']=witness;statuses[witness['status']]+=1
        if witness['status']=='inconsistent_evidence':
            row['numerical_reproduction_status']=row.get('numerical_reproduction_status',row['status'])
            row['status']='invalid_source_witness'
            row['reason']='retained source or crossing witnesses fail independent physical checks'
    audited['witness_summary']=dict(statuses)


def audit_material_bounds(bounds):
    from task.atomic.finite_material import validate_material_bound
    output={}
    for label,row in (bounds or {}).items():
        if row.get('status')=='unavailable':
            output[label]={'status':'unavailable','reason':row.get('reason')};continue
        try:
            radius=validate_material_bound(row)
            if row['label']!=label:raise ValueError('material map label differs from bound label')
            output[label]={'status':'consistent_evidence','enclosing_radius_m':radius,
                           'closed_oriented_mesh':row['closed_oriented_mesh']}
        except (KeyError,TypeError,ValueError,AttributeError) as error:
            output[label]={'status':'inconsistent_evidence','reason':str(error)}
    return output


def apply_surface_capture_validation(atomic,output):
    config=atomic.get('recognition') or {}
    if 'target_surface' not in config:return
    from task.atomic.strike_surfaces import validate_capture,validate_surface_event
    capture=atomic.get('target_surface_binding')
    output['target_surface_validation']=validate_capture(capture,config['target_surface'])
    output['target_surface_validation']['capture_status']=(capture or {}).get('status','absent')
    if (capture or {}).get('reason'):output['target_surface_validation']['reason']=capture['reason']
    event_name='impact' if config['kind']=='held_tool_strike' else 'contact'
    event=atomic.get('physical_events',{}).get(event_name)
    if event is not None:output['target_surface_contact_validation']=validate_surface_event(config,event,capture)


def apply_stage_success_validation(atomic,output):
    from task.atomic.completion_validation import validate_stage_success
    for ident,raw in atomic.get('geometry',{}).items():
        witness=validate_stage_success(atomic,raw)
        if witness['status']=='not_applicable' or ident not in output['conditions']:continue
        row=output['conditions'][ident];row['stage_success_witness']=witness
        if witness['status']=='inconsistent_evidence':
            row['numerical_reproduction_status']=row.get('numerical_reproduction_status',row['status'])
            row['status']='invalid_stage_success_witness'
            row['reason']='stage-success completion flags, physical gate, lift bound or measurement clock contradict qualification'


def audit_selection(selection):
    if not selection:return None
    binding_ok = True
    binding_error = None
    definition = selection.get('definition', {}).get('candidates')
    if isinstance(definition, dict):
        try:
            from task.atomic.selection import candidates_from_inventory
            binding = selection['candidate_binding']
            labels, rejected = candidates_from_inventory(definition, binding['inventory'])
            binding_ok = (binding['kind'] == 'initial_layout_query' and binding['query'] == definition
                          and labels == binding['labels'] and rejected == binding['rejected']
                          and set(labels) == set(selection['snapshot']))
        except (ValueError, KeyError, TypeError) as error:
            binding_ok = False
            binding_error = str(error)
    candidates={}
    for label,rows in selection['snapshot'].items():
        candidates[label]={}
        for ident,row in rows.items():
            result=evaluate_geometry(row['condition'],row['measured_state'],row.get('reference_state')).as_dict()
            candidates[label][ident]={'status':'reproduced' if _same_result(result,row['result']) else 'score_mismatch',
                                      'recorded_result':result}
    eligible=[label for label,rows in candidates.items() if all(r['recorded_result']['passed'] for r in rows.values())]
    target_status='resolved' if len(eligible)==1 else 'ambiguous_target' if eligible else 'no_matching_target'
    observed=selection.get('observed');passed=None
    if observed and len(observed['contacts'])==1 and target_status=='resolved':
        passed=observed['contacts'][0]['label']==eligible[0]
    matches=(binding_ok and eligible==selection['eligible_candidates'] and target_status==selection['target_status']
             and passed==selection['passed'] and all(r['status']=='reproduced' for rows in candidates.values() for r in rows.values()))
    return {'status':'reproduced' if matches else 'score_mismatch','candidates':candidates,
            'candidate_binding_reproduced':binding_ok,'candidate_binding_error':binding_error,
            'eligible_candidates':eligible,'target_status':target_status,'passed':passed,'observed':observed}


def apply_recognition_validation(atomic, output):
    config=atomic.get('recognition') or {}
    if config.get('kind') == 'contact_constrained_twist':
        from task.atomic.twist_validation import validate_twist,validate_twist_diagnostic
        witness=validate_twist(atomic)
        output['twist_rotation_diagnostic']=validate_twist_diagnostic(atomic)
        invalid={'rotation'} if witness['status']=='inconsistent_evidence' else set()
    elif config.get('kind') == 'held_tool_landmark_contact' and ('target_candidates' in config or 'target_surface' in config):
        from task.atomic.target_regions import validate_target_region_witness
        event=atomic.get('physical_events',{}).get('contact')
        checks=validate_target_region_witness(config,event) if event is not None and 'target_candidates' in config else {}
        unavailable=[]
        if event is not None and 'target_surface' in config:
            from task.atomic.strike_surfaces import validate_surface_event
            surface=validate_surface_event(config,event,atomic.get('target_surface_binding'))
            checks.update(surface.get('checks',{}));unavailable.extend(surface.get('unavailable',[]))
        failed=[key for key,value in checks.items() if not value]
        witness={'status':'unobserved' if event is None else 'inconsistent_evidence' if failed else 'partial_evidence' if unavailable else 'consistent_evidence',
                 'checks':checks,'failed_checks':failed,'unavailable':unavailable}
        invalid={'contact'} if failed else set()
    elif config.get('kind') == 'held_tool_strike':
        from scripts.atomic.validate_strike_evidence import validate_strike
        witness = validate_strike(atomic)
        window_errors = {'event_order', 'elapsed_steps', 'same_arm_hold_interval',
                         'retraction_rise_from_raw_poses', 'contiguous_retraction_samples'}
        window_errors.update(name for name in witness.get('failed_checks',[]) if name.startswith('target_region_'))
        window_errors.update(name for name in witness.get('failed_checks',[]) if name.startswith('surface_'))
        invalid = {'impact', 'retracted', 'strike'} if window_errors.intersection(witness.get('failed_checks', [])) else set()
    else:
        from task.atomic.recognition_validation import validate_recognition_window
        witness = validate_recognition_window(atomic)
        if witness['status'] == 'not_applicable':
            return
        invalid = set(witness.get('invalid_event_names', []))
    output['recognition_witness'] = witness
    if config.get('kind')=='supported_release':
        from task.atomic.settling_validation import validate_settling
        motion=validate_settling(atomic);output['settling_witness']=motion
        if motion['status']=='inconsistent_evidence':
            invalid.add('settled')
            witness['status']='inconsistent_evidence'
            witness.setdefault('failed_checks',[]).extend(motion['failed_checks'])
            witness['invalid_event_names']=sorted(set(witness.get('invalid_event_names',[]))|{'settled'})
    if not invalid:
        return
    conditions = {c['id']: c for c in atomic.get('conditions', [])}
    for ident, row in output['conditions'].items():
        event = conditions.get(ident, {}).get('event', {})
        if event.get('kind') == 'recognition_event' and event['name'] in invalid:
            row['numerical_reproduction_status'] = row.get('numerical_reproduction_status', row['status'])
            row['status'] = 'invalid_recognition_window'
            row['reason'] = 'event witnesses span incompatible physical attempts or fail boundary checks'
    for row in output.get('trajectories', {}).values():
        c = row.get('condition', {})
        if not any(c.get(key, {}).get('kind') == 'recognition_event'
                   and c[key]['name'] in invalid for key in ('start_event', 'end_event')):
            continue
        row['numerical_reproduction_status'] = row.get('numerical_reproduction_status', row['status'])
        row['status'] = 'invalid_recognition_window'
        row['reason'] = 'path boundary witnesses span incompatible physical attempts'


def validate_cached_recognition(report, scores):
    """Check raw physical witnesses even when arithmetic audits are cached."""
    raw = {}
    for native in report.get('native_results', []):
        details = native.get('details', {})
        for episode, detail in (details.items() if isinstance(details, dict) else enumerate(details)):
            for stage in [*detail.get('atomic_sequence', {}).get('stages', []),
                          *([detail['atomic']] if 'atomic' in detail else [])]:
                raw[(str(episode), stage['stage_id'])] = stage
    for score in scores:
        stage = raw.get((str(score['episode']), score['stage_id']))
        if stage is not None:
            apply_recognition_validation(stage, score)
            apply_flow_validation(stage, score)
            apply_support_validation(stage, score)
            apply_contact_validation(stage, score)
            apply_stage_success_validation(stage,score)
            from task.atomic.source_candidates import audit_source_candidates
            score['source_candidate_diagnostic']=audit_source_candidates(stage)
            apply_surface_capture_validation(stage,score)


def apply_contact_validation(atomic, output):
    """A reproduced point error cannot override a contradictory force witness."""
    from task.atomic.contact_validation import validate_contact_witness
    for ident, raw in atomic.get('geometry', {}).items():
        measurement = raw.get('condition', {}).get('measurement', {})
        if measurement.get('kind') not in ('contact_points','object_contact_points','contact_pose','object_contact_pose') or 'measured_state' not in raw:
            continue
        row = output['conditions'].get(ident)
        if row is None: continue
        witness = validate_contact_witness(raw.get('measurement_source'), measurement, raw['measured_state'])
        row['contact_witness'] = witness
        if witness['status'] == 'inconsistent_contact_evidence':
            row['numerical_reproduction_status'] = row.get('numerical_reproduction_status', row['status'])
            row['status'] = 'invalid_contact_witness'
            row['reason'] = 'retained force contacts, identity, coordinates or physical frame contradict the contact measurement'
    snapshots = {}
    def walk(value, path):
        if not isinstance(value, dict): return
        if value.get('kind') in ('contact_points','object_contact_points','contact_pose','object_contact_pose') and ('contacts' in value or 'contact_source' in value):
            snapshots[path] = validate_contact_witness(value)
            return
        for key, child in value.items():
            walk(child, path + '/' + key)
    for field in ('physical_events', 'interaction_evidence'):
        walk(atomic.get(field), field)
    if snapshots: output['contact_witnesses'] = snapshots
    if atomic.get('selection') and output.get('selection'):
        from task.atomic.contact_validation import validate_selection_contact_witness
        selection=output['selection'];witness=validate_selection_contact_witness(atomic['selection'])
        selection['contact_witness']=witness
        if witness['status']=='inconsistent_contact_evidence':
            selection['numerical_reproduction_status']=selection.get('numerical_reproduction_status',selection['status'])
            selection['status']='invalid_selection_witness'
            selection['reason']='retained selected candidate, force, arm or timing contradicts the selection observation'


def apply_support_validation(atomic, output):
    from task.atomic.support_validation import validate_support_witness
    for ident, raw in atomic.get('geometry', {}).items():
        if raw.get('condition', {}).get('expected') != 'on_top' or 'measured_state' not in raw:
            continue
        row = output['conditions'].get(ident)
        if row is None: continue
        witness = validate_support_witness(raw['measured_state'])
        row['support_witness'] = witness
        if witness['status'] == 'inconsistent_support_evidence':
            row['numerical_reproduction_status'] = row.get('numerical_reproduction_status', row['status'])
            row['status'] = 'invalid_support_witness'
            row['reason'] = 'retained support body/force signs do not match the recorded support flag'


def audit_atomic(atomic, variant=None):
    if variant and variant.get("stage_id") != atomic["stage_id"]:
        raise ValueError("counterfactual variant must use the recorded stage")
    overrides = variant.get("conditions", {}) if variant else {}
    conditions = {c["id"]: c for c in atomic.get("conditions", [])}
    if conditions and set(overrides) - set(conditions):
        raise ValueError("counterfactual variant refers to unknown conditions")
    for condition_id, override in overrides.items():
        # A reusable live-run variant may repeat immutable selector/axis fields.
        # Repetition is safe only if it equals the recorded definition exactly.
        original = conditions.get(condition_id, {})
        if any(key not in TARGET_FIELDS and (key not in original or value != original[key])
               for key, value in override.items()):
            raise ValueError("changing measurements, landmarks, or events requires a new simulator run")
    rows = {}
    for condition_id, item in atomic.get("geometry", {}).items():
        if "measured_state" not in item or "condition" not in item:
            rows[condition_id] = {"status": "missing_raw_evidence"}
            continue
        condition = item["condition"]
        measured, reference = item["measured_state"], item.get("reference_state")
        reproduced = evaluate_geometry(condition, measured, reference).as_dict()
        saved = item["result"]
        matches = reproduced["passed"] == saved["passed"] and all(
            np.isclose(reproduced[k], saved[k], rtol=1e-7, atol=1e-9)
            for k in ("error", "tolerance")
        ) and reproduced["components"].keys() == saved["components"].keys() and all(
            np.isclose(value, saved["components"][key], rtol=1e-7, atol=1e-9)
            for key, value in reproduced["components"].items()
        )
        changed = {**condition, **overrides.get(condition_id, {})}
        rows[condition_id] = {
            "status": "reproduced" if matches else "score_mismatch",
            'kind': condition['kind'], 'slot': condition['slot'], 'condition': condition,
            "recorded_result": reproduced,
            "rescored_result": evaluate_geometry(changed, measured, reference).as_dict(),
            "policy_action_index": item.get("policy_action_index"),
            "measurement_source": item.get("measurement_source"),
            "ee_contact_proxy": item.get("ee_contact_proxy", False),
        }
    for condition_id in conditions.keys() - rows.keys():
        failure = atomic.get('measurement_failures', {}).get(condition_id)
        rows[condition_id] = {**(failure or {"status": "event_not_observed"}),
                              'kind': conditions[condition_id]['kind'], 'slot': conditions[condition_id]['slot']}
    output = {
        "stage_id": atomic["stage_id"], "instruction": atomic.get("instruction"),
        "action_success": atomic["action_success"],
        "geometry_coverage": atomic["geometry_coverage"],
        "counterfactual_instruction": variant.get("instruction") if variant else None,
        "interpretation": "Rescoring a saved outcome changes the target, not the policy behavior.",
        "conditions": rows,
        'required':atomic.get('required',True),
        'choice_status':atomic.get('choice_status'),
        'family': atomic.get('family'), 'recognition_status': atomic.get('recognition_status'),
        'interaction_observed': atomic.get('interaction_observed'),
        'trajectories': audit_trajectories(atomic.get('trajectories',{})),
        'selection': audit_selection(atomic.get('selection')),
        'material_flow': audit_flow(atomic.get('material_flow')),
        'material_bounds':audit_material_bounds(atomic.get('material_bounds')),
    }
    from task.atomic.source_candidates import audit_source_candidates
    output['source_candidate_diagnostic']=audit_source_candidates(atomic)
    apply_surface_capture_validation(atomic,output)
    apply_recognition_validation(atomic, output)
    apply_flow_validation(atomic, output)
    apply_support_validation(atomic, output)
    apply_contact_validation(atomic, output)
    apply_stage_success_validation(atomic,output)
    if atomic.get("closest_approach"):
        alternate = {**atomic, "geometry": atomic["closest_approach"], "closest_approach": {}}
        output["closest_approach"] = audit_atomic(alternate, variant)["conditions"]
    return output


def audit_report(report, variant=None):
    rows = []
    for native in report.get("native_results", []):
        details = native.get("details", {})
        for episode, detail in (details.items() if isinstance(details, dict) else enumerate(details)):
            if "atomic" in detail:
                rows.append({"episode": str(episode), "layout_id": detail["layout_id"],
                             **audit_atomic(detail["atomic"], variant)})
            for atomic in detail.get("atomic_sequence", {}).get("stages", []):
                rows.append({"episode": str(episode), "layout_id": detail["layout_id"],
                             "reached": atomic["reached"], **audit_atomic(atomic, variant)})
    return {"atomic_episodes": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--variant", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    variant = json.loads(args.variant.read_text()) if args.variant else None
    audit = audit_report(json.loads(args.report.read_text()), variant)
    args.output.write_text(json.dumps(audit, indent=2) + "\n")
    print(args.output)


if __name__ == "__main__":
    main()
