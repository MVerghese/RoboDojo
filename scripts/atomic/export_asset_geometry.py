#!/usr/bin/env python3
"""Export baked asset meshes without SimulationApp, a policy or GPU allocation.

Geometry is authored asset evidence, not live contact or cavity certification.
The caller separately compares it with live scaled mesh bounds/model identity.
"""
import argparse
import hashlib
import json
import ast
import re
import shutil
import subprocess
import sys
from pathlib import Path
import numpy as np
from pxr import Gf, Usd, UsdGeom, UsdPhysics
try:
    from task.atomic.collision_metadata import describe_mesh_collision
except ModuleNotFoundError:
    # The CPU evidence worker ships this module beside the standalone exporter.
    from collision_metadata import describe_mesh_collision


ASSETS = [('Rigid','key',0),('Geometry','key_slot',0),('Rigid','cup',6),
          ('Rigid','charger',0),('Rigid','socket',0),('Rigid','wuliangye',0),
          ('Rigid','mug',15),('Rigid','mug',16),('Rigid','goblet',6)]
ASSETS += [('Rigid','factory_nut',i) for i in range(5)]
ASSETS += [('Geometry','factory_bolt',i) for i in range(5)]
ASSETS += [('Geometry','vase',i) for i in range(5)]


def export_asset(asset_root, section, category, model):
    folder=asset_root/section/category/f'{model:05d}'
    source=folder/'object.usdz';stage=Usd.Stage.Open(str(source))
    if stage is None:raise RuntimeError('cannot open asset stage')
    root=stage.GetDefaultPrim()
    if not root:raise RuntimeError('asset requires an explicit default prim')
    transforms=UsdGeom.XformCache();root_transform=transforms.GetLocalToWorldTransform(root)
    scale=np.asarray(Gf.Transform(root_transform).GetScale(),dtype=float)
    points=[];triangles=[];meshes=[];rigid_bodies=[]
    for prim in Usd.PrimRange(root,Usd.TraverseInstanceProxies()):
        if prim.HasAPI(UsdPhysics.RigidBodyAPI):
            transform = UsdGeom.Xformable(prim)
            rigid_bodies.append({'path': str(prim.GetPath()),
                'enabled': UsdPhysics.RigidBodyAPI(prim).GetRigidBodyEnabledAttr().Get(),
                'reset_xform_stack': bool(transform and transform.GetResetXformStack())})
        if not prim.IsA(UsdGeom.Mesh):continue
        mesh=UsdGeom.Mesh(prim);raw=mesh.GetPointsAttr().Get()
        if not raw:continue
        transform,_=transforms.ComputeRelativeTransform(prim,root)
        values=np.asarray([transform.Transform(Gf.Vec3d(*map(float,p))) for p in raw])
        base=len(points);points.extend(values.tolist())
        faces=[];indices=list(mesh.GetFaceVertexIndicesAttr().Get());offset=0
        for count in mesh.GetFaceVertexCountsAttr().Get():
            face=indices[offset:offset+count];offset+=count
            faces.extend([[base+face[0],base+face[i],base+face[i+1]] for i in range(1,count-1)])
        triangles.extend(faces)
        meshes.append({'path':str(prim.GetPath()),'point_offset':base,'points':len(values),
                       'triangles':len(faces),'has_collision_api':prim.HasAPI(UsdPhysics.CollisionAPI),
                       'collision_configuration':describe_mesh_collision(prim,UsdPhysics)})
    vertices=np.asarray(points)
    if not len(triangles):raise RuntimeError('asset contains no triangle geometry')
    metadata_path=folder/'metadata.json'
    return {'source':str(source),'asset_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'metadata':json.loads(metadata_path.read_text()),'metadata_sha256':hashlib.sha256(metadata_path.read_bytes()).hexdigest(),
        'default_prim':str(root.GetPath()),'stage_metres_per_unit':UsdGeom.GetStageMetersPerUnit(stage),
        'authored_root_scale':scale.tolist(),'root_relative_mesh':{'vertices':points,'triangles':triangles},
        'unscaled_bounds':[vertices.min(axis=0).tolist(),vertices.max(axis=0).tolist()],
        'authored_scaled_bounds':[(vertices*scale).min(axis=0).tolist(),(vertices*scale).max(axis=0).tolist()],
        'meshes':meshes,'rigid_body_declarations':rigid_bodies,
        'interpretation':'authored material/outer geometry; no automatic interior or opening inference'}


def main():
    p=argparse.ArgumentParser();p.add_argument('--asset-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--asset',action='append',help='Explicit section/category/model-id; default is the 24 reviewed rigid assets')
    p.add_argument('--sdk-inventory',action='store_true',help='Read installed cloth/particle API source declarations without SimulationApp')
    p.add_argument('--native-inventory',action='store_true',help='Retain installed particle/cloth headers and relevant exported PhysX symbols; no SimulationApp')
    args=p.parse_args();rows={}
    selected=[(s,c,int(m)) for s,c,m in (x.split('/') for x in args.asset)] if args.asset else ASSETS
    for section,category,model in selected:
        key=f'{section}/{category}/{model:05d}'
        try:rows[key]={'status':'exported',**export_asset(args.asset_root,section,category,model)}
        except Exception as error:rows[key]={'status':'unavailable','error':f'{type(error).__name__}: {error}'}
        print(key,rows[key]['status'],flush=True)
    result={'schema_version':1,'assets':rows,'gpu_used':False,
            'scope':'baked asset metadata/mesh export; live frame and cavity calibration remain separate'}
    if args.sdk_inventory:
        package=Path(sys.prefix)/'lib'/f'python{sys.version_info.major}.{sys.version_info.minor}'/'site-packages'/'isaacsim'
        files=set(package.rglob('*cloth*.py'))|set(package.rglob('*particle*.py'))|set(package.glob('**/omni/physics/tensors/impl/api.py'))
        inventory=[]
        for path in sorted(files)[:256]:
            try:
                source=path.read_text();tree=ast.parse(source)
                classes=[{'class':n.name,'methods':[m.name for m in n.body if isinstance(m,(ast.FunctionDef,ast.AsyncFunctionDef))]}
                         for n in ast.walk(tree) if isinstance(n,ast.ClassDef) and any(s in n.name.lower() for s in ('cloth','particle'))]
                if classes:inventory.append({'path':str(path),'sha256':hashlib.sha256(source.encode()).hexdigest(),'classes':classes})
            except (OSError,SyntaxError,UnicodeError):continue
        result['sdk_api_inventory']={'package_root':str(package),'files':inventory,
            'scope':'static installed Python declarations; native/binary APIs require separate verification'}
    if args.native_inventory:
        package=Path(sys.prefix)/'lib'/f'python{sys.version_info.major}.{sys.version_info.minor}'/'site-packages'/'isaacsim'
        declarations=[]
        for path in sorted(set(package.rglob('*particle*.pyi'))|set(package.rglob('*Particle*.h'))|
                           set(package.rglob('*Cloth*.h'))|set(package.rglob('*PBD*.h')))[:128]:
            if path.stat().st_size>2*1024**2:continue
            source=path.read_text(errors='replace')
            declarations.append({'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                                 'source':source})
        binaries=[];nm=shutil.which('nm')
        for path in sorted(package.rglob('*physx*.so'))[:48]:
            row={'path':str(path),'size_bytes':path.stat().st_size,'tool':nm}
            if nm:
                try:
                    scan=subprocess.run([nm,'-D','-C','--defined-only',str(path)],
                        capture_output=True,text=True,timeout=20)
                    relevant=[line for line in scan.stdout.splitlines()
                        if re.search(r'particle|cloth|contact|impulse|force',line,re.I)]
                    row.update(returncode=scan.returncode,relevant_symbols=relevant[:500],
                               symbols_truncated=len(relevant)>500)
                except subprocess.TimeoutExpired:row['status']='symbol_scan_timeout'
            else:row['status']='nm_unavailable'
            binaries.append(row)
        result['native_api_inventory']={'package_root':str(package),'declarations':declarations,
            'binaries':binaries,'scope':'installed declaration/exported-symbol inventory only; absence does not prove lack of an internal API or certify particle contact readback'}
        # Binding stubs commonly have names such as _physx.pyi rather than
        # "particle". Inspect their declarations directly; the earlier filename
        # inventory did not cover these interfaces.
        binding_files = sorted(set(package.rglob('*.pyi')))
        bindings=[]; skipped=[]
        for path in binding_files:
            if path.stat().st_size > 2*1024**2:
                skipped.append({'path':str(path),'reason':'over_2_MiB'});continue
            source=path.read_text(errors='replace')
            if not re.search(r'particle|cloth|contact.?report|contact.?force|contact.?impulse',source,re.I):
                continue
            signatures=[{'line':i,'declaration':line.strip()} for i,line in enumerate(source.splitlines(),1)
                if re.search(r'particle|cloth|contact|impulse|force',line,re.I)]
            bindings.append({'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                             'source':source,'matching_declarations':signatures})
        result['contact_binding_inventory']={'package_root':str(package),'stub_files_scanned':len(binding_files),
            'files':bindings,'skipped':skipped,
            'scope':'all installed Python binding stubs including generic _physx interfaces; declarations are not runtime particle/finger force readback validation'}
    args.output.write_text(json.dumps(result)+'\n')
    print('Exported',sum(r['status']=='exported' for r in rows.values()),'/',len(rows),flush=True)


if __name__=='__main__':main()
