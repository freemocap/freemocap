"""Completion follows real numerical work and fails atomically for mismatched inputs."""

from dataclasses import replace
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
import pytest
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellytracker.core.data_primitives.keypoints import Keypoints
from skellytracker.core.data_primitives.observation import Observation, StageObservation

from freemocap.core.pipeline.posthoc.processing_request import ProcessingStage
from freemocap.core.pipeline.posthoc.stage_execution_plan import StageExecutionPlan, retained_run
from freemocap.core.types.channel_kind import ChannelKind
from freemocap.core.reconstruction.posthoc_filtering import PosthocFilterConfig, filter_recording_points
from freemocap.core.pipeline.posthoc.video_group_helper import VideoMetadata
from freemocap.core.reconstruction.posthoc_reconstruction import (
    reconstruct_skeletons_for_recording,
    reconstruct_skeletons_with_fits,
)
from freemocap.core.reconstruction.posthoc_timing import PosthocTimingReport
from freemocap.core.reconstruction.recording_reconstruction import (
    RecordingReconstructionInput,
)
from freemocap.core.recording.result_processing.observation_inputs import (
    ObservationRecordingRequest,
    ObservationGroup,
    TrackerRecordingDefinition,
)
from freemocap.core.recording.result_processing.observation_publication import (
    publish_posthoc_observations,
)
from freemocap.core.recording.data_descriptors.recording_model import RecordedModel
from freemocap.core.recording.sample_encoding.reconstruction_samples import (
    ReconstructionRecording,
    ReconstructionSourceDefinition,
)
from freemocap.core.recording.result_processing.saved_reconstruction import (
    SavedPointPolicy,
    SavedReconstructionRequest,
    read_saved_reconstruction,
)
from freemocap.core.recording.sample_encoding.spatial_points import (
    PointSeriesDefinition,
    SpatialPointSeries,
    SpatialReference,
)
from freemocap.core.skeletons.standard_human_skeleton import build_standard_human_bundle
from freemocap.system.recording_structure.recording_structure import RecordingStructure
from freemocap.tests.test_model_scale_in_the_loop import _standing_keypoints


@pytest.fixture
def publication(tmp_path: Path) -> ObservationRecordingRequest:
    bundle = build_standard_human_bundle(detector_type="rtmpose")
    points = _standing_keypoints()
    values = np.stack(
        [np.stack(list(points.values())), np.full((len(points), 3), np.nan)]
    )
    numerical = RecordingReconstructionInput(
        bundles=(bundle,),
        keypoint_names=tuple(points),
        keypoints_3d=values,
        compute_center_of_mass=True,
        timing=PosthocTimingReport(),
    )
    result = reconstruct_skeletons_for_recording(numerical)[bundle.model_id]
    spatial = SpatialPointSeries(
        definition=PointSeriesDefinition(
            kind=ChannelKind.RAW_KEYPOINTS_3D,
            sensor_group="mocap",
            source=bundle.detector_type,
            names=tuple(points),
            reference=SpatialReference.for_camera_count(1),
        ),
        values=values,
    )
    frames = [
        {
            "camera": Observation(
                frame_number=index,
                image_size=(48, 64),
                stages={
                    "body": StageObservation(
                        name="body",
                        keypoints=Keypoints(
                            names=("wrist",),
                            xyz=np.array([[1.0, 2.0, 0.0]]),
                            visibility=np.ones(1),
                        ),
                    )
                },
            )
        }
        for index in range(2)
    ]
    return ObservationRecordingRequest(
        reprojection=None,
        filtering=None,
        models=(RecordedModel.from_bundle(bundle),),
        reconstructions=(
            ReconstructionRecording(
                sensor_group="mocap",
                reference=spatial.definition.reference,
                definition=ReconstructionSourceDefinition.from_bundle(bundle, tracker_source=bundle.detector_type,
                    point_kind=ChannelKind.RAW_KEYPOINTS_3D),
                result=result,
            ),
        ),
        recording=RecordingInfo(
            recording_name="recording", recording_directory=str(tmp_path)
        ),
        group=ObservationGroup(
            name="mocap",
            frames=frames,
            videos={
                "camera": VideoMetadata(
                    file_path=tmp_path / "camera.mp4",
                    width=64,
                    height=48,
                    fps=30.0,
                    frame_count=2,
                    end_frame=2,
                    fourcc="mp4v",
                    duration_seconds=2 / 30,
                )
            },
        ),
        tracker=TrackerRecordingDefinition(
            name=bundle.detector_type, point_names=("body.wrist",), configuration={}
        ),
        spatial_series=(spatial,),
        camera_geometry=(),
    )


def test_completion_roundtrip_overwrite_and_failed_publication(
    publication: ObservationRecordingRequest, tmp_path: Path
) -> None:
    metadata = publish_posthoc_observations(publication)
    assert {item.stage for item in metadata.runs[0].checkpoints} == {
        ProcessingStage.FILTERING,
        ProcessingStage.SCALE_FIT,
        ProcessingStage.RECONSTRUCTION,
        ProcessingStage.BIOMECHANICS,
    }
    structure = RecordingStructure(base_directory=tmp_path, recording_name="recording")
    loaded = read_saved_reconstruction(
        SavedReconstructionRequest(
            structure=structure,
            run_id=0,
            sensor_group="mocap",
            point_source=publication.tracker.name,
            model_id=publication.models[0].model_id,
            point_policy=SavedPointPolicy.IDENTITY,
            compute_center_of_mass=True,
        )
    )
    assert loaded.fit.inputs == publication.reconstructions[0].result.fit_inputs
    overwritten = publish_posthoc_observations(publication)
    assert overwritten.runs[0].checkpoints == metadata.runs[0].checkpoints
    original = structure.data_parquet_path.read_bytes()
    changed = replace(
        publication.spatial_series[0], values=publication.spatial_series[0].values + 1.0
    )
    with pytest.raises(ValueError, match="differ from"):
        publish_posthoc_observations(replace(publication, spatial_series=(changed,)))
    assert structure.data_parquet_path.read_bytes() == original
    with pytest.raises(ValueError, match="inputs changed"):
        reconstruct_skeletons_with_fits(
            request=replace(loaded.numerical_input, keypoints_3d=changed.values),
            fits={publication.models[0].model_id: loaded.fit.for_reconstruction()},
        )


def test_refitting_changed_points_changes_completion(
    publication: ObservationRecordingRequest,
) -> None:
    before = publish_posthoc_observations(publication)
    changed = replace(
        publication.spatial_series[0], values=publication.spatial_series[0].values * 1.2
    )
    numerical = RecordingReconstructionInput(
        bundles=(publication.models[0].to_bundle(),),
        keypoint_names=changed.definition.names,
        keypoints_3d=changed.values,
        compute_center_of_mass=True,
        timing=PosthocTimingReport(),
    )
    result = reconstruct_skeletons_for_recording(numerical)[
        publication.models[0].model_id
    ]
    after = publish_posthoc_observations(
        replace(
            publication,
            spatial_series=(changed,),
            reconstructions=(replace(publication.reconstructions[0], result=result),),
        )
    )
    assert before.runs[0].checkpoints != after.runs[0].checkpoints
    assert (
        after.runs[0].scale_fits[0].fit.fitted_scale
        != before.runs[0].scale_fits[0].fit.fitted_scale
    )


def test_filtered_points_reload_with_their_fit_and_preserve_raw_data(
    publication: ObservationRecordingRequest, tmp_path: Path,
) -> None:
    count = 90
    times = np.arange(count, dtype=np.float64) / 30
    raw_values = np.repeat(publication.spatial_series[0].values[:1], repeats=count, axis=0)
    raw_values[:, :, 0] += 5 * np.sin(2 * np.pi * 10 * times[:, None])
    filtered = filter_recording_points(points=raw_values, timestamps_s=times, config=PosthocFilterConfig())
    raw = replace(publication.spatial_series[0], values=raw_values)
    processed = replace(raw, definition=raw.definition.model_copy(update={"kind": ChannelKind.KEYPOINTS_3D}),
        values=filtered.points)
    bundle = publication.models[0].to_bundle()
    result = reconstruct_skeletons_for_recording(RecordingReconstructionInput(
        bundles=(bundle,), keypoint_names=processed.definition.names, keypoints_3d=processed.values,
        compute_center_of_mass=True, timing=PosthocTimingReport(),
    ))[bundle.model_id]
    group = replace(publication.group,
        frames=[{"camera": replace(publication.group.frames[0]["camera"], frame_number=index)} for index in range(count)],
        videos={"camera": publication.group.videos["camera"].model_copy(update={
            "frame_count": count, "end_frame": count, "duration_seconds": count / 30,
        })})
    request = replace(publication, group=group, filtering=filtered.report, spatial_series=(raw, processed),
        reconstructions=(replace(publication.reconstructions[0], result=result,
            definition=publication.reconstructions[0].definition.model_copy(update={"point_kind": ChannelKind.KEYPOINTS_3D})),))
    metadata = publish_posthoc_observations(request)
    assert metadata.runs[0].processing["mocap"]["filtering"]["filtered_runs"] > 0
    structure = RecordingStructure(base_directory=tmp_path, recording_name="recording")
    saved_request = SavedReconstructionRequest(
        structure=structure, run_id=0, sensor_group="mocap", point_source=publication.tracker.name,
        model_id=bundle.model_id, point_policy=SavedPointPolicy.FILTERED, compute_center_of_mass=True,
    )
    saved = read_saved_reconstruction(saved_request)
    raw_rows = pq.read_table(source=structure.data_parquet_path, columns=["value"], filters=[
        ("channel", "=", ChannelKind.RAW_KEYPOINTS_3D), ("source", "=", publication.tracker.name),
    ])
    np.testing.assert_array_equal(raw_rows["value"].to_numpy().reshape(raw_values.shape), raw_values)
    np.testing.assert_array_equal(saved.points.values, filtered.points)
    assert not np.allclose(saved.points.values, raw_values)
    assert saved.fit.inputs == result.fit_inputs
    with pytest.raises(ValueError, match="point policy"):
        read_saved_reconstruction(replace(saved_request, point_policy=SavedPointPolicy.IDENTITY))
    assert publish_posthoc_observations(request).runs[0].checkpoints == metadata.runs[0].checkpoints
    original_bytes = structure.data_parquet_path.read_bytes()
    missing = raw_values.copy()
    missing[0, 0] = np.nan
    with pytest.raises(ValueError, match="missing observations"):
        publish_posthoc_observations(replace(request, spatial_series=(replace(raw, values=missing), processed)))
    assert structure.data_parquet_path.read_bytes() == original_bytes


def test_filter_settings_change_checkpoint_even_when_short_runs_are_unchanged(
    publication: ObservationRecordingRequest,
) -> None:
    raw = publication.spatial_series[0]
    processed = replace(raw, definition=raw.definition.model_copy(update={"kind": ChannelKind.KEYPOINTS_3D}))
    reconstruction = replace(publication.reconstructions[0],
        definition=publication.reconstructions[0].definition.model_copy(update={"point_kind": ChannelKind.KEYPOINTS_3D}))
    checkpoints: list[dict[ProcessingStage, str]] = []
    for cutoff in (3., 6.):
        result = filter_recording_points(points=raw.values, timestamps_s=np.array([0., 1 / 30]),
            config=PosthocFilterConfig(cutoff=cutoff))
        saved = publish_posthoc_observations(replace(publication, filtering=result.report,
            spatial_series=(raw, processed), reconstructions=(reconstruction,)))
        checkpoints.append({item.stage: item.signature for item in saved.runs[0].checkpoints})
    assert checkpoints[0][ProcessingStage.FILTERING] != checkpoints[1][ProcessingStage.FILTERING]
    assert checkpoints[0][ProcessingStage.SCALE_FIT] == checkpoints[1][ProcessingStage.SCALE_FIT]
    retained = retained_run(base=saved.runs[0], plan=StageExecutionPlan(
        base_run_id=0, target_run_id=0, sensor_groups=("mocap",), execute=(ProcessingStage.FILTERING,),
        invalidate=(ProcessingStage.FILTERING, ProcessingStage.SCALE_FIT, ProcessingStage.RECONSTRUCTION, ProcessingStage.BIOMECHANICS),
    ))
    assert "filtering" not in retained.processing["mocap"]
    assert any(channel.kind == ChannelKind.RAW_KEYPOINTS_3D for channel in retained.channels)
    assert not any(channel.kind == ChannelKind.KEYPOINTS_3D for channel in retained.channels)
