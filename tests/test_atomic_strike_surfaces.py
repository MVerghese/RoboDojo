"""Live USD-region binding and independently retained force-contact counterexamples."""
from copy import deepcopy
import hashlib
from pathlib import Path
from types import SimpleNamespace as NS
import tempfile
import unittest
import numpy as np
import test_atomic_physical_runtime as runtime
import test_atomic_strike_validation as strike
from task.atomic.geometry import _rotation
from task.atomic.session import AtomicSession
from task.atomic.spec import AtomicStage
from task.atomic.strike_surfaces import (validate_definition,capture_surface,validate_capture,
    contact_surface,validate_surface_event)
from scripts.atomic.audit_scores import apply_recognition_validation


def fixture():
    triangle=[[[0,0,0],[1,0,0],[0,1,0]]]
    row={'asset_sha256':'a'*64,'scaled_bounds_m':[[0,0,0],[1,1,0]],
        'local_pose':[0,0,0,1,0,0,0],'calibration_id':'reviewed key collision component',
        'triangle_indices':[0],'expected_triangles_m':triangle,'landmark_root_pose':[.2,.2,0,1,0,0,0]}
    profile={'kind':'model_mesh_region','label':'target','surface_tag':'hit_0','mesh_paths':['collision'],
        'models':{'keys/00000':row},'distance_tolerance_m':.002,'require_contact':True}
    config={'kind':'held_tool_landmark_contact','label':'object','target_label':'target','arm':'any',
        'min_contact_steps':2,'min_impulse_ns':.005,'tool_radius_m':.04,'target_radius_m':.04,
        'tool_point':{'kind':'functional_point','label':'object','tag':'beat','type':'active'},
        'target_point':{'kind':'functional_point','label':'target','tag':'hit_0','type':'passive'},
        'target_surface':profile}
    capture={'status':'observed_model_mesh_region','label':'target','surface_tag':'hit_0',
        'environment_index':0,'physics_step':0,'frame':'scaled_object_root_local','length_unit':'metres',
        'source':'ObjectSurfaces.resolve selected scaled USD triangles anchored to actual task root',
        'object_root':'/env/target','model_frame_proof':{'model':'keys/00000','asset_sha256':'a'*64,
        'scaled_bounds_m':row['scaled_bounds_m']},'mesh_paths':['collision'],'triangle_indices':[0],
        'local_triangles_m':triangle,'root_pose_at_capture':[0,0,0,1,0,0,0],
        'landmark_pose_at_capture':[.2,.2,0,1,0,0,0]}
    return config,capture


def impact(config,capture):
    witness,mask=contact_surface(capture,config['target_surface'],[[.2,.2,.001]],
        [0,0,0,1,0,0,0],101,[1,2,3]);witness['selected_point_indices']=[0]
    return {'physics_step':101,'target_surface_witness':witness,'contact_points':[[.2,.2,.001]],
        'target_landmark_position':[.2,.2,0], 'held_contact':{'environment_index':0},
        'tool_target_contacts':[{'actor0':'/env/object/tip','actor1':'/env/target/collision',
            'position_world':[1.2,2.2,3.001],'force_report_physics_step':101,
            'impulse':[0,0,.01],'normal_world':[0,0,1]}]}


class StrikeSurfaceTests(unittest.TestCase):
    def test_definition_rejects_misbound_tags_paths_and_duplicate_faces(self):
        config,_=fixture();validate_definition(config['target_surface'],config)
        for edit in [lambda p:p.__setitem__('surface_tag','hit_1'),
            lambda p:p.__setitem__('mesh_paths',['../collision']),
            lambda p:p['models']['keys/00000'].__setitem__('triangle_indices',[0,0]),
            lambda p:p['models']['keys/00000'].pop('landmark_root_pose')]:
            broken=deepcopy(config);edit(broken['target_surface'])
            with self.assertRaises(ValueError):validate_definition(broken['target_surface'],broken)

    def test_live_file_scale_selected_mesh_and_landmark_binding_fail_closed(self):
        config,_=fixture();world=runtime.World();root=world.poses['target'];obj=NS()
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'keys.usdz';path.write_bytes(b'actual selected model');obj.usd_path=str(path)
            row=config['target_surface']['models']['keys/00000'];row['asset_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
            lm=world.env.scene_manager.layout_manager
            lm.get_instance_metadata=lambda **kw:{'model_name':'keys','model_id':0}
            lm.get_instance_name=lambda **kw:kw['label'];lm.get_scene_object=lambda **kw:obj
            lm.instance_type_by_env=[{'object':'rigid','target':'geometry'}]
            triangles=np.asarray(row['expected_triangles_m'],dtype=float).reshape(-1,3).copy()
            world.env._atomic_surfaces=NS(local_mesh_summary=lambda *args:{'bounds':row['scaled_bounds_m']},
                resolve=lambda *args,**kw:{'vertices':(triangles@_rotation(root[3:]).T+root[:3]).tolist(),
                    'triangles':[[0,1,2]],'prim_path':'/env/target','selected_mesh_paths':kw['mesh_paths']})
            session=NS(env=world.env,env_idx=0,_object_pose=lambda label:root,
                _resolve=lambda selector:np.r_[root[:3]+_rotation(root[3:])@np.array([.2,.2,0]),root[3:]])
            root[:]=[1,2,3,2**-.5,0,0,2**-.5]
            packet=capture_surface(session,config)
            self.assertEqual(validate_capture(packet,config['target_surface'])['status'],'consistent_evidence')
            triangles[0,0]=.1
            self.assertEqual(capture_surface(session,config)['status'],'unavailable')
            triangles[0,0]=0;path.write_bytes(b'changed asset')
            self.assertEqual(capture_surface(session,config)['status'],'unavailable')
            self.assertEqual(packet['status'],'observed_model_mesh_region')

    def test_landmark_proximity_does_not_accept_contact_off_the_actual_surface(self):
        config,_=fixture();world=runtime.World();world.hold();point=[.2,.2,.02]
        # Capture adapter is exercised separately above; here test the recognizer's physical gate.
        _,packet=fixture()
        from unittest.mock import patch
        original=world.contacts.resolve_object_pair
        def pair(selector,env_idx):
            _,data=original(selector,env_idx)
            data.update(measured_contact_points={'points':[point.copy()]},environment_origin_world_m=[0,0,0])
            return {'points':[point.copy()]},data
        world.contacts.resolve_object_pair=pair
        stage=AtomicStage.from_dict({'id':'contact','family':'touch_with_tool','instruction':'touch',
            'success_checks':[{'name':'is_test','args':{}}],'recognition':config})
        with patch('task.atomic.strike_surfaces.capture_surface',return_value=packet):
            session=AtomicSession(world.env,stage,0)
        session._resolve=lambda selector:np.array([.2,.2,0,1,0,0,0])
        world.tick(session,2);world.contacts.pairs=True
        self.assertFalse(world.tick(session));self.assertFalse(session.interaction_observed)
        world.contacts.pairs=False;world.tick(session);point[2]=.001;world.contacts.pairs=True
        self.assertTrue(world.tick(session));self.assertTrue(session.interaction_observed)
        self.assertAlmostEqual(session.summary()['physical_events']['contact']['target_surface_witness']['all_distances_m'][0],.001)

    def test_force_clock_impulse_actor_origin_and_geometry_contradictions_exclude_metrics(self):
        config,capture=fixture();event=impact(config,capture)
        self.assertEqual(validate_surface_event(config,event,capture)['status'],'consistent_evidence')
        for edit in [lambda e:e['tool_target_contacts'][0].__setitem__('impulse',[0,0,0]),
            lambda e:e['tool_target_contacts'][0].__setitem__('force_report_physics_step',100),
            lambda e:e['tool_target_contacts'][0].__setitem__('actor1','/env/wrong/collision'),
            lambda e:e['target_surface_witness'].__setitem__('environment_origin_world_m',[0,0,0]),
            lambda e:e['target_surface_witness']['root_pose'].__setitem__(2,.01),
            lambda e:e['target_surface_witness'].__setitem__('selected_point_indices',[-1]),
            lambda e:e['target_surface_witness'].__setitem__('all_distances_m',[0])]:
            broken=deepcopy(event);edit(broken);out=validate_surface_event(config,broken,capture)
            self.assertEqual(out['status'],'inconsistent_evidence');self.assertEqual(out['metrics'],{})
        config['target_surface']['require_contact']=False
        self.assertEqual(validate_surface_event(config,event,{'status':'unavailable'})['status'],'partial_evidence')

    def test_cached_strike_surface_failure_excludes_boundary_geometry_without_rewriting_outcomes(self):
        config,capture=fixture();stage=strike.retained_strike();stage['action_success']=True
        stage['recognition'].update(target_label='target',target_surface=config['target_surface'])
        stage['target_surface_binding']=capture
        event=impact(config,capture);stage['physical_events']['impact'].update(event)
        stage['physical_events']['impact']['tool_target_contacts'][0]['force_report_physics_step']=100
        stage['conditions']=[{'id':'contact','event':{'kind':'recognition_event','name':'impact'}}]
        score={'conditions':{'contact':{'status':'reproduced','recorded_result':{'error':.003}}},
            'trajectories':deepcopy(stage['trajectories'])}
        score['trajectories']['path']['status']='reproduced'
        apply_recognition_validation(stage,score)
        self.assertEqual(score['conditions']['contact']['status'],'invalid_recognition_window')
        self.assertEqual(score['conditions']['contact']['recorded_result']['error'],.003)
        self.assertTrue(stage['action_success'])
