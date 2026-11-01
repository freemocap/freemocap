"""Realtime timing reports must not infer accounting from unpaired samples."""
import logging
from multiprocessing import Queue
from threading import Event

import numpy as np
import pytest

from freemocap.core.pipeline.pipeline_stage_timer import PipelineStageTimer
from freemocap.core.pipeline.pipeline_timing_reporter import (
    PipelineTimingReporter,
    SECTION_LAYOUTS,
    _build_table,
)


@pytest.fixture
def publication_queue():
    queue = Queue()
    yield queue
    queue.close()
    queue.join_thread()


@pytest.mark.parametrize("frame_count", [600, 3000])
def test_skipped_detection_does_not_produce_percentage_of_unrelated_frames(caplog, publication_queue, frame_count):
    reporter = PipelineTimingReporter(name="test", timing_sub=publication_queue, stop_event=Event())
    for camera_id in ("camera-a", "camera-b"):
        timer = PipelineStageTimer(name=camera_id, flush_interval=0.0)
        # The real camera loop records detection only on attempted frames,
        # but records its wrapper even when the missing-board gate skips work.
        for frame in range(frame_count):
            if frame % 5 == 0:
                timer.record("charuco_detection", 9.16)
                timer.record("total_camera_node", 9.17)
            else:
                timer.record("total_camera_node", 0.0013)
        timer.maybe_flush(publication_queue=publication_queue, node_kind="camera", camera_id=camera_id)
        reporter._ingest(publication_queue.get(timeout=2))
    with caplog.at_level(logging.INFO):
        reporter._print_report()
    assert "charuco_detection" in caplog.text
    assert "9.16" in caplog.text
    assert "%" not in caplog.text
    assert "unpaired" in caplog.text
    assert "overlap" in caplog.text
    assert "WRAPPER: total_camera_node" in caplog.text
    assert len(reporter._camera_samples[("camera-a", "total_camera_node")]) == 500
    assert len(reporter._camera_samples[("camera-a", "charuco_detection")]) == min(frame_count // 5, 500)


def test_report_distinguishes_counts_and_amortized_batch_cost():
    table = _build_table(stage_to_samples={
        "predict_batch": np.array([40., 60.]),
        "predict_per_camera": np.array([10., 15.]),
        "dropped_frames": np.array([2., 3.]),
    }, layout=SECTION_LAYOUTS["skeleton_inference"])
    assert "Unit" in table
    assert "count" in table
    assert "amortized" in table
    assert "%" not in table
    drop_row = next(line for line in table.splitlines() if line.startswith("dropped_frames"))
    assert drop_row.split()[:5] == ["dropped_frames", "2", "count", "2.50", "2.50"]


def test_unknown_and_empty_stages_remain_visible_without_synthetic_total():
    table = _build_table(stage_to_samples={
        "new_stage": np.array([1., 3.]),
        "charuco_detection": np.array([]),
    }, layout=SECTION_LAYOUTS["camera"])
    assert "new_stage" in table
    assert "charuco_detection" in table
    assert "nan" not in table
    assert "%" not in table
    assert "WRAPPER" not in table


def test_parallel_camera_samples_are_pooled_not_added(publication_queue, caplog):
    reporter = PipelineTimingReporter(name="parallel", timing_sub=publication_queue, stop_event=Event())
    for camera_id, elapsed in (("camera-a", 10.), ("camera-b", 20.)):
        timer = PipelineStageTimer(name=camera_id, flush_interval=0.0)
        timer.record("charuco_detection", elapsed)
        timer.maybe_flush(publication_queue=publication_queue, node_kind="camera", camera_id=camera_id)
        reporter._ingest(publication_queue.get(timeout=2))
    with caplog.at_level(logging.INFO):
        reporter._print_report()
    row = next(line for line in caplog.messages[-1].splitlines() if line.startswith("charuco_detection"))
    assert row.split()[:9] == ["charuco_detection", "2", "ms", "15.00", "15.00", "5.00", "12.50", "17.50", "10.00"]
