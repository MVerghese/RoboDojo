"""Score the first contacted referent against an immutable candidate snapshot."""
from copy import deepcopy

from task.atomic.contacts import ContactUnavailable
from task.atomic.geometry import evaluate_geometry


def validate_selection(c,validate_condition):
    fields={'candidates','conditions','arm','min_finger_bodies','min_contact_steps'}
    if not isinstance(c,dict) or set(c)!=fields:
        raise ValueError('selection needs candidates, conditions and an explicit contact rule')
    labels=c['candidates']
    if not isinstance(labels,list) or len(labels)<2 or any(not isinstance(l,str) or not l or l=='@candidate' for l in labels) or len(set(labels))!=len(labels):
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
        self.snapshot={}; self.holds={}; self.last_step=None; self.observed=None
        for label in self.c['candidates']:
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
        if self.last_step is not None and step!=self.last_step+1:self.holds.clear()
        self.last_step=step; qualifying=[]
        for label in self.c['candidates']:
            try:
                _,source=contacts.resolve({'kind':'contact_points','label':label,'arm':self.c['arm'],
                    'min_finger_bodies':self.c['min_finger_bodies']},self.session.env_idx)
            except ContactUnavailable:
                self.holds.pop(label,None);continue
            previous=self.holds.get(label)
            count=previous[1]+1 if previous and previous[0]==source['resolved_arm'] else 1
            self.holds[label]=(source['resolved_arm'],count)
            if count>=self.c['min_contact_steps']:
                qualifying.append({'label':label,'contact_source':deepcopy(source),'contact_steps':count})
        if qualifying:
            self.observed={'physics_step':step,'policy_action_index':self.session._action_index(),'contacts':qualifying,
                'status':'selected' if len(qualifying)==1 else 'ambiguous_contact',
                'passed':(qualifying[0]['label']==self.eligible[0]) if len(qualifying)==1 and self.target_status=='resolved' else None}

    def summary(self):
        return {'definition':deepcopy(self.c),'snapshot_physics_step':self.snapshot_step,
            'snapshot':deepcopy(self.snapshot),'eligible_candidates':list(self.eligible),'target_status':self.target_status,
            'observed':deepcopy(self.observed),'status':self.observed['status'] if self.observed else 'contact_not_observed',
            'passed':self.observed['passed'] if self.observed else None}
