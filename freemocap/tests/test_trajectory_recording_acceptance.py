"""Reconstruct copies of saved reference data, without detection or optimization."""

import os
from pathlib import Path
import shutil

import numpy as np
import pyarrow.parquet as pq
import pytest
from numpy.testing import assert_allclose, assert_array_equal
from skellyforge.core.math.geometry.rotation_quaternion import rotate_vector_pairs
from skellyforge.core.skeleton.chain.anchored_batch import AnchoredSkeletonGeometry
from skellyforge.core.skeleton.pose.hydration_batch import LandmarkPoseGeometry

from freemocap.core.recording.parquet_storage.parquet_reader import read_metadata
from freemocap.core.recording.result_processing.saved_reconstruction import read_saved_channel
from freemocap.core.recording.playback_queries import playback_manifest
from freemocap.core.types.channel_kind import ChannelKind
from freemocap.system.recording_structure.recording_structure import RecordingStructure
from freemocap.tests.refresh_recording_reconstruction import refresh_reconstruction


def assert_saved_weighted_geometry(*, bundle, fit, mapped, landmarks, origins, rotations):
    """Check rigid geometry and the constrained strength-one objective independently.

    Recover observed origins from saved mapping evidence. Published rotations
    already include chronological roll resolution and remain the source for
    fitted offsets; translation validation must not re-estimate those rotations.
    """
    geometry = AnchoredSkeletonGeometry.from_skeleton(skeleton=bundle.skeleton, fit=fit,
        anchor_segment_name=bundle.anchor_segment_name or bundle.rest_pose.root_segment_name)
    recovery = LandmarkPoseGeometry.from_skeleton(skeleton=bundle.skeleton,
        landmark_names=tuple(mapped.channel.names))
    assert recovery.segment_names == geometry.segment_names
    indices = {name: i for i, name in enumerate(geometry.segment_names)}
    origin_columns = [origins.channel.names.index(name) for name in geometry.segment_names]
    rotation_columns = [rotations.channel.names.index(name) for name in geometry.segment_names]
    landmark_columns = [landmarks.channel.names.index(name) for name in geometry.landmark_names]
    joints = tuple(bundle.skeleton.joints.values())
    parents = np.array([indices[joint.parent.name] for joint in joints])
    children = np.array([indices[joint.child.name] for joint in joints])
    anchor = geometry.anchor_index
    assert np.isfinite(origins.values).all(axis=-1).any()
    # Bound recovery and rotated-landmark temporaries for full reference recordings.
    for start in range(0, len(origins.frames), 256):
        stop = start + 256
        mapped_values = mapped.values[start:stop]
        recovered = recovery.recover_tensor(positions=mapped_values,
            landmark_present=np.isfinite(mapped_values).all(axis=-1))
        selected = np.zeros_like(recovered.segment_present)
        selected[:, anchor] = recovered.segment_present[:, anchor]
        for traversal_parents, traversal_children, _, _ in geometry.traversal_levels:
            selected[:, traversal_children] = (selected[:, traversal_parents]
                                               & recovered.segment_present[:, traversal_children])
        positions = origins.values[start:stop, origin_columns]
        orientations = rotations.values[start:stop, rotation_columns]
        model_landmarks = landmarks.values[start:stop, landmark_columns]
        assert_array_equal(np.isfinite(positions).all(axis=-1), selected)
        assert_array_equal(np.isfinite(orientations).all(axis=-1), selected)
        assert np.isnan(positions[~selected]).all()
        assert np.isnan(orientations[~selected]).all()
        safe_rotations = np.where(selected[..., None], orientations, [1., 0., 0., 0.])

        def rotate_offsets(owners, vectors):
            return rotate_vector_pairs(quaternions=safe_rotations[:, owners].reshape((-1, 4)),
                vectors=np.broadcast_to(vectors, (len(positions), len(owners), 3)).reshape((-1, 3))
            ).reshape((len(positions), len(owners), 3))

        landmark_present = selected[:, geometry.landmark_owners]
        assert_array_equal(np.isfinite(model_landmarks).all(axis=-1), landmark_present)
        assert np.isnan(model_landmarks[~landmark_present]).all()
        expected_landmarks = positions[:, geometry.landmark_owners] + rotate_offsets(
            geometry.landmark_owners, geometry.landmark_vectors)
        assert_allclose(model_landmarks[landmark_present], expected_landmarks[landmark_present], atol=1e-8)

        # Half the objective gradient: (t-o) + B.T @ (B @ t - R*a).
        # With the anchor fixed and unit position weights, zero free gradient
        # characterizes the unique strength-one minimizer, including missingness.
        gaps = positions[:, children] - positions[:, parents] - rotate_offsets(
            geometry.attachment_owners, geometry.attachment_vectors)
        edges_present = selected[:, children] & selected[:, parents]
        gaps = np.where(edges_present[..., None], gaps, 0.)
        gradient = np.where(selected[..., None], positions - recovered.origins, 0.)
        for edge, (parent, child) in enumerate(zip(parents, children, strict=True)):
            gradient[:, parent] -= gaps[:, edge]
            gradient[:, child] += gaps[:, edge]
        free = selected.copy()
        free[:, anchor] = False
        assert_allclose(gradient[free], 0., atol=1e-7, rtol=0.)
        assert_allclose(positions[selected[:, anchor], anchor],
                        recovered.origins[selected[:, anchor], anchor], atol=1e-8, rtol=0.)


@pytest.mark.parametrize('dataset', ['freemocap_test_data', 'freemocap_sample_data'])
def test_saved_reference_preserves_three_trajectories(tmp_path, dataset):
    root = Path(os.environ.get('FREEMOCAP_PROVENANCE_PREPARED_ROOT', Path.home() / 'freemocap_data/testing/prepared'))
    source = root / dataset / 'current/recordings' / dataset / f'{dataset}_data.parquet'
    if not source.is_file():
        pytest.skip(f'Prepared reference recording unavailable: {source}')
    from freemocap.tools.datasets.workflow import checked_ready
    assert checked_ready(root / dataset) is not None
    structure = RecordingStructure(base_directory=tmp_path, recording_name=dataset)
    structure.full_path.mkdir(parents=True)
    shutil.copy2(source, structure.data_parquet_path)
    metadata = read_metadata(path=structure.data_parquet_path)
    run_id = metadata.selected_run_id
    run = metadata.runs[run_id]
    model = run.models['standard_human']
    bundle = model.to_bundle()
    evidence_filter = [('channel', 'in', ['KEYPOINTS_3D', 'RAW_KEYPOINTS_3D'])]
    evidence = pq.read_table(source, filters=evidence_filter).replace_schema_metadata(None)
    refresh_reconstruction(structure, bundle)
    assert pq.read_table(structure.data_parquet_path, filters=evidence_filter).replace_schema_metadata(None).equals(evidence)
    metadata = read_metadata(path=structure.data_parquet_path)
    run = metadata.runs[run_id]
    assert run.models['standard_human'] == model
    channels = {c.kind: c for c in run.channels if c.source == 'model:standard_human'}
    products = {kind: read_saved_channel(structure=structure, run_id=run_id, metadata=metadata, channel=channels[kind])
        for kind in (ChannelKind.MAPPED_KEYPOINTS_3D, ChannelKind.LANDMARKS_3D, ChannelKind.SEGMENT_ORIGINS, ChannelKind.ROTATIONS_WORLD)}
    mapped, landmarks, origins, rotations = products.values()
    assert mapped.frames == landmarks.frames == origins.frames == rotations.frames
    assert mapped.timestamps_s == landmarks.timestamps_s == origins.timestamps_s == rotations.timestamps_s
    assert mapped.channel.components == landmarks.channel.components == dict.fromkeys('xyz', 'mm')
    common = np.isfinite(mapped.values).all(axis=-1) & np.isfinite(landmarks.values).all(axis=-1)
    assert np.any(np.linalg.norm(mapped.values[common] - landmarks.values[common], axis=-1) > 1.)
    fit = next(f.fit for f in run.scale_fits if f.source == 'model:standard_human')
    assert_saved_weighted_geometry(bundle=bundle, fit=fit, mapped=mapped, landmarks=landmarks,
                                  origins=origins, rotations=rotations)
    manifest = playback_manifest(structure.data_parquet_path)
    playback = next(r for r in manifest.runs if r.run_id == run_id)
    assert all(channel in playback.channels for channel in channels.values())
