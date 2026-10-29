"""Recording collections preserve numerical ownership, identities and timelines."""

from dataclasses import FrozenInstanceError, replace
import unittest
from unittest.mock import patch

import numpy as np

from freemocap.core.data_tensors import (
    AxisDefinition, ChannelIdentity, DataTensor, DefinitionDocument, RecordingDataset,
    SampleTimeline, ScientificProvenance, SourceIdentity, TensorLayout, TimeSeries,
)


class RecordingDatasetTests(unittest.TestCase):
    def series(self, *, source="camera_a", channel="OVERLAY_2D", sample_ids=(10, 12),
               timestamps=(0., .2), timeline_id=None, clock_id="camera_clock", instance_id=0,
               timeline=None):
        identity = SourceIdentity(source_id=source, camera_id=source, instance_id=instance_id)
        if timeline is None:
            timeline = SampleTimeline(timeline_id=timeline_id or f"{source}:capture", clock_id=clock_id,
                source_identity=identity, sample_ids=sample_ids, timestamps_s=timestamps)
        layout = TensorLayout(axes=(timeline.sample_axis, AxisDefinition("entity_identity", ("point",)),
                                   AxisDefinition("component_identity", ("x", "y"))),
                              dtype="float64", component_units=("px", "px"), reference_id="image",
                              source_identity=identity, channel_kind=channel)
        tensor = DataTensor(np.arange(np.prod(layout.shape), dtype=np.float64).reshape(layout.shape), layout,
                            ScientificProvenance("detector_estimates", "tracking")).immutable_copy()
        return TimeSeries(tensor, timeline)

    def static(self, *, source="model:human", channel="SEGMENT_LENGTHS", instance_id=0):
        layout = TensorLayout(axes=(AxisDefinition("entity_identity", ("arm", "leg")),
                                   AxisDefinition("component_identity", ("length",))),
                              dtype="float64", component_units=("mm",), reference_id="world",
                              source_identity=SourceIdentity(source_id=source, instance_id=instance_id),
                              channel_kind=channel)
        return DataTensor(np.array([[300.], [500.]]), layout,
                          ScientificProvenance("fitted_lengths", "scale_fit")).immutable_copy()

    def test_dataset_and_selection_retain_exact_payload_and_metadata_objects(self):
        series = self.series()
        static = self.static()
        document = DefinitionDocument("model:human", '{"segments":["arm","leg"]}')
        with patch.object(DataTensor, "__post_init__", side_effect=AssertionError("Payload revalidated")):
            dataset = RecordingDataset("recording", 0, (series,), (static,), (document,))
            selected = dataset.select_channels((ChannelIdentity.from_data(static),))
        self.assertIs(dataset.time_series[0], series)
        self.assertIs(dataset.sample_timelines[0], series.sample_timeline)
        self.assertIs(selected.static_tensors[0], static)
        self.assertIs(selected.static_tensors[0].data_values, static.data_values)
        self.assertIs(selected.definition_documents[0], document)
        self.assertIs(dataset.channel_data(ChannelIdentity.from_data(series)), series)

    def test_independent_camera_timelines_coexist_without_padding_or_resampling(self):
        camera = self.series()
        sensor = self.series(source="imu", channel="ANGULAR_VELOCITY", sample_ids=(0, 1, 3),
                             timestamps=(0., .005, .015), clock_id="imu_clock")
        dataset = RecordingDataset("recording", 0, (camera, sensor))
        self.assertEqual([item.sample_count for item in dataset.time_series], [2, 3])
        self.assertEqual([item.clock_id for item in dataset.sample_timelines], ["camera_clock", "imu_clock"])
        np.testing.assert_array_equal(sensor.sample_timeline.timestamps_s, [0., .005, .015])

    def test_shared_timeline_identity_reuses_same_reference(self):
        first = self.series()
        second = self.series(channel="BOXES_2D", timeline=first.sample_timeline)
        with patch("numpy.array_equal", side_effect=AssertionError("Shared timeline rescanned")):
            dataset = RecordingDataset("recording", 0, (first, second))
        self.assertEqual(len(dataset.sample_timelines), 1)
        self.assertIs(first.sample_timeline, second.sample_timeline)
        self.assertIs(dataset.sample_timelines[0], first.sample_timeline)

    def test_two_cameras_keep_independent_timelines_for_the_same_channel_kind(self):
        first = self.series()
        second = self.series(source="camera_b", timestamps=(.1, .4), clock_id="camera_b_clock")
        dataset = RecordingDataset("recording", 0, (first, second))
        self.assertEqual(len(dataset.channel_identities), 2)
        self.assertIs(dataset.time_series[1].sample_timeline, second.sample_timeline)
        self.assertEqual(dataset.time_series[1].sample_timeline.timestamps_s[0], .1)

    def test_same_timeline_id_cannot_represent_a_different_clock_epoch(self):
        first = self.series()
        later_epoch = replace(first.sample_timeline, clock_epoch=1)
        second = self.series(channel="BOXES_2D", timeline=later_epoch)
        with self.assertRaisesRegex(ValueError, "Conflicting sample timeline"):
            RecordingDataset("recording", 0, (first, second))

    def test_equal_timeline_identity_accepts_exact_content_but_rejects_conflicts(self):
        first = self.series()
        equal = self.series(channel="BOXES_2D")
        self.assertEqual(len(RecordingDataset("recording", 0, (first, equal)).sample_timelines), 1)
        for changes in ({"timestamps": (0., .3)}, {"clock_id": "other_clock"},
                        {"sample_ids": (10, 13)}, {"instance_id": 1}):
            with self.subTest(changes=changes):
                conflict = self.series(channel="BOXES_2D", **changes)
                with self.assertRaisesRegex(ValueError, "Conflicting sample timeline"):
                    RecordingDataset("recording", 0, (first, conflict))

    def test_distinct_timeline_ids_are_not_merged_by_equal_numbers(self):
        first = self.series()
        second = self.series(channel="BOXES_2D", timeline_id="different_capture")
        dataset = RecordingDataset("recording", 0, (first, second))
        self.assertEqual(len(dataset.sample_timelines), 2)

    def test_instance_identity_distinguishes_same_model_channels(self):
        first = self.static(instance_id=0)
        second = self.static(instance_id=1)
        dataset = RecordingDataset("recording", 0, static_tensors=(first, second))
        self.assertEqual([identity.source_identity.instance_id for identity in dataset.channel_identities], [0, 1])

    def test_duplicate_scientific_channels_and_selection_duplicates_fail(self):
        series = self.series()
        with self.assertRaisesRegex(ValueError, "Duplicate scientific"):
            RecordingDataset("recording", 0, (series, series))
        dataset = RecordingDataset("recording", 0, (series,))
        identity = ChannelIdentity.from_data(series)
        with self.assertRaisesRegex(ValueError, "Duplicate scientific"):
            dataset.select_channels((identity, identity))
        static_layout = replace(series.data_tensor.tensor_layout, axes=series.data_tensor.tensor_layout.axes[1:])
        static = DataTensor(series.data_tensor.data_values[0], static_layout,
                            series.data_tensor.scientific_provenance).immutable_copy()
        with self.assertRaisesRegex(ValueError, "static/dynamic"):
            RecordingDataset("recording", 0, (series,), (static,))

    def test_borrowed_payloads_and_static_sample_axes_fail(self):
        series = self.series()
        with self.assertRaisesRegex(ValueError, "immutable_copy"):
            RecordingDataset("recording", 0, (series.mutable_copy(),))
        with self.assertRaisesRegex(ValueError, "immutable_copy"):
            RecordingDataset("recording", 0, static_tensors=(self.static().mutable_copy(),))
        with self.assertRaisesRegex(ValueError, "sample axis"):
            RecordingDataset("recording", 0, static_tensors=(series.data_tensor,))

    def test_source_and_channel_identity_are_required(self):
        static = self.static()
        for field in ("source_identity", "channel_kind"):
            layout = replace(static.tensor_layout, **{field: None})
            missing = DataTensor(static.data_values, layout, static.scientific_provenance).immutable_copy()
            with self.assertRaisesRegex(ValueError, "source identity and channel kind"):
                RecordingDataset("recording", 0, static_tensors=(missing,))

    def test_dataset_metadata_cannot_be_mutated_and_unknown_keys_fail(self):
        static = self.static()
        dataset = RecordingDataset("recording", 0, static_tensors=(static,))
        with self.assertRaises(FrozenInstanceError):
            dataset.run_id = 1
        with self.assertRaises(TypeError):
            dataset._channel_index[ChannelIdentity.from_data(static)] = self.static(instance_id=1)
        with self.assertRaises(KeyError):
            dataset.channel_data(ChannelIdentity.from_data(self.static(instance_id=1)))
        empty = dataset.select_channels(())
        self.assertEqual(empty.channel_identities, ())

    def test_invalid_run_identity_and_definitions_fail(self):
        for run_id in (-1, True):
            with self.assertRaises(ValueError):
                RecordingDataset("recording", run_id)
        with self.assertRaises(ValueError):
            RecordingDataset("", 0)
        for content in ('{"bad":', '{"value":NaN}', '{"value":Infinity}'):
            with self.assertRaises(ValueError):
                DefinitionDocument("definition", content)
        document = DefinitionDocument("definition", '{}')
        with self.assertRaises(FrozenInstanceError):
            document.content_json = '{"changed":true}'
        with self.assertRaisesRegex(ValueError, "definition identities"):
            RecordingDataset("recording", 0, definition_documents=(document, document))
