"""Keep effective collision settings distinct from authored overrides and cooked shapes."""
from copy import deepcopy
from types import SimpleNamespace as NS
import unittest
from task.atomic.collision_metadata import describe_mesh_collision,validate_collision_configuration


class Attribute:
    def __init__(self,name,value,authored=False):self.name=name;self.value=value;self.authored=authored
    def GetName(self):return self.name
    def Get(self):return self.value
    def HasAuthoredValueOpinion(self):return self.authored


class CollisionAPI:
    def __init__(self,prim):self.prim=prim
    def GetCollisionEnabledAttr(self):return self.prim.enabled


class MeshCollisionAPI:
    def __init__(self,prim):self.prim=prim
    def GetApproximationAttr(self):return self.prim.approximation


class Prim:
    def __init__(self):
        self.apis={CollisionAPI,MeshCollisionAPI};self.enabled=Attribute('physics:collisionEnabled',True)
        self.approximation=Attribute('physics:approximation','convexDecomposition',True)
    def HasAPI(self,api):return api in self.apis
    def GetAttributes(self):return [self.approximation,Attribute('displayColor',None)]
    def GetAppliedSchemas(self):return [api.__name__ for api in self.apis]
    def GetPath(self):return '/env/target/collision'


class CollisionMetadataTests(unittest.TestCase):
    def test_schema_default_and_authored_approximation_are_retained_without_cooked_face_claim(self):
        prim=Prim();settings=describe_mesh_collision(prim,NS(CollisionAPI=CollisionAPI,MeshCollisionAPI=MeshCollisionAPI))
        self.assertTrue(settings['collision_enabled']);self.assertFalse(settings['attributes']['physics:collisionEnabled']['authored'])
        self.assertEqual(settings['approximation'],'convexDecomposition');self.assertTrue(settings['attributes']['physics:approximation']['authored'])
        self.assertNotIn('displayColor',settings['attributes']);self.assertIn('not cooked PhysX',settings['scope'])
        capture={'object_root':'/env/target','mesh_paths':['collision'],'collision_configuration':{
            'status':'observed_composed_usd','meshes':[{'relative_path':'collision',**settings}]}}
        self.assertEqual(validate_collision_configuration(capture)['status'],'consistent_retained_configuration')
        for mutate in [lambda c:c['collision_configuration']['meshes'][0].__setitem__('prim_path','/env/wrong/collision'),
            lambda c:c['collision_configuration']['meshes'][0].__setitem__('approximation','none')]:
            broken=deepcopy(capture);mutate(broken)
            self.assertEqual(validate_collision_configuration(broken)['status'],'inconsistent_evidence')
        self.assertEqual(validate_collision_configuration({})['status'],'partial_evidence')

    def test_absent_mesh_schema_does_not_invent_triangle_mesh_approximation(self):
        prim=Prim();prim.apis={CollisionAPI};prim.enabled.value=False
        row=describe_mesh_collision(prim,NS(CollisionAPI=CollisionAPI,MeshCollisionAPI=MeshCollisionAPI))
        self.assertFalse(row['collision_enabled']);self.assertIsNone(row['approximation'])
        prim.approximation.value=float('nan')
        with self.assertRaisesRegex(ValueError,'nonfinite'):describe_mesh_collision(prim,NS(CollisionAPI=CollisionAPI,MeshCollisionAPI=MeshCollisionAPI))
