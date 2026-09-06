"""Completion follows real numerical work and fails atomically for mismatched inputs."""

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellytracker.core.data_primitives.keypoints import Keypoints
from skellytracker.core.data_primitives.observation import Observation, StageObservation

from freemocap.core.pipeline.posthoc.processing_request import ProcessingStage
from freemocap.core.pipeline.posthoc.video_group_helper import VideoMetadata
from freemocap.core.reconstruction.posthoc_reconstruction import (
    reconstruct_skeletons_for_recording,
    reconstruct_skeletons_with_fits,
)
from freemocap.core.reconstruction.posthoc_timing import PosthocTimingReport
from freemocap.core.reconstruction.recording_reconstruction import (
    RecordingReconstructionInput,
)
from freemocap.core.recording.observation_recording_models import (
    ObservationRecordingRequest,
    ObservationGroup,
    TrackerRecordingDefinition,
)
from freemocap.core.recording.posthoc_observation_recording import (
    publish_posthoc_observations,
)
from freemocap.core.recording.recorded_model import RecordedModel
from freemocap.core.recording.reconstruction_recording import (
    ReconstructionRecording,
    ReconstructionSourceDefinition,
)
from freemocap.core.recording.saved_reconstruction import (
    SavedPointPolicy,
    SavedReconstructionRequest,
    read_saved_reconstruction,
)
from freemocap.core.recording.spatial_point_series import (
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
        models=(RecordedModel.from_bundle(bundle),),
        reconstructions=(
            ReconstructionRecording(
                sensor_group="mocap",
                reference=spatial.definition.reference,
                definition=ReconstructionSourceDefinition.from_bundle(bundle),
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
