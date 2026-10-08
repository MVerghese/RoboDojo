"""Role selection must keep immutable initial geometry and reject ambiguous factors."""
from copy import deepcopy
import math
import unittest
from scripts.atomic.generate_source_selection_suite import probes
from task.atomic.selection import validate_selection
from task.atomic.spec import _validate_condition
from scripts.atomic.continuous_report import collect_events
import test_atomic_paths_selection as runtime
from task.atomic.session import AtomicSession
from scripts.atomic.audit_scores import audit_atomic


def scene(task):
    labels,models,angles=(('bottle','cup'),('wuliangye','mug'),(0,0)) if task=='pour_liquid_into_cup' else (('cup','vase'),('cup','vase'),(55,10))
    data={'coordinate_frame':'environment_local_world','quaternion_order':'wxyz','objects':{}}
    for label,model,angle,x in zip(labels,models,angles,(-.2,.1)):
        q=[math.cos(math.radians(angle)/2),0,0,math.sin(math.radians(angle)/2)]
        data['objects'][label]={'category':'rigid','errors':[],'metadata':{'model_name':model,'model_id':0},
            'initial_root_pose':[x,0,.8,*q],'local_mesh_bounds_m':[[-.02]*3,[.02]*3]}
    return data


class SourceSelectionTests(unittest.TestCase):
    def test_role_selection_uses_initial_candidate_geometry_not_moved_outcome(self):
        world=runtime.World();world.goal=False;world.poses['other'][0]=.2
        selection=runtime.selection_definition(role={'family':'pour','slot':'source'})
        selection['conditions'][0]['slot']='source'
        session=AtomicSession(world.env,runtime.endpoint_stage(selection=selection),0)
        world.poses['other'][0]=0;world.poses['object'][0]=.2
        world.hold(label='other');world.tick(session);world.tick(session)
        audit=audit_atomic(session.summary());chosen=audit['selection']
        self.assertEqual(chosen['role'],{'family':'pour','slot':'source'})
        self.assertEqual(chosen['eligible_candidates'],['object']);self.assertFalse(chosen['passed'])
        event=next(iter(collect_events({'atomic_scores':[audit]}).values()))
        self.assertEqual(event['family'],'pour');self.assertEqual(event['score']['slot'],'source')
        self.assertAlmostEqual(event['score']['recorded_result']['components']['position_m'],.2)
        bad=deepcopy(selection);bad['role']['family']='invented'
        with self.assertRaisesRegex(ValueError,'known action family'):validate_selection(bad,_validate_condition)
        bad=deepcopy(selection);bad['role']['slot']='destination'
        with self.assertRaisesRegex(ValueError,'match'):validate_selection(bad,_validate_condition)

    def test_initial_source_factors_discriminate_or_report_orientation_ambiguity(self):
        for task in ('pour_liquid_into_cup','pour_balls_into_vase'):
            rows,blocked=probes(scene(task),task)
            expected={'point','pose','displacement','relation'}
            if task=='pour_balls_into_vase':expected.add('orientation')
            self.assertEqual(set(rows),expected)
            for row in rows.values():
                self.assertEqual([l for l,r in row['preflight'].items() if r['passed']],[row['target']])
            if task=='pour_liquid_into_cup':self.assertEqual(set(blocked),{'orientation'})
        bad=scene('pour_liquid_into_cup');bad['objects']['cup']['metadata']['model_name']='other'
        with self.assertRaisesRegex(ValueError,'reviewed vessel'):probes(bad,'pour_liquid_into_cup')
        bad=scene('pour_liquid_into_cup');bad['coordinate_frame']='world'
        with self.assertRaisesRegex(ValueError,'environment-local'):probes(bad,'pour_liquid_into_cup')
