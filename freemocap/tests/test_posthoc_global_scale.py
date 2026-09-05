"""Every batch frame uses the complete recording's scale evidence."""

from freemocap.core.reconstruction.recording_reconstruction import (
    RecordingReconstructionInput,
)
import numpy as np
import pytest
from pathlib import Path
from freemocap.core.recording.reconstruction_recording import (
    ReconstructionRecording,
    ReconstructionSourceDefinition,
)
from freemocap.core.recording.spatial_point_series import SpatialReference
from freemocap.core.recording.channel_series import SeriesSampling
from freemocap.core.recording.recording_metadata import (
    RunDescriptor,
    RecordingMetadata,
    SensorGroup,
)
from freemocap.core.recording.recording_writer import (
    publish_recording,
    recording_write_lock,
)
from freemocap.core.recording.recording_reader import read_metadata
from freemocap.system.recording_structure.recording_structure import RecordingStructure
from freemocap.core.reconstruction.posthoc_reconstruction import (
    reconstruct_skeletons_with_fits,
)
from freemocap.core.reconstruction import posthoc_reconstruction

from freemocap.core.reconstruction.posthoc_reconstruction import (
    reconstruct_skeletons_for_recording,
)
from freemocap.core.reconstruction.posthoc_timing import PosthocTimingReport
from freemocap.core.skeletons.standard_human_skeleton import build_standard_human_bundle
from freemocap.tests.test_model_scale_in_the_loop import _standing_keypoints


def test_early_noisy_frames_use_the_same_fit_as_late_frames() -> None:
    points = _standing_keypoints()
    names = tuple(points)
    frame = np.stack(list(points.values()))
    recording = np.stack(
        [frame * scale for scale in (1.5, 1.4, 1.0, 1.0, 1.0, 1.0, 1.0)]
    )
    bundle = build_standard_human_bundle(detector_type="rtmpose")
    results = reconstruct_skeletons_for_recording(
        RecordingReconstructionInput(
            bundles=(bundle,),
            keypoint_names=names,
            keypoints_3d=recording,
            compute_center_of_mass=True,
            timing=PosthocTimingReport(),
        )
    )[bundle.model_id].frames
    assert all(result is not None for result in results)
    scales = [result.fitted_scale_mm for result in results if result is not None]
    assert scales[0] is not None
    assert len(set(scales)) == 1
    lengths = [result.segment_lengths for result in results if result is not None]
    assert all(value == lengths[0] for value in lengths)


def test_all_missing_recording_remains_missing() -> None:
    names = tuple(_standing_keypoints())
    bundle = build_standard_human_bundle(detector_type="rtmpose")
    results = reconstruct_skeletons_for_recording(
        RecordingReconstructionInput(
            bundles=(bundle,),
            keypoint_names=names,
            keypoints_3d=np.full((2, len(names), 3), np.nan),
            compute_center_of_mass=True,
            timing=PosthocTimingReport(),
        )
    )
    assert results[bundle.model_id].frames == (None, None)
    assert results[bundle.model_id].scale_fit is None


def test_saved_fit_reproduces_reconstruction_without_fitting(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    points = _standing_keypoints()
    bundle = build_standard_human_bundle(detector_type="rtmpose")
    request = RecordingReconstructionInput(
        bundles=(bundle,),
        keypoint_names=tuple(points),
        keypoints_3d=np.stack(
            [np.stack(list(points.values())) * scale for scale in (1.1, 1.0, 0.9)]
        ),
        compute_center_of_mass=True,
        timing=PosthocTimingReport(),
    )
    expected = reconstruct_skeletons_for_recording(request)[bundle.model_id]
    publication = ReconstructionRecording(
        sensor_group="mocap",
        reference=SpatialReference.for_camera_count(2),
        definition=ReconstructionSourceDefinition.from_bundle(bundle),
        result=expected,
    )
    structure = RecordingStructure(base_directory=tmp_path, recording_name="recording")
    metadata = RecordingMetadata(
        recording_id="recording",
        selected_run_id=0,
        runs={
            0: RunDescriptor(
                sensor_groups={
                    "mocap": SensorGroup(
                        clock_description="recording clock", sample_count=3
                    )
                },
                sources={bundle.model_id: publication.definition.to_source()},
                reference_frames={
                    publication.reference.name: publication.reference.model_dump(
                        mode="json"
                    )
                },
                models={},
                processing={},
                channels=tuple(publication.channels()),
                scale_fits=(publication.to_scale_fit(),),
            )
        },
    )
    with recording_write_lock(structure=structure):
        publish_recording(
            structure=structure,
            metadata=metadata,
            batches=(
                batch
                for series in publication.series()
                for batch in series.batches(
                    SeriesSampling(
                        frame_numbers=(5, 6, 7),
                        timestamps_s=(0.1, 0.15, 0.19),
                        run_id=0,
                        batch_size=5,
                    )
                )
            ),
        )
    loaded = read_metadata(path=structure.data_parquet_path).runs[0].scale_fits[0]
    assert loaded == publication.to_scale_fit()

    def forbid_fitting(*, window_frames: int) -> None:
        raise AssertionError("Saved-fit reconstruction must not create a scale fitter")

    monkeypatch.setattr(
        posthoc_reconstruction, "streaming_model_scale_source", forbid_fitting
    )
    actual = reconstruct_skeletons_with_fits(
        request=request, fits={bundle.model_id: loaded.fit}
    )[bundle.model_id]
    for before, after in zip(expected.frames, actual.frames, strict=True):
        assert before is not None and after is not None
        assert before.segment_lengths == after.segment_lengths
        assert before.fitted_scale_mm == after.fitted_scale_mm
        for name in before.landmarks:
            np.testing.assert_array_equal(before.landmarks[name], after.landmarks[name])
        for name in before.segment_rotations_world:
            np.testing.assert_array_equal(
                before.segment_rotations_world[name],
                after.segment_rotations_world[name],
            )
            np.testing.assert_array_equal(
                before.segment_rotations_local[name],
                after.segment_rotations_local[name],
            )
        np.testing.assert_array_equal(before.center_of_mass, after.center_of_mass)
