"""Pose conditioning uses real contacts for position and named physical axes."""
from copy import deepcopy
import math
from types import SimpleNamespace as NS
import unittest
import numpy as np
from task.atomic.geometry import evaluate_geometry
from task.atomic.session import AtomicSession
from task.atomic.spec import _validate_condition, _validate_selector
from task.atomic.contact_validation import validate_contact_witness
from test_atomic_contact_validation import sample


def selector():
    return {'kind':'contact_pose','label':'object','arm':'right','min_finger_bodies':2,
        'orientation_frame':{'kind':'robot_ee_pose','arm':'contacting','label':'object','min_finger_bodies':2}}


def condition():
    return {'id':'grasp_pose','slot':'grasp_region','kind':'pose','measurement':selector(),
        'expected':{'position':[0,0,0],'orientation':[1,0,0,0]},'tolerance':.02,'angle_tolerance_rad':.3}


def runtime():
    _,_,source=sample()
    # Exercise the real contact resolver and session frame resolver together.
    from task.atomic.contacts import PhysXContacts
    backend=PhysXContacts.__new__(PhysXContacts);backend.rows=deepcopy(source['contacts'])
    backend.errors=[];backend.steps=12;backend.reports=5
    backend.fingers={k:tuple(v) for k,v in source['finger_body_bindings'].items()}
    lm=NS(get_instance_name=lambda i,label:'object',get_scene_object=lambda i,name:NS(usd_prim_path='/env/object'))
    robot=NS(arm_name='right',ee_link_name='palm')
    env=NS(_atomic_contacts=backend,scene_manager=NS(layout_manager=lm),
        sim=NS(scene=NS(env_origins=np.array([[1.,2.,3.]]))),
        robot_manager=NS(robot_list=[robot],get_real_endpose=lambda *a,**kw:{0:np.array([8,9,10,1,0,0,0])}))
    backend.env=env;session=AtomicSession.__new__(AtomicSession);session.env=env;session.env_idx=0
    return session,backend


class ContactPoseTests(unittest.TestCase):
    def test_schema_requires_a_named_live_contacting_arm_or_contacting_object_frame(self):
        _validate_condition(condition())
        for change in ('missing','nearest','wrong_label','weak_fingers','frozen','wrong_object'):
            s=selector()
            if change=='missing':s.pop('orientation_frame')
            elif change=='nearest':s['orientation_frame']['arm']='nearest'
            elif change=='wrong_label':s['orientation_frame']['label']='other'
            elif change=='weak_fingers':s['orientation_frame']['min_finger_bodies']=1
            elif change=='frozen':s['orientation_frame']['time']='stage_start'
            else:s['kind']='object_contact_pose';s['other_label']='target';s.pop('arm');s.pop('min_finger_bodies')
            with self.subTest(change=change),self.assertRaises(ValueError):_validate_selector(s,'measurement')
        plain=condition();plain['measurement']={'kind':'contact_points','label':'object'}
        with self.assertRaisesRegex(ValueError,'orientation'):_validate_condition(plain)

    def test_runtime_positions_come_from_contacts_even_with_distant_end_effector(self):
        session,_=runtime();measured,source=session._resolve_with_source(selector())
        np.testing.assert_allclose(measured['points'],[[.01,0,0],[-.01,0,0]])
        self.assertEqual(source['orientation_frame_pose'][:3],[8,9,10])
        result=evaluate_geometry(condition(),measured)
        self.assertTrue(result.passed);self.assertAlmostEqual(result.components['position_m'],.01)
        self.assertEqual(validate_contact_witness(source,selector(),measured)['status'],'consistent_contact_evidence')

    def test_pose_components_keep_worst_translation_when_orientation_dominates_all_points(self):
        measured={'position':[.015,0,0],'points':[[.01,0,0],[.02,0,0]],
            'orientation':[math.cos(.1),0,0,math.sin(.1)],'oriented_contact_frame':True}
        c=condition();c['tolerance']=.1;c['angle_tolerance_rad']=.4
        result=evaluate_geometry(c,measured)
        self.assertAlmostEqual(result.error,.5);self.assertAlmostEqual(result.components['position_m'],.02)
        self.assertAlmostEqual(result.components['orientation_rad'],.2)
        measured.pop('oriented_contact_frame')
        with self.assertRaisesRegex(ValueError,'explicit contact frame'):evaluate_geometry(c,measured)

    def test_wrong_link_arm_step_orientation_and_position_are_detected_independently(self):
        session,_=runtime();measured,original=session._resolve_with_source(selector())
        for change in ('arm','link','step','orientation','position'):
            source=deepcopy(original);value=deepcopy(measured)
            if change=='arm':source['orientation_frame_source']['resolved_arm']='left'
            elif change=='link':source['orientation_frame_source']['ee_link_name']=None
            elif change=='step':source['orientation_frame_source']['physics_step']=11
            elif change=='orientation':value['orientation']=[0,0,0,1]
            else:value['points'][0][0]=.5
            with self.subTest(change=change):
                self.assertEqual(validate_contact_witness(source,selector(),value)['status'],'inconsistent_contact_evidence')

    def test_named_arm_is_preserved_during_two_arm_contact(self):
        session,backend=runtime();backend.fingers['/env/left']=(0,'left')
        row=deepcopy(backend.rows[0]);row['actor0']='/env/left';row['collider0']='/env/left/shape'
        backend.rows.extend([row]*4)
        measured,source=session._resolve_with_source(selector())
        self.assertEqual(source['orientation_frame_source']['resolved_arm'],'right')
        self.assertEqual(source['contact_source']['resolved_arm'],'right')

    def test_relative_orientation_and_cached_audit_retain_physical_frame_validation(self):
        from scripts.atomic.audit_scores import apply_contact_validation
        session,_=runtime();measured,source=session._resolve_with_source(selector())
        c=condition();c['kind']='relative_orientation';c['expected']=[1,0,0,0]
        result=evaluate_geometry(c,measured,[0,0,0,1,0,0,0])
        self.assertAlmostEqual(result.components['orientation_rad'],0.)
        stage={'geometry':{'grasp_pose':{'condition':c,'measured_state':measured,'measurement_source':source}}}
        scores={'conditions':{'grasp_pose':{'status':'reproduced'}}}
        source['orientation_frame_source']['physics_step']=11
        apply_contact_validation(stage,scores)
        row=scores['conditions']['grasp_pose']
        self.assertEqual(row['status'],'invalid_contact_witness')
        self.assertEqual(row['numerical_reproduction_status'],'reproduced')

    def test_object_pair_contact_pose_uses_first_object_axes_and_checks_pair_force(self):
        session,backend=runtime();lm=session.env.scene_manager.layout_manager
        lm.get_instance_name=lambda i,label:label
        lm.get_scene_object=lambda i,name:NS(usd_prim_path='/env/'+name)
        lm.get_instance_pose=lambda env_idx,label:(np.zeros(3),np.array([math.cos(.2),0,math.sin(.2),0]))
        for row in backend.rows:
            row['actor0']='/env/tool';row['collider0']='/env/tool/tip'
            row['actor1']='/env/target';row['collider1']='/env/target/top'
        s={'kind':'object_contact_pose','label':'tool','other_label':'target',
           'orientation_frame':{'kind':'object_pose','label':'tool'}}
        _validate_selector(s,'measurement');measured,source=session._resolve_with_source(s)
        self.assertEqual(validate_contact_witness(source,s,measured)['status'],'consistent_contact_evidence')
        source['contact_source']['contacts'][0]['impulse']=[0,0,0]
        self.assertEqual(validate_contact_witness(source,s,measured)['status'],'inconsistent_contact_evidence')

if __name__=='__main__':unittest.main()
