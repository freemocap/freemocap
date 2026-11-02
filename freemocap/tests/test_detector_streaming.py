"""Every selectable human detector must reach the actual WebSocket message encoder."""
from typing import get_args

import cbor2
import numpy as np
import pytest

from freemocap.core.streaming.message_composer import compose_messages
from freemocap.core.streaming.message_model import encode_message
from freemocap.core.streaming.producers.producer_contexts import FrameContext, StreamContext
from freemocap.core.skeletons.standard_human_skeleton import build_standard_human_bundle
from freemocap.core.pipeline.realtime.camera_node_config import CameraNodeConfig
from freemocap.core.pipeline.realtime.realtime_pipeline_config import RealtimePipelineConfig
from freemocap.pubsub.pubsub_topics import AggregationNodeOutputMessage, CameraNodeOutputMessage
from skellytracker.core.data_primitives.bounding_box import BoundingBox
from skellytracker.core.data_primitives.keypoints import Keypoints
from skellytracker.core.data_primitives.observation import Observation, StageObservation


HUMAN_DETECTORS = tuple(value for value in get_args(CameraNodeConfig.model_fields['detector_type'].annotation)
                        if value != 'dlc')  # Generic DLC has no anatomical bundle; test_dlc_streaming covers it.


@pytest.mark.parametrize('detector_type', HUMAN_DETECTORS)
@pytest.mark.parametrize('camera_count', [1, 3, 4])
def test_every_selectable_detector_serializes_points_and_person_boxes(detector_type, camera_count):
    bundle = build_standard_human_bundle(detector_type=detector_type)
    names = tuple(bundle.tracker_keypoint_names)
    cameras = tuple(f'camera-{index}' for index in range(camera_count))
    values = np.arange(len(names) * 3, dtype=np.float64).reshape(len(names), 3)
    visibility = np.full(len(names), 0.75)
    values[0] = np.nan
    visibility[0] = 0
    outputs = {
        camera: CameraNodeOutputMessage(camera_id=camera, frame_number=7,
            skeleton_observation=Observation(frame_number=7, image_size=(720, 1280), stages={
                'body': StageObservation(name='body',
                    keypoints=Keypoints(names=names, xyz=values.copy(), visibility=visibility.copy()),
                    bounding_boxes=[BoundingBox(10, 20, 300, 400, 0.9)], detector_ran=True,
                    children={'right_hand': StageObservation(name='right_hand', keypoints=None,
                        bounding_boxes=[BoundingBox(30, 40, 80, 90, 1)], detector_ran=True)}),
            }))
        for camera in cameras
    }
    config = RealtimePipelineConfig()
    config.camera_node_config.detector_type = detector_type
    aggregation = AggregationNodeOutputMessage(frame_number=7, pipeline_config=config,
        camera_group_id='test-group', camera_node_outputs=outputs)
    composition = compose_messages(StreamContext(skeletons=(bundle,), camera_ids=cameras,
        detector_type=detector_type, pipeline_live=True,
        live_image_sizes={camera: (1280, 720) for camera in cameras}))
    frame = composition.compose_frame_message(FrameContext(frame_number=7, timestamp=0.25,
        aggregator_output=aggregation))
    decoded = cbor2.loads(encode_message(frame))
    tracker, = decoded['trackers']
    assert tracker['detector_type'] == detector_type
    overlays = [channel for channel in tracker['channels'] if channel['kind'] == 'OVERLAY_2D']
    assert [channel['camera_id'] for channel in overlays] == list(cameras)
    expected = np.column_stack((values[:, :2], visibility)).astype('<f4')
    expected[0] = np.nan  # Missing entries serialize as fully unavailable rows.
    for channel in overlays:
        assert tuple(channel['names']) == names
        np.testing.assert_array_equal(np.frombuffer(channel['data'], dtype='<f4').reshape(-1, 3), expected)
    boxes = [channel for channel in tracker['channels'] if channel['kind'] == 'BOXES_2D']
    assert [channel['camera_id'] for channel in boxes] == list(cameras)
    expected_names = ['body'] if detector_type == 'rtmpose' else ['body/right_hand', 'body/left_hand']
    expected_boxes = [[10, 20, 300, 400, 0.9, 1]] if detector_type == 'rtmpose' else [[30, 40, 80, 90, 1, 1], [np.nan] * 6]
    if detector_type == 'rtmw_mediapipe_hands':
        expected_names.insert(0, 'body')
        expected_boxes.insert(0, [10, 20, 300, 400, 0.9, 1])
    for channel in boxes:
        assert channel['names'] == expected_names
        np.testing.assert_array_equal(np.frombuffer(channel['data'], dtype='<f4').reshape(-1, 6),
                                      np.asarray(expected_boxes, dtype='<f4'))
