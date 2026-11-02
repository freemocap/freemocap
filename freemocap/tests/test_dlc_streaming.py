"""Generic keypoints publish without reconstruction, with declared connections."""
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock

import cbor2
import numpy as np
import pytest
from skellytracker.core.tracker.tracker_presets import DlcTrackerMetadata, dlc_tracker_config
from skellytracker.core.data_primitives import Keypoints
from skellytracker.core.data_primitives.observation import Observation, StageObservation

from freemocap.api.websocket.websocket_server import WebsocketServer
from freemocap.core.pipeline.posthoc.annotation_style import build_observation_annotator
from freemocap.core.pipeline.realtime.realtime_pipeline_config import RealtimePipelineConfig
from freemocap.core.streaming.message_model import encode_message
from freemocap.core.streaming.message_composer import compose_messages
from freemocap.core.streaming.producers.producer_contexts import StreamContext, FrameContext
from freemocap.pubsub.pubsub_topics import AggregationNodeOutputMessage, CameraNodeOutputMessage


def metadata():
    return DlcTrackerMetadata(model_name="fixture.yaml", model_sha256="a" * 64,
        input_size=(8, 12), resize_method="fit", stage_path=("dlc_keypoints",),
        keypoint_names=("feature_z", "feature_a"), connections=(("feature_z", "feature_a"),),
        connection_groups=(("feature_edges", (("feature_z", "feature_a"),)),))


@pytest.mark.parametrize("camera_count", [1, 3])
def test_generic_tracker_wire_is_dense_and_self_contained(camera_count):
    descriptor = metadata()
    cameras = tuple(f"camera-{i}" for i in range(camera_count))
    values = np.array([[4., 6., 0.], [np.nan, np.nan, np.nan]])
    observation = Observation(7, (720, 1280), {
        "dlc_keypoints": StageObservation("dlc_keypoints",
            keypoints=Keypoints(descriptor.keypoint_names, values, np.array([.8, 0.]))),
    })
    outputs = {c: CameraNodeOutputMessage(camera_id=c, frame_number=7,
        skeleton_observation=observation) for c in cameras}
    aggregation = AggregationNodeOutputMessage(frame_number=7, pipeline_config=RealtimePipelineConfig(),
        camera_group_id="test", camera_node_outputs=outputs)
    context = StreamContext(skeletons=(), camera_ids=cameras, detector_type="dlc",
        pipeline_live=True, independent_trackers=(descriptor,),
        live_image_sizes={c: (1280, 720) for c in cameras})
    composition = compose_messages(context)
    frame = composition.compose_frame_message(FrameContext(7, .25, aggregator_output=aggregation))
    wire = cbor2.loads(encode_message(frame))
    assert wire["models"] == wire["instances"] == []
    tracker, = wire["trackers"]
    assert tracker["model_id"] is None and tracker["detector_type"] == "dlc"
    assert tracker["connection_groups"] == [{"name": "feature_edges",
        "pairs": [["feature_z", "feature_a"]], "color": "#00AA00"}]
    assert len(tracker["channels"]) == camera_count
    for channel in tracker["channels"]:
        assert channel["names"] == list(descriptor.keypoint_names)
        assert channel["image_size"] == [1280, 720]
        np.testing.assert_allclose(np.frombuffer(channel["data"], dtype="<f4").reshape(-1, 3),
            [[4, 6, .8], [np.nan] * 3], equal_nan=True)
    again = composition.compose_frame_message(FrameContext(8, .3, aggregator_output=aggregation))
    assert again.trackers[0].connection_groups is frame.trackers[0].connection_groups


def test_websocket_uses_owned_metadata_without_model_io(monkeypatch):
    server = WebsocketServer.__new__(WebsocketServer)
    first = metadata()
    pipeline = SimpleNamespace(alive=True, tracker_metadata=first)
    server._app = SimpleNamespace(realtime_pipeline_manager=SimpleNamespace(pipelines={"one": pipeline}))
    import skellytracker.core.tracker.tracker_presets as presets
    reader = Mock(side_effect=AssertionError("frame path read model files"))
    monkeypatch.setattr(presets, "dlc_tracker_metadata", reader)
    assert server._independent_trackers() == (first,)
    old_signature = server._context_signature(StreamContext(skeletons=(), independent_trackers=(first,)))
    second = replace(first, model_sha256="b" * 64)
    pipeline.tracker_metadata = second
    assert server._independent_trackers() == (second,)
    assert old_signature != server._context_signature(StreamContext(skeletons=(), independent_trackers=(second,)))
    reader.assert_not_called()


def test_posthoc_annotation_uses_declared_connections(monkeypatch):
    from skellytracker.core.config.tracker_config import TrackerConfig
    from skellytracker.core.config.detection_stage_config import DetectionStageConfig
    from skellytracker.core.detectors.keypoint_detectors.dlc import DlcDetectorConfig
    import skellytracker.core.tracker.tracker_presets as presets
    monkeypatch.setattr(presets, "dlc_tracker_metadata", lambda **kwargs: metadata())
    config = TrackerConfig(preset_name="dlc", stages=[DetectionStageConfig(name="dlc_keypoints",
        keypoint_detectors=[DlcDetectorConfig(model_name="fixture.yaml")])])
    annotator = build_observation_annotator(config)
    assert set(annotator.config.stage_schemas) == {"dlc_keypoints"}
    assert annotator.config.stage_schemas["dlc_keypoints"].connections == metadata().connections
    observation = Observation(0, (40, 40), {"dlc_keypoints": StageObservation("dlc_keypoints",
        keypoints=Keypoints(metadata().keypoint_names, np.array([[5., 5., 0.], [30., 30., 0.]]), np.ones(2)))})
    rendered = annotator.annotate(np.zeros((40, 40, 3), dtype=np.uint8), observation)
    assert rendered[17, 17].any()  # Declared edge, away from either endpoint.
