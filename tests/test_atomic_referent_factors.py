"""Each initial referent constraint must discriminate its declared candidate."""
from copy import deepcopy
import math
import unittest
from scripts.atomic.generate_referent_factor_suite import probes


def scene():
    data={'coordinate_frame':'environment_local_world','quaternion_order':'wxyz','objects':{}}
    for i,(x,y,angle) in enumerate([(.08,-.13,-25),(-.35,-.13,17),(.15,-.076,15)]):
        rad=math.radians(angle)/2
        data['objects']['block_'+str(i)]={'category':'rigid','errors':[],
            'initial_root_pose':[x,y,.78,math.cos(rad),0,0,math.sin(rad)],
            'local_mesh_bounds_m':[[-.0175]*3,[.0175]*3],'metadata':{'model_name':'cube'}}
    return data


class ReferentFactorTests(unittest.TestCase):
    def test_all_four_factors_discriminate_actual_initial_geometry(self):
        rows,_=probes(scene())
        self.assertEqual(set(rows),{'pose','relative_displacement','relative_orientation','spatial_relation'})
        for row in rows.values():
            self.assertEqual([label for label,result in row['preflight'].items() if result['passed']],[row['target']])
        self.assertEqual(rows['spatial_relation']['condition']['relation_scope'],'points')
        self.assertEqual(rows['spatial_relation']['target'],'block_1')

    def test_orientation_ambiguity_is_rejected_before_submission(self):
        data=scene();data['objects']['block_1']['initial_root_pose'][3:]=data['objects']['block_0']['initial_root_pose'][3:]
        with self.assertRaisesRegex(ValueError,'relative_orientation.*unique'):probes(data)

    def test_uncomparable_frame_wrong_model_and_bad_mesh_bounds_fail(self):
        original=scene()
        for change in ('frame','model','bounds','readback'):
            data=deepcopy(original)
            if change=='frame':data['coordinate_frame']='world'
            elif change=='model':data['objects']['block_0']['metadata']['model_name']='other'
            elif change=='bounds':data['objects']['block_0']['local_mesh_bounds_m']=[[.0175]*3,[-.0175]*3]
            else:data['objects']['block_0']['errors']=['readback failed']
            with self.subTest(change=change),self.assertRaises(ValueError):probes(data)


if __name__=='__main__':unittest.main()
