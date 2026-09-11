"""Posthoc ingestion reads capture sidecars or infers timing for imported video."""

import json
from pathlib import Path
from freemocap.core.recording.parquet_storage.parquet_reader import read_metadata
from freemocap.core.recording.playback_queries import playback_manifest

from freemocap.core.recording.result_processing.observation_inputs import (
    BOX_COMPONENTS,
    DetectorRecordingDefinition,
    ObservationRecordingRequest,
    ObservationGroup,
    TrackerRecordingDefinition,
    camera_group_name,
)
import numpy as np
from freemocap.core.recording.sample_encoding.spatial_points import (
    SpatialPointSeries,
    PointSeriesDefinition,
    SpatialReference,
)
import pyarrow as pa
import pytest
from freemocap.core.types.channel_kind import ChannelKind
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellytracker.core.data_primitives.bounding_box import BoundingBox
from skellytracker.core.data_primitives.keypoints import Keypoints
from skellytracker.core.data_primitives.observation import Observation, StageObservation

from freemocap.core.pipeline.posthoc.video_group_helper import VideoMetadata
from freemocap.core.recording.result_processing.observation_publication import (
    publish_posthoc_observations,
)
from freemocap.core.recording.parquet_storage.parquet_reader import read_batches
from freemocap.system.recording_structure.recording_structure import RecordingStructure


@pytest.mark.parametrize("recorded", [False, True])
def test_ingestion_and_overwrite(tmp_path: Path, recorded: bool) -> None:
    info = RecordingInfo(recording_name="recording", recording_directory=str(tmp_path))
    videos = {
        camera: VideoMetadata(
            file_path=tmp_path / f"{camera}.mp4",
            width=64,
            height=48,
            fps=30.0,
            frame_count=2,
            end_frame=2,
            fourcc="mp4v",
            duration_seconds=2 / 30,
        )
        for camera in ("a", "b")
    }
    frames = [
        {
            camera: Observation(
                frame_number=frame,
                image_size=(48, 64),
                stages={
                    "body": StageObservation(
                        name="body",
                        keypoints=Keypoints(
                            names=("wrist",),
                            xyz=np.array([[10.0, 20.0, 0.0]]),
                            visibility=np.array([1.0]),
                        ),
                    )
                },
            )
            for camera in videos
        }
        for frame in range(2)
    ]
    timing_references = {
        camera: Path(info.camera_timestamps_file_path_from_camera_id(camera)).relative_to(Path(info.full_recording_path)).as_posix()
        for camera in videos
    }
    if recorded:
        Path(info.recording_info_path).write_text(json.dumps({"camera_timing": timing_references}), encoding="utf-8")
        for index, camera in enumerate(videos):
            Path(info.camera_timestamps_file_path_from_camera_id(camera)).write_text(
                "# recording_frame_number,timestamp.from_recording_start.sec\n"
                f"0,{0.001 + index * 0.001}\n1,{0.04 + index * 0.001}\n",
                encoding="utf-8",
            )
    for iteration in range(2):
        points = SpatialPointSeries(
            definition=PointSeriesDefinition(
                kind=ChannelKind.RAW_KEYPOINTS_3D,
                sensor_group="mocap",
                source="tracker",
                names=("wrist",),
                reference=SpatialReference.for_camera_count(len(videos)),
            ),
            values=np.array(
                [[[10.0 + iteration, 20.0, 30.0]], [[np.nan, np.nan, np.nan]]]
            ),
        )
        metadata = publish_posthoc_observations(
            ObservationRecordingRequest(
        reprojection=None,
                filtering=None,
                models=(),
                reconstructions=(),
                camera_geometry=(),
                recording=info,
                spatial_series=(points,),
                group=ObservationGroup(name="mocap", frames=frames, videos=videos),
                tracker=TrackerRecordingDefinition(
                    name="tracker", point_names=("body.wrist",), configuration={}
                ),
            )
        )
        assert metadata.runs[0].sources["camera:a"].definition["timing_method"] == (
            "recorded" if recorded else "inferred_from_fps"
        )
    structure = RecordingStructure(base_directory=tmp_path, recording_name="recording")
    assert read_metadata(path=structure.data_parquet_path) == metadata
    media = playback_manifest(structure.data_parquet_path).runs[0].media
    assert tuple(item.video_filename for item in media) == ("a.mp4", "b.mp4")
    assert all(item.nominal_fps == 30.0 and item.timeline.sensor_group == "mocap" for item in media)
    for index, item in enumerate(media):
        expected = (0.001 + index * 0.001, 0.04 + index * 0.001) if recorded else (0.0, 1 / 30)
        assert item.timeline.timestamps_s == pytest.approx(expected)
    rows = pa.Table.from_batches(
        list(
            read_batches(
                path=structure.data_parquet_path, run_id=0, sensor_groups=("mocap",)
            )
        )
    ).to_pylist()
    times = [
        row["timestamp_s"]
        for row in rows
        if row["channel"] == "OVERLAY_2D"
        and row["reference_frame"] == "camera:a:image"
        and row["component"] == "x"
    ]
    assert times == ([0.001, 0.04] if recorded else [0.0, 1 / 30])
    spatial = [
        row
        for row in rows
        if row["channel"] == "RAW_KEYPOINTS_3D" and row["component"] == "x"
    ]
    assert [row["value"] for row in spatial] == [11.0, None]
    assert all(row["units"] == "mm" for row in spatial)
    assert [row["timestamp_s"] for row in spatial] == pytest.approx(
        [0.0015, 0.0405] if recorded else [0.0, 1 / 30]
    )
    original = structure.data_parquet_path.read_bytes()
    Path(info.camera_timestamps_file_path_from_camera_id("a")).write_text(
        "broken\n", encoding="utf-8"
    )
    Path(info.recording_info_path).write_text(json.dumps({"camera_timing": timing_references}), encoding="utf-8")
    with pytest.raises(ValueError, match="Missing recording timing columns"):
        publish_posthoc_observations(
            ObservationRecordingRequest(
        reprojection=None,
                filtering=None,
                models=(),
                reconstructions=(),
                camera_geometry=(),
                recording=info,
                spatial_series=(),
                group=ObservationGroup(name="mocap", frames=frames, videos=videos),
                tracker=TrackerRecordingDefinition(
                    name="tracker", point_names=("body.wrist",), configuration={}
                ),
            )
        )
    assert structure.data_parquet_path.read_bytes() == original


def test_detector_boxes_are_published_beside_the_points_they_cropped(tmp_path: Path) -> None:
    """A declared detector adds a BOXES_2D channel per camera, sourced to the detector.

    The boxes and the keypoints come from different models, so they are filed under
    different sources — that is what lets a reader tell which produced which.
    """
    info = RecordingInfo(recording_name="recording", recording_directory=str(tmp_path))
    videos = {
        "a": VideoMetadata(
            file_path=Path(info.videos_folder) / "a.mp4", width=64, height=48, fps=30.0,
            frame_count=2, end_frame=2, fourcc="mp4v", duration_seconds=2 / 30,
        )
    }
    frames = [
        {
            "a": Observation(
                frame_number=frame,
                image_size=(48, 64),
                stages={
                    "body": StageObservation(
                        name="body",
                        keypoints=Keypoints(
                            names=("wrist",),
                            xyz=np.array([[10.0, 20.0, 0.0]]),
                            visibility=np.array([1.0]),
                        ),
                        bounding_boxes=[
                            BoundingBox(x1=4.0, y1=6.0, x2=40.0, y2=44.0, confidence=0.9)
                        ],
                        # The detector ran on the first frame only; the second frame
                        # reuses the tracked crop, which is the healthy steady state.
                        detector_ran=frame == 0,
                    )
                },
            )
        }
        for frame in range(2)
    ]
    group = camera_group_name(videos)
    metadata = publish_posthoc_observations(
        ObservationRecordingRequest(
            reprojection=None, filtering=None, models=(), reconstructions=(),
            camera_geometry=(), recording=info, spatial_series=(),
            group=ObservationGroup(name=group, frames=frames, videos=videos),
            tracker=TrackerRecordingDefinition(
                name="keypoint_model:rtmw-x-l_256x192",
                point_names=("body.wrist",), configuration={},
            ),
            detector=DetectorRecordingDefinition(
                name="object_detector:yolox-m", box_names=("body",), configuration={},
            ),
        )
    )
    run = metadata.runs[0]
    assert "object_detector:yolox-m" in run.sources
    box_channels = [c for c in run.channels if c.kind == ChannelKind.BOXES_2D]
    assert [c.source for c in box_channels] == ["object_detector:yolox-m"]
    assert box_channels[0].names == ("body",)

    structure = RecordingStructure(base_directory=tmp_path, recording_name="recording")
    rows = pa.Table.from_batches(
        list(read_batches(path=structure.data_parquet_path, run_id=0, sensor_groups=(group,)))
    ).to_pylist()
    boxes = [row for row in rows if row["channel"] == "BOXES_2D"]
    assert len(boxes) == 2 * len(BOX_COMPONENTS)
    assert {row["source"] for row in boxes} == {"object_detector:yolox-m"}
    assert {row["reference_frame"] for row in boxes} == {"camera:a:image"}
    corners = {
        row["component"]: row["value"] for row in boxes if row["frame_number"] == 0
    }
    assert (corners["x1"], corners["y1"], corners["x2"], corners["y2"]) == (4.0, 6.0, 40.0, 44.0)
    ran = {
        row["frame_number"]: row["value"]
        for row in boxes if row["component"] == "detector_ran"
    }
    assert ran == {0: 1.0, 1: 0.0}
