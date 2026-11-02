"""CPU-only Blender oracle for browser asset fitting; no rendering or saved scene.

blender --background --factory-startup --python-exit-code 1 --python THIS --
  ADDON_ROOT REFERENCE_MODEL_JSON PREPARED_ASSET_JSON
The existing addon functions execute unchanged except their package imports,
which are supplied explicitly so addon registration/install is unnecessary.
"""
import ast
import gzip
import json
from pathlib import Path
import sys

import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

addon, model_path, asset_path = map(Path, sys.argv[sys.argv.index('--') + 1:])
source = addon / 'freemocap_blender_addon'
folder = source / 'core_functions/meshes/skelly_mesh'
namespace = dict(bpy=bpy, np=np, Matrix=Matrix, Quaternion=Quaternion, Vector=Vector,
                 json=json, gzip=gzip, Path=Path,
                 SKELLY_FULL_MESH_PATH=str(source / 'assets/skelly_full_mesh_20k_faces.blend'))


def load_functions(path, names):
    tree = ast.parse(path.read_text())
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    class Imports(ast.NodeTransformer):
        def visit_ImportFrom(self, node):
            return None
    tree = ast.fix_missing_locations(Imports().visit(ast.Module(body=functions, type_ignores=[])))
    exec(compile(tree, str(path), 'exec'), namespace)


load_functions(folder / 'portable_asset.py', ['load_skelly_mesh'])
load_functions(folder / 'attachment_frame.py', ['basis', 'attachment_rotation'])
load_functions(source / 'core_functions/parquet_scene.py', ['asset_segments', 'bind', 'native_skelly'])
groups_tree = ast.parse((folder / 'helpers/skelly_vertex_groups.py').read_text())
namespace['_SKELLY_VERTEX_GROUPS'] = ast.literal_eval(next(node.value for node in groups_tree.body if isinstance(node, ast.Assign)))
rig = bpy.data.objects.new('reference', bpy.data.armatures.new('reference'))
bpy.context.collection.objects.link(rig)
mesh = namespace['native_skelly'](dict(data=json.loads(model_path.read_text()), rig=rig))
original = json.loads(gzip.decompress((source / 'assets/skelly_mesh.json.gz').read_bytes()))
prepared = json.loads(asset_path.read_text())
parts = {p['name']: p for p in prepared['parts']}
maximum = 0.
for old, name in namespace['asset_segments']().items():
    indices = [i for i, weight in original['groups'][old] if weight > 0]
    # Explicit presentation delta from the addon; its scientific binding is unchanged.
    expected = np.array([mesh.data.vertices[i].co[:] for i in indices]) * prepared.get('artworkScales', {}).get(name, 1.)
    if name == 'thoracic' and prepared.get('torsoSocketFit'):
        # Explicit artwork correction, independently applied to Blender's fit.
        fit = prepared['torsoSocketFit']
        original_expected = expected.copy()
        for side, (source_anchor, target_anchor) in enumerate(zip(fit['source'], fit['target'])):
            mask = original_expected[:, 0] < 0 if side == 0 else original_expected[:, 0] > 0
            weights = original_expected[mask, 0] / source_anchor[0]
            expected[mask] += weights[:, None] * (np.asarray(target_anchor) - source_anchor)
    actual = np.asarray(parts[name]['positions']).reshape(-1, 3)[:len(indices)]
    maximum = max(maximum, float(np.max(np.abs(actual - expected))))
    np.testing.assert_allclose(actual, expected, atol=2e-6, rtol=0, err_msg=name)
print(json.dumps(dict(check='addon-native-skelly-fit', parts=len(parts), max_authored_unit_error=maximum)))
