"""Bounding boxes survive canonical storage beside the points measured inside them.

Boxes were dropped at `Observation.to_keypoints()`, so nothing about the detector crop
reached disk and an over-eager redetect policy was invisible offline. `box_batches`
walks the stage tree instead, and holds to the same complete-coverage contract every
other channel does: a stage that detected nothing still emits its row, with nulls.
"""

from pathlib import Path

import pyarrow as pa
import pytest
from skellytracker.core.data_primitives.bounding_box import BoundingBox
from skellytracker.core.data_primitives.observation import Observation, StageObservation

from freemocap.core.pipeline.posthoc.processing_request import ProcessingStage
from freemocap.core.recording.data_descriptors.recording_descriptor import (
    Channel,
    RecordingMetadata,
    RunDescriptor,
    SensorGroup,
    Source,
)
from freemocap.core.recording.parquet_storage.parquet_reader import read_batches
from freemocap.core.recording.parquet_storage.parquet_writer import (
    publish_recording,
    recording_write_lock,
)
from freemocap.core.recording.result_processing.observation_inputs import BOX_COMPONENTS
from freemocap.core.recording.sample_encoding.observation_samples import (
    TimedObservation,
    box_batches,
)
from freemocap.system.recording_structure.recording_structure import RecordingStructure

GROUP = "camera_group:e9aa03"
SOURCE = "object_detector:yolox-m"
REFERENCE = "camera:3e59:image"
BOX = (512.0, 18.0, 791.0, 706.0)


def box_channel() -> Channel:
    return Channel(
        sensor_group=GROUP,
        source=SOURCE,
        reference_frame=REFERENCE,
        kind="BOXES_2D",
        names=("body",),
        components=BOX_COMPONENTS,
        stage=ProcessingStage.OBSERVATIONS,
    )


def observation(*, frame: int, with_box: bool, detector_ran: bool) -> Observation:
    return Observation(
        frame_number=frame,
        image_size=(720, 1280),
        stages={
            "body": StageObservation(
                name="body",
                bounding_boxes=(
                    [BoundingBox(x1=BOX[0], y1=BOX[1], x2=BOX[2], y2=BOX[3],
                                 confidence=0.93)]
                    if with_box else []
                ),
                detector_ran=detector_ran,
            )
        },
    )


def _published_rows(tmp_path: Path, samples: list[TimedObservation]) -> pa.Table:
    channel = box_channel()
    metadata = RecordingMetadata(
        recording_id="recording",
        selected_run_id=0,
        runs={
            0: RunDescriptor(
                sensor_groups={
                    GROUP: SensorGroup(
                        clock_description="capture clock", sample_count=len(samples)
                    )
                },
                sources={SOURCE: Source(kind="tracker", definition={})},
                reference_frames={REFERENCE: {"width": 1280, "height": 720}},
                models={},
                processing={},
                channels=(channel,),
            )
        },
    )
    structure = RecordingStructure(base_directory=tmp_path, recording_name="recording")
    with recording_write_lock(structure=structure):
        publish_recording(
            structure=structure,
            metadata=metadata,
            batches=box_batches(
                samples=samples, channel=channel, run_id=0, batch_size=4
            ),
        )
    return pa.Table.from_batches(
        list(
            read_batches(
                path=structure.data_parquet_path,
                run_id=0,
                sensor_groups=(GROUP,),
            )
        )
    )


def test_box_rows_round_trip_with_every_component(tmp_path: Path) -> None:
    rows = _published_rows(
        tmp_path,
        [
            TimedObservation(
                observation=observation(frame=0, with_box=True, detector_ran=True),
                capture_timestamp_s=0.001,
            ),
            TimedObservation(
                observation=observation(frame=1, with_box=True, detector_ran=False),
                capture_timestamp_s=0.035,
            ),
        ],
    ).to_pylist()

    assert {row["channel"] for row in rows} == {"BOXES_2D"}
    assert {row["sensor_group"] for row in rows} == {GROUP}
    assert {row["source"] for row in rows} == {SOURCE}
    # Six components per declared name per frame — the complete-coverage contract.
    assert len(rows) == 2 * len(BOX_COMPONENTS)

    first = {row["component"]: row["value"] for row in rows if row["frame_number"] == 0}
    assert (first["x1"], first["y1"], first["x2"], first["y2"]) == BOX
    assert first["confidence"] == pytest.approx(0.93)
    assert first["detector_ran"] == 1.0


def test_detector_provenance_distinguishes_fresh_from_carried_forward(
    tmp_path: Path,
) -> None:
    """The flag that makes a redetect-every-frame bug legible in the parquet."""
    rows = _published_rows(
        tmp_path,
        [
            TimedObservation(
                observation=observation(frame=0, with_box=True, detector_ran=True),
                capture_timestamp_s=0.001,
            ),
            TimedObservation(
                observation=observation(frame=1, with_box=True, detector_ran=False),
                capture_timestamp_s=0.035,
            ),
        ],
    ).to_pylist()
    ran = {
        row["frame_number"]: row["value"]
        for row in rows if row["component"] == "detector_ran"
    }
    assert ran == {0: 1.0, 1: 0.0}


def test_absent_box_is_a_null_row_not_a_missing_one(tmp_path: Path) -> None:
    rows = _published_rows(
        tmp_path,
        [
            TimedObservation(
                observation=observation(frame=0, with_box=True, detector_ran=True),
                capture_timestamp_s=0.001,
            ),
            TimedObservation(
                observation=observation(frame=1, with_box=False, detector_ran=False),
                capture_timestamp_s=0.035,
            ),
        ],
    ).to_pylist()
    absent = [row for row in rows if row["frame_number"] == 1]
    assert len(absent) == len(BOX_COMPONENTS)
    assert all(row["value"] is None for row in absent)


def test_undeclared_stage_is_rejected_rather_than_silently_dropped() -> None:
    channel = box_channel()
    stray = Observation(
        frame_number=0,
        image_size=(720, 1280),
        stages={
            "left_hand": StageObservation(
                name="left_hand",
                bounding_boxes=[BoundingBox(x1=0, y1=0, x2=10, y2=10)],
            )
        },
    )
    with pytest.raises(ValueError, match="undeclared bounding-box stage names"):
        list(
            box_batches(
                samples=[TimedObservation(observation=stray, capture_timestamp_s=0.001)],
                channel=channel,
                run_id=0,
                batch_size=4,
            )
        )
