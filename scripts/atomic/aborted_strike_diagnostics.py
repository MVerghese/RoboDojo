"""Retained impact conditioning on interrupted attempts; never successful-strike scores."""
from copy import deepcopy
from scripts.atomic.validate_strike_evidence import validate_strike


def audit_aborted_strikes(stage):
    if (stage.get('recognition') or {}).get('kind')!='held_tool_strike':return []
    from scripts.atomic.audit_scores import audit_atomic
    results=[]
    for attempt in stage.get('aborted_recognition_attempts',[]):
        impact=attempt.get('physical_events',{}).get('impact')
        if impact is None:continue
        snapshot=deepcopy(stage);snapshot.update(aborted_recognition_attempts=[],
            action_success=False,physical_events=deepcopy(attempt['physical_events']),
            geometry=deepcopy(attempt.get('geometry',{})),trajectories={})
        snapshot['conditions']=[c for c in stage.get('conditions',[]) if c.get('event')=={'kind':'recognition_event','name':'impact'}]
        witness=validate_strike(snapshot,impact_only=True)
        binding=(type(attempt.get('attempt_index')) is int and attempt['attempt_index']==impact.get('attempt_index')
            and type(impact.get('physics_step')) is int and type(attempt.get('aborted_physics_step')) is int
            and attempt['aborted_physics_step']>=impact['physics_step'])
        if not binding:
            witness['status']='inconsistent_evidence';witness.setdefault('failed_checks',[]).append('aborted_impact_attempt_clock_binding')
            witness['metrics']={}
        try:score=audit_atomic(snapshot)
        except (KeyError,TypeError,ValueError,IndexError,AttributeError):
            score={'conditions':{}};witness['status']='inconsistent_evidence'
            witness.setdefault('failed_checks',[]).append('aborted_impact_geometry_fields');witness['metrics']={}
        conditions={}
        for ident,row in score['conditions'].items():
            raw=snapshot['geometry'].get(ident,{})
            metadata=(raw.get('event_evidence')==impact and type(raw.get('measurement_physics_step')) is int
                and raw['measurement_physics_step']==impact.get('physics_step'))
            valid=witness['status'] in ('consistent_evidence','partial_evidence') and metadata and row['status']=='reproduced'
            contact=row.get('contact_witness') or {}
            conditions[ident]={'status':('partial_evidence' if contact.get('status')=='partial_contact_evidence' else row['status']) if valid else 'invalid_or_missing_impact_geometry',
                'kind':row.get('kind'),'components':row.get('recorded_result',{}).get('components',{}) if valid else {}}
        surface=score.get('target_surface_contact_validation') or {}
        results.append({'attempt_index':attempt.get('attempt_index'),'reason':attempt.get('reason'),
            'impact_physics_step':impact.get('physics_step'),'abort_physics_step':attempt.get('aborted_physics_step'),
            'impact_validation':witness,'surface_validation':surface,'conditions':conditions,
            'scope':'interrupted attempt impact diagnostics only; excluded from completed-strike and main conditioning summaries'})
    return results
