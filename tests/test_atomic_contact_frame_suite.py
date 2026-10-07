"""Contact-frame A/B generation preserves physical gates and condition semantics."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from scripts.atomic.generate_contact_frame_suite import expand,generate
from task.atomic.spec import _validate_condition
from task.atomic.geometry import evaluate_geometry


def program(family='push',pair=False):
    measurement={'kind':'object_contact_points' if pair else 'contact_points','label':'tool' if pair else 't'}
    if pair:measurement['other_label']='t'
    else:measurement.update(arm='any',min_finger_bodies=1)
    return {'stages':[{'id':'action','instruction':'Push the target.','family':family,
        'recognition':{'kind':'held_tool_push' if pair else 'finger_contact_motion','label':measurement['label']},
        'success_checks':[{'name':'is_at','args':{'label':'t','target':'pad'}}],
        'geometry':[{'id':'original','slot':'contact','kind':'relative_displacement',
            'measurement':measurement,'reference':{'kind':'object_center_pose','label':'t'},
            'event':{'kind':'first_motion','label':'t','threshold':.01},'expected':[.04,0,0],
            'axes':[0],'tolerance':.02}]}]}


class ContactFrameSuiteTests(unittest.TestCase):
    def test_annotations_preserve_success_recognition_and_source_program(self):
        for task,family,pair in [('push_T','push',False),('stack_blocks_by_language','pick',False),
                                  ('align_blocks','push_with_tool',True),('play_Xylophone','touch_with_tool',True)]:
            source=program(family,pair);before=deepcopy(source)
            result,text,coverage=expand(source,task)
            self.assertEqual(source,before)
            stage=result['stages'][0]
            self.assertEqual(stage['recognition'],before['stages'][0]['recognition'])
            self.assertEqual(stage['success_checks'],before['stages'][0]['success_checks'])
            for c in stage['geometry']:_validate_condition(c)
            self.assertEqual(coverage[0]['family'],family)
            self.assertIn('actual force-bearing contact',text)

    def test_box_is_at_reference_origin_and_direction_is_separate_from_full_pose(self):
        result,text,_=expand(program(),'push_T');conditions={c['id']:c for c in result['stages'][0]['geometry']}
        self.assertTrue(evaluate_geometry(conditions['contact_point'],[.07,0,0]).passed)
        self.assertFalse(evaluate_geometry(conditions['contact_box'],[.07,0,0]).passed)
        self.assertIn('box centered at the reference origin',text)
        # Rotation by pi around local y keeps the requested negative z axis but changes yaw.
        observed={'position':[.04,0,0],'points':[[.04,0,0]],'orientation':[0,0,1,0],
                  'oriented_contact_frame':True}
        self.assertTrue(evaluate_geometry(conditions['contact_frame_z'],observed).passed)
        self.assertFalse(evaluate_geometry(conditions['contact_frame_pose'],observed).passed)

    def test_ambiguous_or_frozen_contact_bindings_fail_before_generation(self):
        for change in ('duplicate','missing','frozen'):
            source=program();geometry=source['stages'][0]['geometry']
            if change=='duplicate':geometry.append(deepcopy(geometry[0]))
            elif change=='missing':geometry.clear()
            else:geometry[0]['reference']['time']='stage_start'
            with self.subTest(change=change),self.assertRaises(ValueError):expand(source,'push_T')

    def test_generated_manifest_separates_task_coverage_from_stage_bindings(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);cases=[]
            for task,family,pair in [('push_T','push',False),('play_Xylophone','touch_with_tool',True)]:
                source=program(family,pair);source['task_name']=task
                source['stages'][0].pop('recognition')
                if family=='push':
                    source['stages'][0]['recognition']={'kind':'finger_contact_motion','label':'t','arm':'any',
                        'motion_threshold_m':.01,'min_contact_steps':2,'support_labels':['@table']}
                for mode in ('baseline','conditioned'):
                    b=deepcopy(source)
                    if mode=='conditioned':b['geometric_instruction']='Use the specified contact location.'
                    path=root/(task+'_'+mode+'.json');path.write_text(json.dumps(b))
                    cases.append({'id':task+'_'+mode,'task':task,'checkpoint_id':'cp','prompt_mode':mode,
                        'program':str(path),'program_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                        'layout_id':0,'stage':'multiple','kind':'multiple'})
            path=root/'suite.json';path.write_text(json.dumps({'checkpoints':{'cp':{'checkpoint':'test','base_run':'/test'}},'cases':cases}))
            result=generate(root/'output',[path],['push_T','play_Xylophone'])
            self.assertEqual(len(result['cases']),4)
            self.assertEqual(sum(row['included'] for row in result['coverage']),2)
            self.assertEqual({row['task'] for row in result['contact_frame_bindings']},{'push_T','play_Xylophone'})


if __name__=='__main__':unittest.main()
