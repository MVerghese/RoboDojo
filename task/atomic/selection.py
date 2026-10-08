"""Score the first contacted referent against an immutable candidate snapshot."""
from copy import deepcopy
from collections import deque

from task.atomic.contacts import ContactUnavailable
from task.atomic.geometry import evaluate_geometry


def validate_candidate_query(query):
    required = {'prefix', 'category', 'min', 'max'}
    if (not isinstance(query, dict) or not required <= set(query)
            or set(query) - required - {'model_names', 'exclude_labels'}):
        raise ValueError('candidate query needs prefix/category/min/max and optional explicit filters')
    if not isinstance(query['prefix'], str) or not query['prefix'] or query['category'] not in ('rigid', 'geometry', 'articulation'):
        raise ValueError('candidate query requires a nonempty prefix and a supported physical object category')
    if (type(query['min']) is not int or type(query['max']) is not int
            or not 2 <= query['min'] <= query['max'] <= 256):
        raise ValueError('candidate query requires bounded counts between 2 and 256')
    for field in ('model_names', 'exclude_labels'):
        if field in query:
            values = query[field]
            if (not isinstance(values, list) or not values
                    or any(not isinstance(v, str) or not v for v in values)
                    or len(set(values)) != len(values)):
                raise ValueError(field + ' must contain distinct nonempty strings')


def candidates_from_inventory(query, inventory):
    """Deterministic binding from retained initial-layout identities, not prose."""
    validate_candidate_query(query)
    labels, names, rejected = [], set(), []
    seen = set()
    for row in sorted(inventory, key=lambda r: r['label']):
        label = row['label']
        if (not isinstance(label, str) or not label.startswith(query['prefix'])
                or label in seen or not isinstance(row.get('instance'), str) or not row['instance']):
            raise ValueError('candidate inventory has an invalid/duplicate label or unresolved instance')
        seen.add(label)
        if (label not in query.get('exclude_labels', []) and row['category'] == query['category']
                and 'model_names' in query and not row.get('model_name')):
            raise ValueError('candidate model filter cannot use missing initial asset metadata')
        reason = ('excluded_label' if label in query.get('exclude_labels', []) else
                  'different_category' if row['category'] != query['category'] else
                  'different_model' if 'model_names' in query and row.get('model_name') not in query['model_names'] else None)
        if reason:
            rejected.append({'label': label, 'reason': reason})
            continue
        if row['instance'] in names:
            raise ValueError('candidate labels alias the same physical instance')
        names.add(row['instance'])
        labels.append(label)
    if not query['min'] <= len(labels) <= query['max']:
        raise ValueError('candidate query resolved outside its reviewed count bounds')
    return labels, rejected


def resolve_candidates(candidates, env, env_idx):
    if isinstance(candidates, list):
        return list(candidates), {'kind': 'explicit_labels', 'labels': list(candidates)}
    lm = env.scene_manager.layout_manager
    inventory = []
    for label in lm.get_labels_by_prefix(prefix=candidates['prefix'], env_idx=env_idx):
        instance = lm.get_instance_name(env_idx=env_idx, label=label)
        metadata = lm.get_instance_metadata(env_idx=env_idx, label=label) or {}
        inventory.append({'label': label, 'instance': instance,
            'category': lm.instance_type_by_env[env_idx].get(instance),
            'model_name': metadata.get('model_name'), 'model_id': metadata.get('model_id')})
    labels, rejected = candidates_from_inventory(candidates, inventory)
    return labels, {'kind': 'initial_layout_query', 'query': deepcopy(candidates),
                    'inventory': inventory, 'labels': labels, 'rejected': rejected}


def validate_selection(c,validate_condition):
    fields={'candidates','conditions','arm','min_finger_bodies','min_contact_steps'}
    if not isinstance(c,dict) or not fields<=set(c) or set(c)-fields-{'role'}:
        raise ValueError('selection needs candidates, conditions and an explicit contact rule')
    if 'role' in c:
        from task.atomic.spec import FAMILIES
        role=c['role']
        if (not isinstance(role,dict) or set(role)!={'family','slot'}
                or role['family'] not in FAMILIES or not isinstance(role['slot'],str) or not role['slot'].strip()):
            raise ValueError('selection role requires a known action family and nonempty slot')
    labels=c['candidates']
    if isinstance(labels, dict):
        validate_candidate_query(labels)
    elif not isinstance(labels,list) or len(labels)<2 or any(not isinstance(l,str) or not l or l=='@candidate' for l in labels) or len(set(labels))!=len(labels):
        raise ValueError('selection requires at least two distinct explicit candidate labels')
    if not isinstance(c['arm'],str) or not c['arm']:
        raise ValueError('selection contact arm must be named or any')
    if type(c['min_finger_bodies']) is not int or c['min_finger_bodies']<1 or type(c['min_contact_steps']) is not int or c['min_contact_steps']<2:
        raise ValueError('selection requires distinct sustained physical contact samples')
    conditions=c['conditions']
    if not isinstance(conditions,list) or not conditions or len({v.get('id') for v in conditions})!=len(conditions):
        raise ValueError('selection needs unique geometric condition IDs')
    for condition in conditions:
        validate_condition(condition)
        if 'role' in c and condition['slot']!=c['role']['slot']:
            raise ValueError('selection condition slot must match its declared role')
        if ('event' in condition or condition['measurement'].get('label')!='@candidate'
                or condition['measurement']['kind'] not in ('object_pose','object_position','object_center_pose','object_center_position')):
            raise ValueError('selection conditions measure @candidate object frames/points at activation; no outcome events')
        if condition.get('expected')=='on_top':
            raise ValueError('selection supported-on needs historical support evidence and is not implemented')
        if condition.get('reference',{}).get('label')=='@candidate':
            raise ValueError('selection reference must identify an independent landmark')


class SelectionObserver:
    def __init__(self,session):
        self.session=session; self.c=session.stage.selection
        self.labels, self.binding = resolve_candidates(self.c['candidates'], session.env, session.env_idx)
        self.snapshot={}; self.holds={}; self.hold_histories={}; self.last_step=None; self.observed=None
        self.candidate_roots={}
        lm=session.env.scene_manager.layout_manager
        for label in self.labels:
            root=None
            if hasattr(lm,'get_scene_object') and hasattr(lm,'get_instance_name'):
                instance=lm.get_instance_name(env_idx=session.env_idx,label=label)
                obj=lm.get_scene_object(session.env_idx,instance)
                root=getattr(obj,'usd_prim_path',None) or getattr(obj,'prim_path',None)
                if not isinstance(root,str) or not root.startswith('/'):
                    raise RuntimeError('selection candidate needs an actual absolute scene root: '+label)
            self.candidate_roots[label]=root
        resolved=[root for root in self.candidate_roots.values() if root is not None]
        if len(resolved)!=len(set(resolved)):
            raise RuntimeError('selection labels alias the same actual scene root')
        for label in self.labels:
            rows={}
            for definition in self.c['conditions']:
                condition=deepcopy(definition)
                condition['measurement']['label']=label
                measured,source,reference,ref_source=session._resolve_condition(condition)
                state=deepcopy(measured) if isinstance(measured,dict) else measured.tolist()
                ref=deepcopy(reference) if isinstance(reference,dict) else reference.tolist() if reference is not None else None
                rows[condition['id']]={'condition':condition,'measured_state':state,'reference_state':ref,
                    'measurement_source':deepcopy(source),'reference_source':deepcopy(ref_source),
                    'result':evaluate_geometry(condition,state,ref).as_dict()}
            self.snapshot[label]=rows
        self.eligible=[label for label,rows in self.snapshot.items() if all(row['result']['passed'] for row in rows.values())]
        self.target_status='resolved' if len(self.eligible)==1 else 'ambiguous_target' if self.eligible else 'no_matching_target'
        contacts=getattr(session.env,'_atomic_contacts',None)
        self.snapshot_step=contacts.steps if contacts is not None else None

    def observe(self):
        if self.observed is not None:return
        contacts=getattr(self.session.env,'_atomic_contacts',None)
        if contacts is None:raise RuntimeError('selection scoring requires actual contact reports')
        if contacts.errors:raise RuntimeError('selection cannot use a broken contact callback')
        step=contacts.steps
        if step==self.last_step:return
        if self.last_step is not None and step!=self.last_step+1:
            self.holds.clear();self.hold_histories.clear()
        self.last_step=step; qualifying=[]
        for label in self.labels:
            try:
                _,source=contacts.resolve({'kind':'contact_points','label':label,'arm':self.c['arm'],
                    'min_finger_bodies':self.c['min_finger_bodies']},self.session.env_idx)
            except ContactUnavailable:
                self.holds.pop(label,None);self.hold_histories.pop(label,None);continue
            previous=self.holds.get(label)
            count=previous[1]+1 if previous and previous[0]==source['resolved_arm'] else 1
            self.holds[label]=(source['resolved_arm'],count)
            capacity=min(256,self.c['min_contact_steps'])
            if count==1:self.hold_histories[label]=deque(maxlen=capacity)
            history=self.hold_histories[label];history.append(deepcopy(source))
            if count>=self.c['min_contact_steps']:
                qualifying.append({'label':label,'contact_source':deepcopy(source),'contact_steps':count,
                    'contact_history':{'sources':list(history),'capacity':capacity,
                        'retained_count':len(history),'observed_count':count,'truncated':len(history)<count}})
        if qualifying:
            self.observed={'physics_step':step,'policy_action_index':self.session._action_index(),'contacts':qualifying,
                'status':'selected' if len(qualifying)==1 else 'ambiguous_contact',
                'passed':(qualifying[0]['label']==self.eligible[0]) if len(qualifying)==1 and self.target_status=='resolved' else None}

    def summary(self):
        return {'definition':deepcopy(self.c),'candidate_binding':deepcopy(self.binding),'snapshot_physics_step':self.snapshot_step,
            'candidate_roots':deepcopy(self.candidate_roots),'environment_index':self.session.env_idx,
            'snapshot':deepcopy(self.snapshot),'eligible_candidates':list(self.eligible),'target_status':self.target_status,
            'observed':deepcopy(self.observed),'status':self.observed['status'] if self.observed else 'contact_not_observed',
            'passed':self.observed['passed'] if self.observed else None}
