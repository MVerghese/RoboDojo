"""Material geometry selection excludes duplicate collision proxies explicitly."""
import unittest
from unittest.mock import patch
from types import SimpleNamespace as NS, ModuleType
import numpy as np
from task.atomic.surfaces import ObjectSurfaces,_transformed_points
from task.atomic.spec import _validate_selector
from task.atomic.calibration import snapshot_scene
from test_atomic_regions import cube
import test_atomic_calibrated_frames as frame_fixtures


class MeshSelectionTests(unittest.TestCase):
    def test_selected_mesh_geometry_and_missing_path_fail_closed(self):
        vertices,faces=cube(-.01,.01)
        def prim(path):return NS(IsA=lambda _:True,GetPath=lambda:path)
        visual=prim('/obj/visual/material');proxy=prim('/obj/collision/proxy');root=prim('/obj')
        matrix=NS(__array__=lambda *args:np.eye(4),Transform=lambda value:value)
        xforms=NS(GetLocalToWorldTransform=lambda _:np.eye(4),ComputeRelativeTransform=lambda *args:(matrix,False))
        mesh=NS(GetPointsAttr=lambda:NS(Get=lambda:vertices.tolist()),
                GetFaceVertexIndicesAttr=lambda:NS(Get=lambda:faces.reshape(-1).tolist()),
                GetFaceVertexCountsAttr=lambda:NS(Get=lambda:[3]*len(faces)))
        omni=ModuleType('omni');omni.usd=NS(get_context=lambda:NS(get_stage=lambda:NS(GetPrimAtPath=lambda _:root)))
        pxr=ModuleType('pxr');pxr.Gf=NS(Transform=lambda _:NS(GetScale=lambda:[1,1,1]),Vec3d=lambda *args:np.array(args))
        pxr.Usd=NS(PrimRange=lambda *args:[visual,proxy],TraverseInstanceProxies=lambda:None)
        pxr.UsdGeom=NS(Mesh=lambda _:mesh,XformCache=lambda:xforms)
        env=NS(scene_manager=NS(layout_manager=NS(get_scene_object=lambda *a:NS(usd_prim_path='/obj'),get_instance_name=lambda *a:'object')))
        surfaces=ObjectSurfaces(env);pose=np.array([0,0,0,1,0,0,0])
        with patch.dict('sys.modules',{'omni':omni,'omni.usd':omni.usd,'pxr':pxr}):
            # Centre readback must not instantiate/export a full triangle surface.
            with patch.object(surfaces,'resolve',side_effect=AssertionError('centre attempted full mesh serialization')):
                np.testing.assert_allclose(surfaces.center_pose('object',0,pose)[:3],[0,0,0])
                self.assertFalse(surfaces.cache);self.assertEqual(len(surfaces.centers),1)
            all_meshes=surfaces.resolve('object',0,pose)
            selected=surfaces.resolve('object',0,pose,mesh_paths=['visual/material'])
            self.assertEqual(len(all_meshes['triangles']),24)
            np.testing.assert_allclose(surfaces.center_pose('object',0,pose)[:3],all_meshes['position'])
            self.assertEqual(len(selected['triangles']),12)
            with self.assertRaisesRegex(RuntimeError,'missing'):surfaces.resolve('object',0,pose,mesh_paths=['absent'])
        for path in ['/elsewhere','../proxy','visual/../proxy','visual//material']:
            with self.assertRaises(ValueError):_validate_selector({'kind':'object_pose','label':'object','mesh_paths':[path],'calibration_id':'proof'},'bad')

    def test_large_initial_mesh_capture_uses_actual_bounds_without_unused_full_export(self):
        lm=NS(get_labels_by_prefix=lambda **kw:['bottle'],get_instance_name=lambda **kw:'bottle',
              instance_type_by_env=[{'bottle':'rigid'}],get_instance_metadata=lambda **kw:{})
        surfaces=NS(local_mesh_summary=lambda *a:{'bounds':[[-1,-2,-3],[1,2,3]],'triangles':100001,
                    'geometry_representation':'actual test material points'},
                    resolve=lambda *a:(_ for _ in ()).throw(AssertionError('unused full mesh export')))
        env=NS(scene_manager=NS(layout_manager=lm),_atomic_surfaces=surfaces)
        s=NS(env=env,env_idx=0,_object_pose=lambda label:np.array([0,0,0,1,0,0,0]))
        row=snapshot_scene(s)['objects']['bottle']
        self.assertEqual(row['errors'],[]);self.assertNotIn('local_mesh',row)
        self.assertEqual(row['local_mesh_bounds_m'],[[-1,-2,-3],[1,2,3]])
        self.assertEqual(row['mesh_capture_status'],'omitted_above_100000_triangle_budget')

    def test_vectorized_usd_row_transform_checks_actual_gf_and_scaled_coordinates(self):
        matrix=np.array([[0,1,0,0],[-1,0,0,0],[0,0,1,0],[10,20,30,1.]])
        values=[[1,0,0],[0,1,0],[0,0,1]]
        mesh=NS(GetPointsAttr=lambda:NS(Get=lambda:values))
        class Transform:
            def __array__(self,*args,**kw):return matrix
            def Transform(self,p):return np.array([10-p[1],20+p[0],30+p[2]])
        pxr=ModuleType('pxr');pxr.Gf=NS(Vec3d=lambda *a:np.array(a))
        with patch.dict('sys.modules',{'pxr':pxr}):
            p=_transformed_points(mesh,Transform(),np.array([2,3,4]))
            np.testing.assert_allclose(p,[[20,63,120],[18,60,120],[20,60,124]])
            with patch.object(Transform,'Transform',return_value=np.zeros(3)):
                with self.assertRaisesRegex(RuntimeError,'Gf witnesses'):_transformed_points(mesh,Transform(),np.ones(3))

    def test_model_identity_is_checked_against_live_layout(self):
        _,s=frame_fixtures.CalibratedFrameTests().world()
        s.env.scene_manager.layout_manager.get_instance_metadata=lambda **kw:{'model_name':'bolt','model_id':2}
        selector={'kind':'calibrated_frame','label':'target','local_pose':[0,0,.05,1,0,0,0],
                  'calibration_id':'mesh review','asset_model':{'name':'bolt','index':2}}
        _validate_selector(selector,'opening');s._resolve(selector)
        selector['asset_model']['index']=3
        with self.assertRaisesRegex(RuntimeError,'model differs'):s._resolve(selector)


if __name__=='__main__':unittest.main()
