"""Reconstruct copies of saved reference data, without detection or optimization."""

import os
from pathlib import Path
import shutil

import numpy as np
import pyarrow.parquet as pq
import pytest
from numpy.testing import assert_allclose
from skellyforge.core.math.geometry.rotation_quaternion import RotationQuaternion

from freemocap.core.recording.parquet_storage.parquet_reader import read_metadata
from freemocap.core.recording.result_processing.saved_reconstruction import read_saved_channel
from freemocap.core.recording.playback_queries import playback_manifest
from freemocap.core.types.channel_kind import ChannelKind
from freemocap.system.recording_structure.recording_structure import RecordingStructure
from freemocap.tests.refresh_recording_reconstruction import refresh_reconstruction


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
    origin_indices = {name: i for i, name in enumerate(origins.channel.names)}
    rotation_indices = {name: i for i, name in enumerate(rotations.channel.names)}
    landmark_indices = {name: i for i, name in enumerate(landmarks.channel.names)}
    for joint in bundle.skeleton.joints.values():
        child = origins.values[:, origin_indices[joint.child.name]]
        attachment = landmarks.values[:, landmark_indices[joint.connect_at.name]]
        present = np.isfinite(child).all(axis=-1)
        assert_allclose(child[present], attachment[present], atol=1e-8)
        assert not np.any(present & ~np.isfinite(origins.values[:, origin_indices[joint.parent.name]]).all(axis=-1))
    for index, name in enumerate(landmarks.channel.names):
        landmark = bundle.skeleton.landmarks[name]
        for frame in range(len(landmarks.frames)):
            rotation = rotations.values[frame, rotation_indices[landmark.segment]]
            position = landmarks.values[frame, index]
            if not np.isfinite(rotation).all():
                assert np.isnan(position).all()
                continue
            expected = origins.values[frame, origin_indices[landmark.segment]] + RotationQuaternion.from_array(array=rotation).rotate_vector(
                vector=fit.segment_scales[landmark.segment] * landmark.local_position.array)
            assert_allclose(position, expected, atol=1e-8)
    manifest = playback_manifest(structure.data_parquet_path)
    playback = next(r for r in manifest.runs if r.run_id == run_id)
    assert all(channel in playback.channels for channel in channels.values())
