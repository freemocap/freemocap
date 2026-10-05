"""Diagnostics separate overlapping work and retain failure-path measurements."""

from concurrent.futures import CancelledError, ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from freemocap.core.pipeline.performance_report import PerformanceReport
from freemocap.core.pipeline.posthoc.mocap_pipeline import MocapWorkerRequest, run_mocap_pipeline


def test_bounded_aggregation_keeps_first_call_separate():
    report = PerformanceReport()
    report.record("batch", 1.0)
    with ThreadPoolExecutor(max_workers=3) as executor:
        list(executor.map(lambda _: report.record("batch", 0.01), range(300)))
    row = report.snapshot()["batch"]
    assert row["count"] == 301
    assert row["total_s"] == pytest.approx(4.0)
    assert row["first_ms"] == 1000
    assert row["mean_after_first_ms"] == pytest.approx(10)
    assert row["max_ms"] == 1000


def test_failed_work_is_timed():
    report = PerformanceReport()
    with patch("freemocap.core.pipeline.performance_report.perf_counter", side_effect=[2.0, 2.25]):
        with pytest.raises(ValueError), report.measure("write"):
            raise ValueError("failed")
    assert report.snapshot()["write"]["total_s"] == 0.25


@pytest.mark.parametrize("error, outcome", [(None, "complete"), (CancelledError(), "cancelled"), (ValueError("bad"), "failed")])
def test_pipeline_always_logs_outcome(error, outcome, caplog):
    request = Mock(spec=MocapWorkerRequest, performance=PerformanceReport(), pipeline_id="test", ipc=SimpleNamespace(should_continue=True))
    with caplog.at_level("INFO"), patch("freemocap.core.pipeline.posthoc.mocap_pipeline._run_mocap_pipeline", side_effect=error):
        if isinstance(error, ValueError):
            with pytest.raises(ValueError):
                run_mocap_pipeline(request=request)
        else:
            run_mocap_pipeline(request=request)
    assert f"outcome={outcome}" in caplog.text
    assert "overlap; do not sum" in caplog.text


def test_report_distinguishes_synchronized_and_camera_throughput(caplog):
    report = PerformanceReport()
    report.frames, report.images = 20, 60
    report.record("detection.total", 2.0)
    with caplog.at_level("INFO"):
        report.log(pipeline_id="test", outcome="complete")
    assert "10.00 synchronized frames/s; 30.00 camera images/s" in caplog.text
