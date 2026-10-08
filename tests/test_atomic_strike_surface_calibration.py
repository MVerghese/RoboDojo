from copy import deepcopy
import unittest
from scripts.atomic.calibrate_strike_surfaces import calibrate
from scripts.atomic.audit_strike_surfaces import audit_stage


def asset():
    vertices=[[0,0,0],[1,0,0],[0,1,0],[2,0,0],[3,0,0],[2,1,0]]
    return {'status':'exported','asset_sha256':'a'*64,'metadata_sha256':'b'*64,
        'default_prim':'/World','authored_root_scale':[1,1,1],
        'authored_scaled_bounds':[[0,0,0],[3,1,0]],
        'meshes':[{'path':'/World/visual','point_offset':0,'points':3,'triangles':1,'has_collision_api':False},
                  {'path':'/World/collision','point_offset':3,'points':6,'triangles':2,'has_collision_api':True}],
        'root_relative_mesh':{'vertices':[[99,99,99],[100,99,99],[99,100,99]]+vertices,
            'triangles':[[0,1,2],[3,4,5],[6,7,8]]},
        'metadata':{'passive':{'functional':{'hit_a':{'frame':[[.2,.2,0,1,0,0,0]]},
                                           'hit_b':{'frame':[[2.2,.2,0,1,0,0,0]]}}}}}


class StrikeSurfaceCalibrationTests(unittest.TestCase):
    def archived_stage(self):
        profile=calibrate(asset(),'/World/collision',['hit_a','hit_b']);profile['asset_key']='Geometry/keys/00000'
        selectors=[{'kind':'functional_point','label':'keys','tag':tag,'type':'passive'} for tag in ['hit_a','hit_b']]
        event={'physics_step':12,'held_contact':{'environment_origin_world_m':[1,2,3]},
            'contact_points':[[.2,.2,.003]],'tool_target_contacts':[{'actor0':'/env/mallet',
                'actor1':'/env/keys/keys_0_3','position_world':[1.2,2.2,3.003],
                'force_report_physics_step':12,'impulse':[0,0,.01]}],
            'target_identity':{'target_index':0,'candidate_selectors':selectors,
                'candidate_poses':[profile['bindings'][tag]['landmark_root_pose'] for tag in ['hit_a','hit_b']]}}
        return {'stage_id':'strike','action_success':True,'recognition':{'target_point':selectors[0]},
            'physical_events':{'impact':event}},profile

    def test_archive_reconstruction_keeps_missing_live_mesh_evidence_partial_and_physical_units(self):
        stage,profile=self.archived_stage();out=audit_stage(stage,profile)
        self.assertEqual(out['status'],'partial_evidence');self.assertFalse(out['failed_checks'])
        self.assertAlmostEqual(out['metrics']['selected_surface_distance_m'][0],.003)
        self.assertTrue(out['action_success']);self.assertIn('live_selected_mesh_and_scale_capture_absent',out['unavailable'])

    def test_archive_corrupt_landmark_force_clock_model_and_point_origin_exclude_diagnostics(self):
        stage,profile=self.archived_stage()
        for change in [lambda e:e['target_identity']['candidate_poses'][1].__setitem__(0,3),
                lambda e:e['tool_target_contacts'][0].__setitem__('force_report_physics_step',11),
                lambda e:e['tool_target_contacts'][0].__setitem__('actor1','/env/keys/keys_1_3'),
                lambda e:e['tool_target_contacts'][0].__setitem__('impulse',[0,0,0]),
                lambda e:e['held_contact'].__setitem__('environment_origin_world_m',[0,0,0])]:
            broken=deepcopy(stage);change(broken['physical_events']['impact']);out=audit_stage(broken,profile)
            self.assertEqual(out['status'],'inconsistent_evidence');self.assertEqual(out['metrics'],{})
            self.assertTrue(out['action_success'])

    def test_distinct_landmarks_bind_actual_collision_faces_without_visual_geometry_or_mutation(self):
        source=asset();before=deepcopy(source);result=calibrate(source,'/World/collision',['hit_a','hit_b'])
        self.assertEqual(source,before);self.assertEqual(result['component_count'],2)
        self.assertEqual(result['bindings']['hit_a']['triangle_indices'],[0])
        self.assertEqual(result['bindings']['hit_b']['triangle_indices'],[1])
        self.assertEqual(result['bindings']['hit_a']['expected_triangles_m'],[[[0,0,0],[1,0,0],[0,1,0]]])
        self.assertEqual(result['bindings']['hit_a']['anchor_surface_distance_m'],0)
        with self.assertRaisesRegex(ValueError,'collision mesh'):calibrate(source,'/World/visual',['hit_a'])

    def test_ambiguous_surfaces_alias_landmarks_and_unreviewed_scale_are_rejected(self):
        source=asset();source['metadata']['passive']['functional']['hit_a']['frame'][0][:3]=[1.5,0,0]
        with self.assertRaisesRegex(ValueError,'unambiguous'):calibrate(source,'/World/collision',['hit_a'],max_anchor_distance_m=1)
        source=asset();source['metadata']['passive']['functional']['hit_b']['frame'][0][:3]=[.3,.3,0]
        with self.assertRaisesRegex(ValueError,'alias'):calibrate(source,'/World/collision',['hit_a','hit_b'])
        source=asset();source['authored_root_scale']=[2,1,1]
        with self.assertRaisesRegex(ValueError,'scaling'):calibrate(source,'/World/collision',['hit_a','hit_b'])


if __name__=='__main__':unittest.main()
