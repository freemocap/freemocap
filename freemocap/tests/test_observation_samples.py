"""Named detector observations and mixed-rate timing survive canonical storage."""

from itertools import chain
from pathlib import Path

import numpy as np
import pyarrow as pa
import pytest
from skellytracker.core.data_primitives.keypoints import Keypoints
from skellytracker.core.data_primitives.observation import Observation, StageObservation

from freemocap.core.pipeline.posthoc.processing_request import ProcessingStage
from freemocap.core.recording.observation_samples import (
    TimedObservation,
    observation_batches,
    timing_batches,
)
from freemocap.core.recording.recording_metadata import (
    Channel,
    RecordingMetadata,
    RunDescriptor,
    SensorGroup,
    Source,
)
from freemocap.core.recording.recording_reader import read_batches
from freemocap.core.recording.recording_writer import (
    publish_recording,
    recording_write_lock,
)
from freemocap.system.recording_structure.recording_structure import RecordingStructure


def overlay_channel() -> Channel:
    return Channel(
        sensor_group="mocap",
        source="tracker",
        reference_frame="camera_image",
        kind="OVERLAY_2D",
        names=("body.wrist", "hand.tip"),
        components={"x": "px", "y": "px", "visibility": "1"},
        stage=ProcessingStage.OBSERVATIONS,
    )


def observation(*, frame: int) -> Observation:
    return Observation(
        frame_number=frame,
        image_size=(480, 640),
        stages={
            "body": StageObservation(
                name="body",
                keypoints=Keypoints(
                    names=("wrist",),
                    xyz=np.array([[12.5, 25.0, 0.0]]),
                    visibility=np.array([0.75]),
                ),
                children={
                    "hand": StageObservation(
                        name="hand",
                        keypoints=Keypoints(
                            names=("tip",),
                            xyz=np.array([[np.nan, np.nan, 0.0]]),
                            visibility=np.array([0.0]),
                        ),
                    )
                },
            )
        },
    )


def test_observations_and_mixed_rate_timing_round_trip(tmp_path: Path) -> None:
    overlay = overlay_channel()
    timing = Channel(
        sensor_group="eye",
        source="eye_clock",
        reference_frame=None,
        kind="TIMESTAMPS",
        names=("capture",),
        components={"timestamp_s": "s"},
        stage=ProcessingStage.TIMING,
    )
    metadata = RecordingMetadata(
        recording_id="recording",
        selected_run_id=0,
        runs={
            0: RunDescriptor(
                sensor_groups={
                    "mocap": SensorGroup(
                        clock_description="capture clock", sample_count=2
                    ),
                    "eye": SensorGroup(
                        clock_description="mapped eye clock", sample_count=8
                    ),
                },
                sources={
                    "tracker": Source(kind="tracker", definition={}),
                    "eye_clock": Source(kind="timing", definition={}),
                },
                reference_frames={"camera_image": {"width": 640, "height": 480}},
                models={},
                processing={},
                channels=(overlay, timing),
            )
        },
    )
    capture_times = (0.001, 0.035)
    eye_times = tuple(0.002 + index / 120 for index in range(8))
    overlays = list(
        observation_batches(
            samples=[
                TimedObservation(
                    observation=observation(frame=10),
                    capture_timestamp_s=capture_times[0],
                ),
                TimedObservation(
                    observation=Observation(frame_number=11, image_size=(480, 640)),
                    capture_timestamp_s=capture_times[1],
                ),
            ],
            channel=overlay,
            run_id=0,
            batch_size=2,
        )
    )
    assert all(batch.num_rows <= 2 for batch in overlays)
    structure = RecordingStructure(base_directory=tmp_path, recording_name="recording")
    with recording_write_lock(structure=structure):
        publish_recording(
            structure=structure,
            metadata=metadata,
            batches=chain(
                overlays,
                timing_batches(
                    samples=enumerate(eye_times), channel=timing, run_id=0, batch_size=3
                ),
            ),
        )
    rows = pa.Table.from_batches(
        list(
            read_batches(
                path=structure.data_parquet_path,
                run_id=0,
                sensor_groups=("mocap", "eye"),
            )
        )
    ).to_pylist()
    assert [row["value"] for row in rows if row["sensor_group"] == "eye"] == list(
        eye_times
    )
    wrist = [
        row for row in rows if row["name"] == "body.wrist" and row["component"] == "x"
    ]
    assert [row["timestamp_s"] for row in wrist] == list(capture_times)
    assert [row["frame_number"] for row in wrist] == [10, 11]
    assert [row["value"] for row in wrist] == [12.5, None]
    assert all(
        row["value"] is None
        for row in rows
        if row["name"] == "hand.tip" and row["component"] in ("x", "y")
    )


@pytest.mark.parametrize("timestamp", [float("nan"), float("inf"), 0.1])
def test_invalid_or_repeated_capture_time_fails(timestamp: float) -> None:
    with pytest.raises(ValueError, match="Capture timestamps"):
        list(
            observation_batches(
                samples=[
                    TimedObservation(
                        observation=observation(frame=0), capture_timestamp_s=0.1
                    ),
                    TimedObservation(
                        observation=observation(frame=1), capture_timestamp_s=timestamp
                    ),
                ],
                channel=overlay_channel(),
                run_id=0,
                batch_size=2,
            )
        )


def test_unknown_points_fail() -> None:
    channel = overlay_channel().model_copy(update={"names": ("body.wrist",)})
    with pytest.raises(ValueError, match="undeclared"):
        list(
            observation_batches(
                samples=[
                    TimedObservation(
                        observation=observation(frame=0), capture_timestamp_s=0.0
                    )
                ],
                channel=channel,
                run_id=0,
                batch_size=2,
            )
        )
