"""Every batch frame uses the complete recording's scale evidence."""

from freemocap.core.reconstruction.recording_reconstruction import (
    RecordingReconstructionInput,
)
import numpy as np
from numpy import testing as npt
import pytest
from freemocap.core.recording.data_descriptors.recording_model import RecordedModel
from freemocap.core.recording.parquet_storage.parquet_reader import (
    read_static_channels,
    static_samples,
)
from freemocap.core.types.channel_kind import ChannelKind
from pathlib import Path
from freemocap.core.recording.sample_encoding.reconstruction_samples import (
    ReconstructionRecording,
    ReconstructionSourceDefinition,
)
from freemocap.core.recording.sample_encoding.spatial_points import (
    SpatialReference,
    SpatialPointSeries,
    PointSeriesDefinition,
)
from freemocap.core.recording.result_processing.saved_reconstruction import (
    SavedReconstructionRequest,
    SavedPointPolicy,
    read_saved_reconstruction,
)
from freemocap.core.recording.sample_encoding.channel_series import SeriesSampling
from freemocap.core.recording.data_descriptors.recording_descriptor import (
    RunDescriptor,
    RecordingMetadata,
    SensorGroup,
    Source,
    SourceKind,
)
from freemocap.core.recording.parquet_storage.parquet_writer import (
    publish_recording,
    recording_write_lock,
)
from freemocap.core.recording.parquet_storage.parquet_reader import read_metadata
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
    )[bundle.model_id]
    assert results.scale_fit is not None
    assert results.frame_count == len(recording)
    assert results.channel_tensor("MAPPED_KEYPOINTS_3D").companion_values("entry_presence").any(axis=(1, 2)).all()
    # The fitted scale and segment lengths are stored once for the whole recording.
    assert results.scale_fit.fitted_scale > 0
    assert all(length > 0 for length in results.scale_fit.segment_lengths.values())


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
    assert not results[bundle.model_id].channel_tensor("MAPPED_KEYPOINTS_3D").companion_values("entry_presence").any()
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
        definition=ReconstructionSourceDefinition.from_bundle(bundle, tracker_source=bundle.detector_type,
            point_kind=ChannelKind.RAW_KEYPOINTS_3D),
        result=expected,
    )
    structure = RecordingStructure(base_directory=tmp_path, recording_name="recording")
    raw = SpatialPointSeries(
        definition=PointSeriesDefinition(
            kind=ChannelKind.RAW_KEYPOINTS_3D,
            sensor_group="mocap",
            source=bundle.detector_type,
            names=request.keypoint_names,
            reference=publication.reference,
        ),
        values=request.keypoints_3d,
    )
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
                sources={
                    publication.definition.source_name: publication.definition.to_source(),
                    bundle.detector_type: Source(
                        kind=SourceKind.TRACKER, definition={}
                    ),
                },
                reference_frames=publication.reference_frames(),
                models={bundle.model_id: RecordedModel.from_bundle(bundle)},
                processing={},
                channels=(*publication.channels(), raw.definition.to_channel()),
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
                for series in (*publication.series(), raw)
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
    loaded_run = read_metadata(path=structure.data_parquet_path).runs[0]
    loaded = loaded_run.scale_fits[0]
    static = {item.channel.kind: item for item in read_static_channels(loaded_run)}
    assert set(static) == {
        ChannelKind.MODEL_SCALE,
        ChannelKind.SEGMENT_SCALES,
        ChannelKind.SEGMENT_LENGTHS,
    }
    length_rows = static_samples(
        channel=static[ChannelKind.SEGMENT_LENGTHS],
        run_id=0,
        frame_number=5,
        timestamp_s=0.1,
    )
    assert length_rows.num_rows == len(bundle.skeleton.segments)
    assert length_rows.column("value").to_pylist() == list(
        expected.scale_fit.segment_lengths.values()
    )
    assert loaded == publication.to_scale_fit()
    assert (
        loaded_run.models[bundle.model_id] == metadata.runs[0].models[bundle.model_id]
    )

    def forbid_definition_file(self: Path, *args: object, **kwargs: object) -> str:
        raise AssertionError(
            "Restoring a recorded model must not read definition files"
        )

    monkeypatch.setattr(Path, "read_text", forbid_definition_file)

    def forbid_fitting(*args, **kwargs) -> None:
        raise AssertionError("Saved-fit reconstruction must not create a scale fitter")

    monkeypatch.setattr(
        posthoc_reconstruction, "fit_skeletons_for_recording", forbid_fitting
    )
    saved = read_saved_reconstruction(
        SavedReconstructionRequest(
            structure=structure,
            run_id=0,
            sensor_group="mocap",
            point_source=bundle.detector_type,
            model_id=bundle.model_id,
            point_policy=SavedPointPolicy.IDENTITY,
            compute_center_of_mass=True,
        )
    )
    assert saved.points.frames == (5, 6, 7)
    assert saved.points.timestamps_s == (0.1, 0.15, 0.19)
    npt.assert_array_equal(saved.numerical_input.keypoints_3d, request.keypoints_3d)
    actual = reconstruct_skeletons_with_fits(
        request=saved.numerical_input,
        fits={bundle.model_id: saved.fit.for_reconstruction()},
    )[bundle.model_id]
    assert expected.scale_fit == actual.scale_fit
    assert expected.frame_count == actual.frame_count
    for before, after in zip(expected.channel_tensors, actual.channel_tensors, strict=True):
        assert before.tensor_layout == after.tensor_layout
        npt.assert_array_equal(before.data_values, after.data_values)
        for before_metadata, after_metadata in zip(before.companion_tensors, after.companion_tensors, strict=True):
            assert before_metadata.metadata_name == after_metadata.metadata_name
            npt.assert_array_equal(before_metadata.data_values, after_metadata.data_values)
