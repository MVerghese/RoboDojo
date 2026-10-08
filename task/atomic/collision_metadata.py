"""Composed USD collision configuration; never a cooked PhysX face mapping."""
import math

SOURCE='composed USD mesh collision schemas and effective attributes'
SCOPE='USD collision configuration only; not cooked PhysX shape or face-index correspondence'


def _json_value(value):
    if value is None or type(value) in (str,bool,int):return value
    if type(value) is float:
        if not math.isfinite(value):raise ValueError('nonfinite collision attribute')
        return value
    try:return [_json_value(v) for v in value]
    except TypeError as error:raise ValueError('unsupported collision attribute value') from error


def describe_mesh_collision(prim,physics):
    """Read actual schema presence and effective/default values without inferring cooking."""
    collision=bool(prim.HasAPI(physics.CollisionAPI))
    mesh_collision=bool(prim.HasAPI(physics.MeshCollisionAPI))
    attributes={}
    for attribute in prim.GetAttributes():
        name=attribute.GetName()
        if (name in ('physics:collisionEnabled','physics:approximation') or
            name.startswith(('physxCollision:','physxConvexHullCollision:',
                             'physxConvexDecompositionCollision:','physxSDFMeshCollision:'))):
            attributes[name]={'value':_json_value(attribute.Get()),
                'authored':bool(attribute.HasAuthoredValueOpinion())}
    # API getters include schema fallbacks even when not listed as authored properties.
    for name,attribute in ([('physics:collisionEnabled',physics.CollisionAPI(prim).GetCollisionEnabledAttr())] if collision else [])+(
        [('physics:approximation',physics.MeshCollisionAPI(prim).GetApproximationAttr())] if mesh_collision else []):
        attributes[name]={'value':_json_value(attribute.Get()),'authored':bool(attribute.HasAuthoredValueOpinion())}
    return {'source':SOURCE,'scope':SCOPE,'prim_path':str(prim.GetPath()),
        'collision_api':collision,'mesh_collision_api':mesh_collision,
        'applied_schemas':list(prim.GetAppliedSchemas()),'attributes':attributes,
        'collision_enabled':attributes.get('physics:collisionEnabled',{}).get('value') if collision else None,
        'approximation':attributes.get('physics:approximation',{}).get('value') if mesh_collision else None}


def validate_collision_configuration(capture):
    """Check retained settings and root bindings; cannot reproduce the live USD stage."""
    configuration=(capture or {}).get('collision_configuration') or {}
    if configuration.get('status')!='observed_composed_usd':
        return {'status':'partial_evidence','reason':configuration.get('reason','collision_configuration_not_captured'),'scope':SCOPE}
    try:
        rows=configuration['meshes'];checks={
            'configuration_mesh_binding':len(rows)>0 and [r['relative_path'] for r in rows]==capture['mesh_paths']
                and all(r['prim_path']==capture['object_root']+'/'+r['relative_path'] for r in rows),
            'configuration_source':all(r['source']==SOURCE and r['scope']==SCOPE for r in rows),
            'configuration_values':all(type(r['collision_api']) is bool and type(r['mesh_collision_api']) is bool
                and (type(r['collision_enabled']) is bool if r['collision_api'] else r['collision_enabled'] is None)
                and (isinstance(r['approximation'],str) if r['mesh_collision_api'] else r['approximation'] is None)
                and all(type(a['authored']) is bool for a in r['attributes'].values()) for r in rows),
            'configuration_effective_values':all(
                (r['attributes'].get('physics:collisionEnabled',{}).get('value')==r['collision_enabled'] if r['collision_api'] else True)
                and (r['attributes'].get('physics:approximation',{}).get('value')==r['approximation'] if r['mesh_collision_api'] else True)
                for r in rows)}
    except (KeyError,TypeError,ValueError,AttributeError):checks={'configuration_fields':False}
    failed=[k for k,v in checks.items() if not v]
    return {'status':'inconsistent_evidence' if failed else 'consistent_retained_configuration',
        'failed_checks':failed,'checks':checks,'meshes':rows if not failed else [],'scope':SCOPE}
