"""Force snapshots are independently checked before reporting contact errors."""
from copy import deepcopy
from types import SimpleNamespace as NS
import unittest
import numpy as np
from task.atomic.contacts import PhysXContacts
from task.atomic.contact_validation import validate_contact_witness
from scripts.atomic.audit_scores import validate_cached_recognition


def sample():
    backend=PhysXContacts.__new__(PhysXContacts);backend.errors=[];backend.steps=12;backend.reports=5
    backend.fingers={'/env/f0':(0,'right'),'/env/f1':(0,'right')}
    lm=NS(get_instance_name=lambda i,label:'object',get_scene_object=lambda i,name:NS(usd_prim_path='/env/object'))
    backend.env=NS(scene_manager=NS(layout_manager=lm),sim=NS(scene=NS(env_origins=np.array([[1.,2.,3.]]))))
    backend.rows=[{'actor0':finger,'actor1':'/env/object','collider0':finger+'/shape',
        'collider1':'/env/object/shape','position_world':[x,2.,3.],
        'normal_world':[0.,0.,1.],'impulse':[0.,0.,.001],'force_report_physics_step':12}
        for finger,x in [('/env/f0',1.01),('/env/f1',.99)]]
    measurement={'kind':'contact_points','label':'object','arm':'right','min_finger_bodies':2}
    measured,source=backend.resolve(measurement,0)
    return measurement,measured,source


class ContactValidationTests(unittest.TestCase):
    def test_actual_resolver_retains_scope_bindings_force_and_world_origin(self):
        measurement,measured,source=sample()
        witness=validate_contact_witness(source,measurement,measured)
        self.assertEqual(witness['status'],'consistent_contact_evidence')
        self.assertEqual(source['object_root'],'/env/object')
        self.assertEqual(source['finger_body_bindings'],{'/env/f0':[0,'right'],'/env/f1':[0,'right']})
        np.testing.assert_allclose(measured['points'],[[.01,0,0],[-.01,0,0]])

    def test_reversed_actor_order_is_valid(self):
        measurement,measured,source=sample()
        for row in source['contacts']:
            for key in ('actor','collider'):row[key+'0'],row[key+'1']=row[key+'1'],row[key+'0']
            for key in ('normal_world','impulse'):row[key]=[-v for v in row[key]]
        self.assertEqual(validate_contact_witness(source,measurement,measured)['status'],'consistent_contact_evidence')

    def test_corrupt_force_object_finger_arm_environment_timing_and_coordinates_are_rejected(self):
        measurement,measured,original=sample()
        for corrupt in ('zero','object','finger','arm','environment','step','point','centroid','normal'):
            source=deepcopy(original);value=deepcopy(measured);row=source['contacts'][0]
            if corrupt=='zero':row['impulse']=[0,0,0]
            elif corrupt=='object':row['actor1']=row['collider1']='/env/other'
            elif corrupt=='finger':row['finger_body']='/env/f1'
            elif corrupt=='arm':row['arm']='left'
            elif corrupt=='environment':source['finger_body_bindings']['/env/f0']=[1,'right']
            elif corrupt=='step':row['force_report_physics_step']=11
            elif corrupt=='point':value['points'][0][0]=.4
            elif corrupt=='centroid':value['position'][0]=.4
            else:row['normal_world']=[0,0,2]
            with self.subTest(corrupt=corrupt):
                self.assertEqual(validate_contact_witness(source,measurement,value)['status'],'inconsistent_contact_evidence')

    def test_legacy_missing_binding_remains_partial_and_cannot_hide_zero_impulse(self):
        measurement,measured,source=sample()
        for key in ('object_root','object_contact_scope','environment_index','finger_body_bindings',
                    'environment_origin_world_m','force_eligibility'):source.pop(key)
        self.assertEqual(validate_contact_witness(source,measurement,measured)['status'],'partial_contact_evidence')
        source['contacts'][0]['impulse']=[0,0,0]
        self.assertEqual(validate_contact_witness(source,measurement,measured)['status'],'inconsistent_contact_evidence')

    def test_requested_two_fingers_cannot_be_faked_with_many_points_from_one(self):
        measurement,measured,source=sample()
        source['contacts']=[source['contacts'][0],source['contacts'][0]]
        source['finger_bodies']=['/env/f0'];source['min_finger_bodies']=1
        self.assertIn('requested_finger_count',validate_contact_witness(source,measurement)['failed_checks'])

    def test_cached_arithmetic_score_does_not_override_contradictory_raw_force(self):
        measurement,measured,source=sample();source['contacts'][0]['impulse']=[0,0,0]
        stage={'stage_id':'pick','geometry':{'contact':{'condition':{'measurement':measurement},
               'measured_state':measured,'measurement_source':source}}}
        report={'native_results':[{'details':{'0':{'atomic_sequence':{'stages':[stage]}}}}]}
        row={'episode':'0','stage_id':'pick','conditions':{'contact':{'status':'reproduced'}}}
        validate_cached_recognition(report,[row]);c=row['conditions']['contact']
        self.assertEqual(c['status'],'invalid_contact_witness')
        self.assertEqual(c['numerical_reproduction_status'],'reproduced')

if __name__=='__main__':unittest.main()
