import threading
from types import SimpleNamespace

from freemocap.core.pipeline.realtime.realtime_pipeline_config import RealtimePipelineConfig
from freemocap.core.streaming.outputs.source import RuntimeOutputSource
from freemocap.pubsub.pubsub_topics import AggregationNodeOutputMessage, CameraNodeOutputMessage


class Pipeline:
    alive = True
    camera_ids = ("a", "b")
    camera_configs = {}

    def __init__(self, number=4, camera_times=(1_000_000_001, 1_000_000_005)):
        self.output = AggregationNodeOutputMessage(frame_number=number, pipeline_id="p",
            pipeline_config=RealtimePipelineConfig(),
            camera_node_outputs={name: CameraNodeOutputMessage(camera_id=name, frame_number=number,
                capture_timestamp_ns=value, capture_timestamp_s=99.0)
                for name, value in zip(self.camera_ids, camera_times)})

    def get_latest_aggregator_output(self, if_newer_than):
        return self.output if self.output.frame_number > if_newer_than else None


def source_for(monkeypatch, pipeline):
    built = []
    def build(**kwargs):
        built.append(kwargs)
        return ()
    monkeypatch.setattr("freemocap.core.streaming.outputs.source.build_tracked_skeletons", build)
    manager = SimpleNamespace(pipelines={"p": pipeline}, lock=threading.RLock())
    return RuntimeOutputSource(SimpleNamespace(realtime_pipeline_manager=manager)), built


def test_no_browser_or_image_fetch_and_capture_provenance_uses_original_camera_ns(monkeypatch):
    pipeline = Pipeline()
    source, built = source_for(monkeypatch, pipeline)
    batch = source.poll()
    assert batch.errors == {}
    sample, = batch.samples
    assert sample.camera_timestamps_ns == (("a", 1_000_000_001), ("b", 1_000_000_005))
    assert sample.source_timestamp_ns == 1_000_000_003
    assert sample.frame.envelope.timestamp == 1_000_000_003
    assert sample.frame.image is None
    # The existing filter-seconds field deliberately differs: no round trip through it.
    assert pipeline.output.camera_node_outputs["a"].capture_timestamp_s == 99.0
    assert source.poll().samples == ()
    pipeline.output.frame_number += 1
    for node in pipeline.output.camera_node_outputs.values():
        node.frame_number += 1
    assert len(source.poll().samples) == 1
    assert len(built) == 1
    # Other consumers keep independent cursors into the retained result.
    assert pipeline.get_latest_aggregator_output(-1) is pipeline.output


def test_missing_capture_time_fails_that_source_without_substitution(monkeypatch):
    pipeline = Pipeline(camera_times=(None, 1_000_000_005))
    source, _ = source_for(monkeypatch, pipeline)
    batch = source.poll()
    assert batch.samples == ()
    assert "acquisition nanoseconds" in batch.errors["p"]


def test_pipeline_replacement_resets_source_cursor(monkeypatch):
    source, _ = source_for(monkeypatch, Pipeline(number=999))
    assert source.poll().samples[0].frame.frame_number == 999
    source.app.realtime_pipeline_manager.pipelines["p"] = Pipeline(number=0)
    assert source.poll().samples[0].frame.frame_number == 0


def test_integral_multicamera_mean_retains_ns_beyond_float_integer_precision(monkeypatch):
    base = 9_007_199_254_740_993
    source, _ = source_for(monkeypatch, Pipeline(camera_times=(base, base + 4)))
    sample, = source.poll().samples
    assert isinstance(sample.source_timestamp_ns, int)
    assert sample.source_timestamp_ns == base + 2
    assert sample.camera_timestamps_ns == (("a", base), ("b", base + 4))
