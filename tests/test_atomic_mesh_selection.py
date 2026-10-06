"""Material geometry selection excludes duplicate collision proxies explicitly."""
import unittest
from unittest.mock import patch
from types import SimpleNamespace as NS, ModuleType
import numpy as np
from task.atomic.surfaces import ObjectSurfaces
from task.atomic.spec import _validate_selector
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
            all_meshes=surfaces.resolve('object',0,pose)
            selected=surfaces.resolve('object',0,pose,mesh_paths=['visual/material'])
            self.assertEqual(len(all_meshes['triangles']),24)
            self.assertEqual(len(selected['triangles']),12)
            with self.assertRaisesRegex(RuntimeError,'missing'):surfaces.resolve('object',0,pose,mesh_paths=['absent'])
        for path in ['/elsewhere','../proxy','visual/../proxy','visual//material']:
            with self.assertRaises(ValueError):_validate_selector({'kind':'object_pose','label':'object','mesh_paths':[path],'calibration_id':'proof'},'bad')

    def test_model_identity_is_checked_against_live_layout(self):
        _,s=frame_fixtures.CalibratedFrameTests().world()
        s.env.scene_manager.layout_manager.get_instance_metadata=lambda **kw:{'model_name':'bolt','model_id':2}
        selector={'kind':'calibrated_frame','label':'target','local_pose':[0,0,.05,1,0,0,0],
                  'calibration_id':'mesh review','asset_model':{'name':'bolt','index':2}}
        _validate_selector(selector,'opening');s._resolve(selector)
        selector['asset_model']['index']=3
        with self.assertRaisesRegex(RuntimeError,'model differs'):s._resolve(selector)


if __name__=='__main__':unittest.main()
