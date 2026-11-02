"""Prepare the browser's rigid Skelly artwork from the existing addon and Forge.

Offline developer tool, not a runtime dependency on Blender or the addon.
Run with Core's editable environment and explicit --addon-root and --output.
The fitting equations follow addon parquet_scene.native_skelly and
meshes/skelly_mesh/attachment_frame.py; poses are never reconstructed here.
"""
import argparse
import ast
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation
from skellyforge.core.skeleton.skeleton_definition import SkeletonDefinition
from skellyforge.core.skeleton.pose.rest_pose import RestPose


def basis(primary, secondary):
    primary = np.asarray(primary, dtype=float)
    primary = primary / np.linalg.norm(primary)
    secondary = np.asarray(secondary, dtype=float)
    secondary = secondary - primary * np.dot(primary, secondary)
    if np.linalg.norm(secondary) < 1e-6:
        raise ValueError('Degenerate attachment roll')
    secondary /= np.linalg.norm(secondary)
    return np.column_stack((primary, secondary, np.cross(primary, secondary)))


def triangulate(points):
    """Ear-clip authored polygons; Skelly includes three concave eight-sided faces."""
    if len(points) == 3:
        return [(0, 1, 2)]
    points = np.asarray(points)
    normal = np.cross(points, np.roll(points, -1, axis=0)).sum(axis=0)
    flat = np.delete(points, np.argmax(np.abs(normal)), axis=1)
    def cross(a, b, c):
        u, v = flat[b] - flat[a], flat[c] - flat[a]
        return float(u[0] * v[1] - u[1] * v[0])
    area = sum(flat[i, 0] * flat[(i + 1) % len(flat), 1] - flat[(i + 1) % len(flat), 0] * flat[i, 1] for i in range(len(flat)))
    winding = 1 if area > 0 else -1
    epsilon = max(float(np.ptp(flat, axis=0).max()) ** 2 * 1e-12, 1e-20)
    remaining, triangles = list(range(len(flat))), []
    while len(remaining) > 3:
        for j, b in enumerate(remaining):
            a, c = remaining[j - 1], remaining[(j + 1) % len(remaining)]
            if winding * cross(a, b, c) <= epsilon:
                continue
            if any(all(winding * cross(u, v, p) >= -epsilon for u, v in ((a, b), (b, c), (c, a)))
                   for p in remaining if p not in (a, b, c)):
                continue
            triangles.append((a, b, c))
            remaining.pop(j)
            break
        else:
            raise ValueError('Cannot triangulate authored polygon')
    triangles.append(tuple(remaining))
    return triangles


def prepare(addon_root, reference_model=None):
    source = addon_root / 'freemocap_blender_addon'
    asset_path = source / 'assets/skelly_mesh.json.gz'
    scene_path = source / 'core_functions/parquet_scene.py'
    asset = json.loads(gzip.decompress(asset_path.read_bytes()))
    if asset['schema_version'] != 2 or asset['coordinate_system'] != 'blender_x_right_y_forward_z_up':
        raise ValueError('Unsupported source asset')
    # Read only the existing pure mapping function: importing this module needs bpy.
    function = next(n for n in ast.parse(scene_path.read_text()).body
                    if isinstance(n, ast.FunctionDef) and n.name == 'asset_segments')
    namespace = {}
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(scene_path), 'exec'), namespace)
    mapping = namespace['asset_segments']()
    skeleton = SkeletonDefinition.from_default_yaml()
    rest = RestPose.from_default_yaml(skeleton=skeleton)
    if reference_model is not None:
        from freemocap.core.streaming.message_model import ModelDefinition
        from skellyforge.core.skeleton.components.color_palette import ColorPalette
        reference = dict(model=dict(skeleton=dict(
            segments=[dict(name=s.name, frame=dict(primary_point=s.frame_definition.primary_point_name,
                                                 secondary_point=s.frame_definition.secondary_point_name)) for s in skeleton.segments.values()],
            landmarks=[dict(name=p.name, segment=p.segment, position=p.local_position.array.tolist()) for p in skeleton.landmarks.values()]),
            rest_pose=dict(parents=dict(rest.parents), orientations={name: dict(zip('wxyz', q.as_array().tolist()))
                                                                   for name, q in rest.relative_orientations.items()})),
            scales={name: 1000 for name in skeleton.segments},
            origins={name: point.array.tolist() for name, point in rest.segment_origins.items()},
            rotations={name: q.as_array().tolist() for name, q in rest.segment_orientations.items()})
        reference['definition'] = ModelDefinition.from_skeleton(
            model_id='fixture', skeleton=skeleton, rest_pose=rest,
            palette=ColorPalette.from_default_yaml(), scale_reference_name='body_height').to_cbor_message()
        reference_model.write_text(json.dumps(reference), encoding='utf-8')
    vertices = np.asarray(asset['vertices'])
    groups = {name: [i for i, weight in members if weight > 0]
              for name, members in asset['groups'].items()}
    parts, assigned = [], set()
    for old, name in mapping.items():
        indices = groups[old]
        if assigned.intersection(indices):
            raise ValueError('Overlapping rigid asset groups')
        assigned.update(indices)
        segment = skeleton.segments[name]
        endpoint = skeleton.landmarks[segment.frame_definition.primary_point_name]
        if endpoint.segment != name:
            raise ValueError('Nonlocal primary landmark')
        local = endpoint.local_position.array
        head = vertices[groups[old + '_origin'][0]]
        tail = vertices[groups['pelvis_left' if old == 'pelvis' else old + '_end'][0]]
        direction = tail - head
        frame = asset['attachment_frames'][old]
        roll = frame['roll_reference']
        source_basis = basis(direction, roll)
        quat = rest.segment_orientations[name].as_array()
        world_rest = Rotation.from_quat([quat[1], quat[2], quat[3], quat[0]]).as_matrix()
        secondary = frame.get('model_secondary_landmark')
        if secondary:
            landmark = skeleton.landmarks[secondary]
            if landmark.segment != name or segment.frame_definition.secondary_point_name != secondary:
                raise ValueError('Secondary landmark mismatch')
            rotation = basis(local, landmark.local_position.array) @ source_basis.T
        else:
            rotation = world_rest.T @ basis(world_rest @ local, roll) @ source_basis.T
        scale = np.linalg.norm(local) / np.linalg.norm(direction)
        if old == 'pelvis':
            width = skeleton.landmarks['left_hip_socket'].local_position.array - skeleton.landmarks['right_hip_socket'].local_position.array
            scale = np.linalg.norm(width) / np.linalg.norm(vertices[groups['pelvis_left'][0]] - vertices[groups['pelvis_right'][0]])
        remap = {index: row for row, index in enumerate(indices)}
        positions = ((vertices[indices] - head) @ rotation.T * scale).tolist()
        triangles, materials = [], []
        for face, material, smooth in zip(asset['faces'], asset['face_materials'], asset['face_smooth']):
            if face[0] not in remap:
                continue
            if not all(index in remap for index in face):
                raise ValueError('Face crosses rigid groups')
            face_indices = [remap[index] for index in face]
            if not smooth:
                # Keep flat-authored faces independent when computing browser normals.
                face_indices = list(range(len(positions), len(positions) + len(face)))
                positions.extend([positions[remap[index]] for index in face])
            for triangle in triangulate(vertices[face]):
                triangles.extend(face_indices[j] for j in triangle)
                materials.append(material)
        parts.append(dict(name=name, authoredLength=segment.length,
                          parent=rest.parents[name], restOrientation=quat.tolist(),
                          positions=np.asarray(positions).reshape(-1).tolist(), indices=triangles, faceMaterials=materials))
    if not {i for face in asset['faces'] for i in face}.issubset(assigned):
        raise ValueError('Unmapped surface')
    return dict(version=1, coordinateSystem=asset['coordinate_system'],
                source='freemocap_blender_addon/assets/skelly_full_mesh_20k_faces.blend',
                sourceSha256=hashlib.sha256(asset_path.read_bytes()).hexdigest(),
                landmarks={name: point.array.tolist() for name, point in rest.landmark_positions.items()},
                materials=asset['materials'], parts=parts)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--addon-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--reference-model', type=Path)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.reference_model is not None:
        args.reference_model.parent.mkdir(parents=True, exist_ok=True)
    payload = prepare(args.addon_root, args.reference_model)
    args.output.write_text(json.dumps(payload, separators=(',', ':')), encoding='utf-8')
    print(f"Prepared {len(payload['parts'])} rigid Skelly parts: {args.output}")
