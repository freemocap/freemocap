"""Executed inside a fresh Blender process; never imports FreeMoCap core."""
import importlib
import json
from pathlib import Path


def validate(request, package):
    import bpy
    import numpy as np
    from mathutils import Quaternion

    path = Path(request['output'])
    bpy.ops.wm.open_mainfile(filepath=str(path), load_ui=False, use_scripts=False)
    if bpy.context.scene.get('freemocap_source_sha256') != request['source_sha256']:
        raise ValueError('Saved Blender scene belongs to a different Parquet snapshot; export it again')
    units = bpy.context.scene.unit_settings
    if units.system != 'METRIC' or abs(units.scale_length - 1.) > 1e-9:
        raise ValueError('Saved Blender scene must use meters')
    reader = importlib.import_module(package + '.freemocap_data_handler.parquet_recording')
    data = reader.read_recording(request['recording'], run_id=request['run_id'], sensor_group=request['sensor_group'])
    roots = [o for o in bpy.data.objects if o.get('import_route') == 'parquet_segments'
             and o.get('run_id') == data['run_id'] and o.get('sensor_group') == data['sensor_group']
             and o.get('source') == data['source']]
    if len(roots) != 1:
        raise ValueError('Saved scene does not contain the selected Parquet segment model')
    root = roots[0]
    rigs = [o for o in root.children_recursive if o.type == 'ARMATURE']
    if len(rigs) != 1:
        raise ValueError('Saved scene must contain one selected armature')
    rig = rigs[0]
    groups = [o for o in root.children if o.name.startswith('landmarks_empties_parent')]
    if len(groups) != 1:
        raise ValueError('Saved scene is missing its landmark group')
    points = {o.name: o for o in groups[0].children}
    frames = data['frames']
    if (bpy.context.scene.frame_start, bpy.context.scene.frame_end) != (int(frames[0]), int(frames[-1])):
        raise ValueError('Saved scene frame range differs from Parquet')
    np.testing.assert_allclose(json.loads(root['timestamps_s']), data['times'], atol=1e-9, rtol=0)
    if len(frames) > 1:
        np.testing.assert_allclose(bpy.context.scene.render.fps / bpy.context.scene.render.fps_base,
            1. / np.median(np.diff(data['times'])), atol=1e-4, rtol=0)
    channels = data['channels']
    if set(rig.pose.bones.keys()) != set(channels['SEGMENT_ORIGINS']):
        raise ValueError('Saved scene segment names differ from Parquet')
    count = 0
    for i, frame in enumerate(frames):
        bpy.context.scene.frame_set(int(frame))
        evaluated = rig.evaluated_get(bpy.context.evaluated_depsgraph_get())
        for name, values in channels['LANDMARKS_3D'].items():
            obj = points.get(name)
            if obj is None:
                raise ValueError(f'Saved scene missing landmark: {name}')
            valid = bool(np.isfinite(values[i]).all())
            if bool(obj['sample_valid']) != valid or obj.hide_viewport == valid:
                raise ValueError(f'Landmark validity differs: {name}, {frame}')
            if valid:
                np.testing.assert_allclose(tuple(obj.matrix_world.translation), values[i], atol=2e-6, rtol=0)
        for name, values in channels['SEGMENT_ORIGINS'].items():
            q = channels['ROTATIONS_WORLD'][name][i]
            bone = evaluated.pose.bones[name]
            valid = bool(np.isfinite(values[i]).all() and np.isfinite(q).all())
            if bool(bone['sample_valid']) != valid:
                raise ValueError(f'Segment validity differs: {name}, {frame}')
            if valid:
                world = evaluated.matrix_world @ bone.matrix
                np.testing.assert_allclose(tuple(world.translation), values[i], atol=2e-6, rtol=0)
                actual = world.to_3x3() @ bone.bone.matrix_local.to_3x3().inverted()
                np.testing.assert_allclose(np.array(actual), np.array(Quaternion(q).to_matrix()), atol=2e-5, rtol=0)
                count += 1
            elif max(abs(v) for v in bone.scale) != 0:
                raise ValueError(f'Missing segment is visible: {name}, {frame}')
    if not count:
        raise ValueError('No finite segment poses were checked')
    return dict(frames=len(frames), finite_segment_poses=count, landmarks=len(channels['LANDMARKS_3D']),
        segments=len(rig.pose.bones), route='parquet_segments', source=data['source'], blender=list(bpy.app.version),
        position_tolerance_m=2e-6, rotation_matrix_tolerance=2e-5)
