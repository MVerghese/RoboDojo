import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import numpy as np
from task.atomic.cloth_calibration import material_patch
from task.atomic.materials import resolve_material,resolve_patch_surface
from task.atomic.spec import _validate_selector
from test_atomic_physical_runtime import World
from test_atomic_materials import attach_material


class ClothCalibrationTests(unittest.TestCase):
    def test_geodesic_region_excludes_nearby_disconnected_material(self):
        v=np.array([[0,0,0],[.01,0,0],[0,.01,0],[0,0,.001],[.01,0,.001],[0,.01,.001]])
        t=np.array([[0,2,1],[3,4,5]])
        row=material_patch(v,t,[0],.02,'a'*64)
        self.assertEqual(row['face_ids'],[0]);self.assertEqual(row['x_id'],1)
        with self.assertRaisesRegex(ValueError,'complete'):material_patch(v,t,[0],.005,'a'*64)

    def test_runtime_model_asset_and_topology_are_verified(self):
        w=World();label,data=attach_material(w,'cloth',[0,1,2],[[0,0,0],[.01,0,0],[0,.01,0]])
        data['triangles']=[[0,1,2]]
        lm=w.env.scene_manager.layout_manager;obj=lm.get_scene_object(0,label)
        lm.get_instance_metadata=lambda **kw:{'model_name':'shirt','model_id':1}
        with TemporaryDirectory() as directory:
            path=Path(directory)/'object.usdz';path.write_bytes(b'actual test asset');obj.usd_path=str(path)
            row=material_patch(data['positions_world'],data['triangles'],[0],.02,hashlib.sha256(path.read_bytes()).hexdigest())
            c={'kind':'cloth_model_patch','label':label,'models':{'shirt/00001':row}};_validate_selector(c,'patch')
            pose,source=resolve_material(w.env,c,0);self.assertEqual(source['calibrated_model_patch']['model'],'shirt/00001')
            self.assertEqual(resolve_patch_surface(w.env,c,0)['material_face_ids'],[0])
            data['positions_world'][1,2]=.005
            pose,_=resolve_material(w.env,c,0);self.assertNotEqual(float(pose[5]),0)
            row['topology_sha256']='b'*64
            with self.assertRaisesRegex(RuntimeError,'topology'):resolve_material(w.env,c,0)
            row['topology_sha256']=hashlib.sha256(np.asarray(data['triangles'],dtype='<i8').tobytes()).hexdigest()
            path.write_bytes(b'changed asset file')
            with self.assertRaisesRegex(RuntimeError,'asset file'):resolve_material(w.env,c,0)
            lm.get_instance_metadata=lambda **kw:{'model_name':'other','model_id':1}
            with self.assertRaisesRegex(RuntimeError,'actual asset model'):resolve_material(w.env,c,0)


if __name__=='__main__':unittest.main()
