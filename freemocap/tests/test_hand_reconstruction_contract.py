"""Tracker hand mappings and Forge frames must produce complete connected hands."""
from types import SimpleNamespace

import numpy as np
import pytest
from numpy.testing import assert_allclose

from freemocap.core.reconstruction.posthoc_reconstruction import reconstruct_skeletons_for_recording
from freemocap.core.reconstruction.posthoc_timing import PosthocTimingReport
from freemocap.core.reconstruction.recording_reconstruction import RecordingReconstructionInput
from freemocap.core.recording.data_descriptors.recording_model import RecordedModel
from freemocap.core.recording.sample_encoding.reconstruction_samples import ReconstructionRecording, ReconstructionSourceDefinition
from freemocap.core.recording.sample_encoding.spatial_points import SpatialReference
from freemocap.core.skeletons.reconstruct_skeleton import reconstruct_skeleton
from freemocap.core.skeletons.standard_human_skeleton import build_standard_human_bundle
from freemocap.core.streaming.producers.segment_producer import SegmentProducer
from freemocap.core.streaming.producers.producer_contexts import FrameContext
from freemocap.core.types.channel_kind import ChannelKind
from freemocap.tests.test_model_scale_in_the_loop import _standing_keypoints
from freemocap.tests.test_trajectory_products import state_for


def tracked_hands(bundle):
    points = _standing_keypoints()
    # Feed only detector-emittable direct hand observations. The missing CMCs
    # must come from the real mapping, not from this fixture.
    for snapshot in bundle.landmark_mapping.mapping_snapshots():
        for name, source in snapshot.entries.items():
            if isinstance(source, str) and '_hand_' in source:
                side = name.split('_')[0]
                wrist = bundle.rest_pose.landmark_positions[f'{side}_carpal_origin'].array
                points[source] = points[f'{side}_wrist'] + 1700 * (bundle.rest_pose.landmark_positions[name].array - wrist)
    return points


def assert_hand_connected(bundle, result, side):
    hands = {name for name, segment in bundle.skeleton.segments.items()
             if segment.anatomical_segment == 'hand' and name.startswith(side + '_')}
    assert len(hands) == 20
    assert hands <= result.segment_origins.keys()
    for joint in bundle.skeleton.joints.values():
        if joint.child.name in hands:
            assert_allclose(result.segment_origins[joint.child.name], result.landmarks[joint.connect_at.name], atol=1e-9)


@pytest.mark.parametrize('tracker', ['rtmpose', 'mediapipe'])
def test_complete_hands_in_live_posthoc_and_recorded_model(tracker):
    bundle = build_standard_human_bundle(detector_type=tracker)
    points = tracked_hands(bundle)
    live = reconstruct_skeleton(bundle=bundle, state=state_for(bundle), filtered_keypoints=points, compute_center_of_mass=False)
    names = tuple(points)
    # Exercise saved model definitions as playback/reprocessing do, including
    # anatomical offsets and the carpal observation frames.
    saved_bundle = RecordedModel.from_bundle(bundle).to_bundle()
    request = RecordingReconstructionInput(bundles=(saved_bundle,), keypoint_names=names,
        keypoints_3d=np.array([[points[n] for n in names]] * 3), compute_center_of_mass=False,
        timing=PosthocTimingReport())
    batch = reconstruct_skeletons_for_recording(request=request)[bundle.model_id]
    for result in (live, *batch.frames):
        for side in ('left', 'right'):
            assert_hand_connected(bundle, result, side)
    # The live rolling estimate and recording-wide scale fit use different evidence
    # windows. With the same fit, their shared geometry must agree exactly.
    same_fit = reconstruct_skeleton(bundle=bundle, state=state_for(bundle, batch.scale_fit),
        filtered_keypoints=points, compute_center_of_mass=False)
    for name in same_fit.segment_origins:
        assert_allclose(same_fit.segment_origins[name], batch.frames[0].segment_origins[name], atol=1e-8)
    context = FrameContext(frame_number=0, timestamp=0., aggregator_output=SimpleNamespace(reconstructions={bundle.model_id: live}))
    blocks = {block.kind: block for block in SegmentProducer().fill(context, bundle)}
    origins = np.frombuffer(blocks[ChannelKind.SEGMENT_ORIGINS].data, dtype='<f4').reshape(-1, 3)
    recording = ReconstructionRecording(sensor_group='mocap', reference=SpatialReference.for_camera_count(2),
        definition=ReconstructionSourceDefinition.from_bundle(bundle=bundle, tracker_source=tracker,
            point_kind=ChannelKind.RAW_KEYPOINTS_3D), result=batch)
    series = {item.channel.kind: item for item in recording.series()}
    for index, name in enumerate(bundle.skeleton.segments):
        if bundle.skeleton.segments[name].anatomical_segment == 'hand':
            assert_allclose(origins[index], live.segment_origins[name], atol=1e-4)
            assert_allclose(series[ChannelKind.SEGMENT_ORIGINS].values[0, index], batch.frames[0].segment_origins[name])


@pytest.mark.parametrize('tracker', ['rtmpose', 'mediapipe'])
def test_missing_palm_evidence_removes_that_hand_and_reentry_restores_it(tracker):
    bundle = build_standard_human_bundle(detector_type=tracker)
    points = tracked_hands(bundle)
    state = state_for(bundle)
    missing = 'left_hand_forefinger1' if tracker == 'rtmpose' else 'left_hand_index_finger_mcp'
    for present in (True, False, True):
        frame = points if present else {n: p for n, p in points.items() if n != missing}
        result = reconstruct_skeleton(bundle=bundle, state=state, filtered_keypoints=frame, compute_center_of_mass=False)
        assert_hand_connected(bundle, result, 'right')
        if present:
            assert_hand_connected(bundle, result, 'left')
        else:
            assert 'left_lower_arm' in result.segment_origins
            assert not any(n.startswith('left_') and s.anatomical_segment == 'hand'
                           for n, s in bundle.skeleton.segments.items() if n in result.segment_origins)
