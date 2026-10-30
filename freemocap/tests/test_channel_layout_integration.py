"""The recording and live boundaries agree on declared ordering and dimensions."""

from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pyarrow as pa
import unittest
from beartype.roar import BeartypeCallHintParamViolation
from skellyforge.core.data_tensors.layout_definitions import SourceIdentity
from skellyforge.core.data_tensors.sample_timing import SampleTiming

from freemocap.core.recording.data_descriptors.recording_descriptor import Channel
from freemocap.core.recording.sample_encoding.channel_series import ChannelSeries, SeriesSampling
from freemocap.core.streaming.message_model import ChannelBlock
from freemocap.core.streaming.producers.joint_angles_producer import JointAnglesProducer
from freemocap.core.streaming.producers.producer_contexts import FrameContext
from freemocap.core.skeletons.tracked_skeleton_bundle import TrackedSkeletonBundle
from freemocap.core.types.channel_kind import ChannelKind


def channel_definition() -> Channel:
    return Channel(
        sensor_group="camera_group", source="tracker", reference_frame="camera_image",
        kind=ChannelKind.OVERLAY_2D, names=("z_point", "a_point"),
        components={"confidence": "1", "image_y": "px", "image_x": "px", "depth": "mm", "extra": "1"},
        stage="observations",
    )


class ChannelLayoutIntegrationTests(unittest.TestCase):
    def test_channel_publication_reuses_validated_timeline(self):
        timeline = SampleTiming(timeline_id="camera_group:synchronized", clock_id="recording_clock",
            source_identity=SourceIdentity(source_id="camera_group"), sample_ids=(17, 23), timestamps_s=(0.25, 0.8))
        sampling = SeriesSampling.from_timeline(sample_timing=timeline, run_id=0)
        channel = channel_definition()
        values = np.ones((timeline.sample_count, *channel.tensor_layout().shape), dtype=np.float64)
        cached_axis = timeline.sample_axis
        for _ in range(2):
            table = pa.Table.from_batches(list(ChannelSeries(channel=channel, values=values).batches(sampling)))
            self.assertEqual(table.column("frame_number")[0].as_py(), 17)
            self.assertEqual(table.column("timestamp_s")[-1].as_py(), 0.8)
            self.assertIs(sampling.sample_timing, timeline)
            self.assertIs(sampling.sample_timing.sample_axis, cached_axis)

    def test_camera_layout_requires_matching_source_and_rejects_cross_camera_selection(self):
        values = np.zeros((1, 1), dtype="<f4")
        message = ChannelBlock(kind=ChannelKind.OVERLAY_2D, names=("point",), columns=("x",),
                               data=values.tobytes(), camera_id="camera_a")
        with self.assertRaisesRegex(ValueError, "camera ID"):
            message.tensor_layout()
        first_source = SourceIdentity(source_id="tracker", camera_id="camera_a")
        second_source = SourceIdentity(source_id="tracker", camera_id="camera_b")
        with self.assertRaisesRegex(ValueError, "camera ID"):
            message.tensor_layout(source_identity=second_source)
        first_layout = message.tensor_layout(source_identity=first_source)
        second_message = ChannelBlock(kind=message.kind, names=message.names, columns=message.columns,
                                      data=message.data, camera_id="camera_b")
        second_layout = second_message.tensor_layout(source_identity=second_source)
        selection = first_layout.prepare_selection("entity_identity", ("point",))
        with self.assertRaisesRegex(ValueError, "source layout"):
            selection.select_values(values, source_layout=second_layout)

    def test_live_and_saved_layouts_preserve_authored_order_with_arbitrary_components(self):
        channel = channel_definition()
        saved_layout = channel.tensor_layout()
        values = np.arange(np.prod(saved_layout.shape), dtype=np.float64).reshape(saved_layout.shape)
        message = ChannelBlock(kind=channel.kind, names=channel.names, columns=tuple(channel.components),
                               data=values.astype("<f4").tobytes())
        live_layout = message.tensor_layout()
        assert live_layout.axes == saved_layout.axes
        assert saved_layout.source_identity.instance_id == 0
        assert saved_layout.component_units == ("1", "px", "px", "mm", "1")
        assert saved_layout.dtype == np.dtype("float64")
        assert live_layout.dtype == np.dtype("<f4")
        assert live_layout.channel_kind == saved_layout.channel_kind
        saved_plan = saved_layout.prepare_selection("entity_identity", ("a_point", "z_point"))
        live_plan = live_layout.prepare_selection("entity_identity", ("a_point", "z_point"))
        np.testing.assert_array_equal(
            saved_plan.select_values(values, source_layout=saved_layout),
            live_plan.select_values(values.astype("<f4"), source_layout=live_layout),
        )



    def test_recording_preserves_actual_sample_ids_times_and_declared_components(self):
        channel = channel_definition()
        channel_layout = channel.tensor_layout()
        values = np.arange(2 * np.prod(channel_layout.shape), dtype=np.float64).reshape((2, *channel_layout.shape))
        sampling = SeriesSampling(frame_numbers=(17, 23), timestamps_s=(0.25, 0.8), run_id=0)
        table = pa.Table.from_batches(list(ChannelSeries(channel=channel, values=values).batches(sampling)))
        rows = table.to_pylist()
        assert list(dict.fromkeys(row["frame_number"] for row in rows)) == [17, 23]
        assert list(dict.fromkeys(row["timestamp_s"] for row in rows)) == [0.25, 0.8]
        assert [row["component"] for row in rows[:len(channel.components)]] == list(channel.components)
        assert [row["value"] for row in rows] == values.ravel().tolist()



    def test_stream_rejects_missing_or_extra_payload_bytes(self):
        for delta in (-1, 1):
            message = ChannelBlock(kind=ChannelKind.KEYPOINTS_3D, names=("point",), columns=("x", "y"), data=b"\0" * (8 + delta))
            with self.assertRaisesRegex(ValueError, "payload"):
                message.tensor_layout()



    def test_stream_requires_explicit_inherited_identity_and_matching_order(self):
        message = ChannelBlock(kind=ChannelKind.LANDMARKS_3D, columns=("x",), data=np.zeros(2, dtype="<f4").tobytes())
        with self.assertRaisesRegex(ValueError, "entity IDs"):
            message.tensor_layout()
        assert message.tensor_layout(entity_ids=("z_point", "a_point")).shape == (2, 1)
        explicit = ChannelBlock(kind=message.kind, columns=message.columns, data=message.data, names=("z_point", "a_point"))
        with self.assertRaisesRegex(ValueError, "order"):
            explicit.tensor_layout(entity_ids=("a_point", "z_point"))



    def test_stream_row_constructor_rejects_component_mismatches(self):
        for row in ([1.0], [1.0, 2.0, 3.0]):
            with self.assertRaisesRegex(ValueError, "width"):
                ChannelBlock.from_float32_rows(kind=ChannelKind.OVERLAY_2D, columns=("x", "y"), rows=[row])



    def test_recording_rejects_implicit_dtype_conversion_and_duplicate_sample_ids(self):
        channel = channel_definition()
        shape = (2, *channel.tensor_layout().shape)
        sampling = SeriesSampling(frame_numbers=(1, 2), timestamps_s=(0.1, 0.2), run_id=0)
        with self.assertRaises((ValueError, BeartypeCallHintParamViolation)):
            list(ChannelSeries(channel=channel, values=np.zeros(shape, dtype=np.float32)).batches(sampling))
        with self.assertRaisesRegex(ValueError, "strictly increase"):
            list(ChannelSeries(channel=channel, values=np.zeros(shape)).batches(
                SeriesSampling(frame_numbers=(1, 1), timestamps_s=(0.1, 0.2), run_id=0)))



    def test_live_joint_order_matches_authored_order_including_missing_joints(self):
        joints = {"z_joint": SimpleNamespace(angle_names=("z.flexion", "z.twist")),
                  "a_joint": SimpleNamespace(angle_names=("a.flexion",))}
        bundle = Mock(spec=TrackedSkeletonBundle, model_id="model", skeleton=SimpleNamespace(joints=joints))
        reconstruction = SimpleNamespace(joint_angles={"a_joint": (3.0,), "z_joint": (1.0, 2.0)})
        context = FrameContext(frame_number=0, timestamp=0., aggregator_output=SimpleNamespace(reconstructions={"model": reconstruction}))
        producer = JointAnglesProducer()
        message, = producer.fill(context, bundle)
        assert message.names == tuple(name for joint in joints.values() for name in joint.angle_names)
        np.testing.assert_array_equal(np.frombuffer(message.data, dtype="<f4"), [1., 2., 3.])
        reconstruction.joint_angles = {"a_joint": (3.0,)}
        message, = producer.fill(context, bundle)
        np.testing.assert_array_equal(np.frombuffer(message.data, dtype="<f4"), [np.nan, np.nan, 3.])
        reconstruction.joint_angles = {"unknown": (3.0,)}
        with self.assertRaisesRegex(ValueError, "Undeclared"):
            producer.fill(context, bundle)
