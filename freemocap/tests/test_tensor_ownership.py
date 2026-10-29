"""Published tensors support safe views without reboxing or rescanning samples."""

from dataclasses import replace
import gc
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from freemocap.core.data_tensors import (
    AxisDefinition, CompanionTensor, DataTensor, SampleTimeline, ScientificProvenance,
    SourceIdentity, TensorLayout, TimeSeries,
)


class TensorOwnershipTests(unittest.TestCase):
    def make_series(self, sample_position=0, sample_name="sample_identity"):
        sample = AxisDefinition(sample_name, (10, 12, 18))
        entity = AxisDefinition("entity_identity", ("second", "first"))
        component = AxisDefinition("component_identity", ("vertical", "horizontal", "depth", "auxiliary"))
        axes = [entity, component]
        axes.insert(sample_position, sample)
        layout = TensorLayout(tuple(axes), "float64", ("px", "px", "mm", "1"),
                              reference_id="image_reference", source_identity=SourceIdentity("tracker"),
                              channel_kind="test_output")
        values = np.arange(np.prod(layout.shape), dtype=np.float64).reshape(layout.shape)
        presence = CompanionTensor("entry_presence", np.ones(layout.shape, dtype=bool), replace(layout, dtype=bool))
        confidence_axes = tuple(axis for axis in axes if axis.axis_name != "component_identity")
        confidence_layout = TensorLayout(confidence_axes, "float32")
        confidence = CompanionTensor("confidence_scores", np.full(confidence_layout.shape, .75, dtype=np.float32), confidence_layout)
        static_layout = TensorLayout((entity,), "uint8")
        static_status = CompanionTensor("solver_status", np.array([1, 2], dtype=np.uint8), static_layout)
        tensor = DataTensor(values, layout, ScientificProvenance("detector estimates", "test_tracker"),
                            (presence, confidence, static_status))
        timeline = SampleTimeline(timeline_id="camera_samples", clock_id="camera_clock",
            source_identity=SourceIdentity("camera"), sample_ids=(10, 12, 18), timestamps_s=(.1, .2, .5))
        return TimeSeries(tensor, timeline, sample_name)

    def test_published_copy_has_no_writable_input_aliases(self):
        borrowed = self.make_series()
        published = borrowed.immutable_copy()
        self.assertEqual(borrowed.data_tensor.storage_mode, "borrowed")
        self.assertEqual(published.data_tensor.storage_mode, "immutable")
        self.assertIs(published.immutable_copy(), published)
        self.assertIs(published.sample_timeline, borrowed.sample_timeline)
        borrowed.data_tensor.data_values.fill(-1)
        borrowed.data_tensor.companion_values("entry_presence").fill(False)
        self.assertTrue(np.all(published.data_tensor.data_values >= 0))
        self.assertTrue(published.data_tensor.companion_values("entry_presence").all())
        arrays = (published.data_tensor.data_values,
                  *(item.data_values for item in published.data_tensor.companion_tensors))
        for values in arrays:
            self.assertFalse(values.flags.writeable)
            with self.assertRaises(ValueError):
                values.flags.writeable = True

    def test_mutable_copy_is_independent_for_values_and_companions(self):
        source = self.make_series().immutable_copy()
        changed = source.mutable_copy()
        self.assertEqual(changed.data_tensor.storage_mode, "mutable")
        changed.data_tensor.data_values.fill(-1)
        changed.data_tensor.companion_values("confidence_scores").fill(.1)
        self.assertTrue(np.all(source.data_tensor.data_values >= 0))
        np.testing.assert_array_equal(source.data_tensor.companion_values("confidence_scores"), .75)
        with self.assertRaisesRegex(ValueError, "immutable_copy"):
            changed.frame_view(0)

    def test_borrowed_readonly_flags_do_not_claim_ownership(self):
        source = self.make_series()
        source.data_tensor.data_values.flags.writeable = False
        self.assertFalse(source.is_immutable)
        with self.assertRaisesRegex(ValueError, "immutable_copy"):
            source.slice_samples(0, 1)
        with self.assertRaises(TypeError):
            DataTensor(source.data_tensor.data_values, source.data_tensor.tensor_layout,
                       source.data_tensor.scientific_provenance, storage_mode="immutable")

    def test_admission_revalidates_mutated_borrowed_metadata(self):
        source = self.make_series().data_tensor
        validity = CompanionTensor("value_validity", np.ones(source.data_values.shape, dtype=bool),
                                   replace(source.tensor_layout, dtype=bool))
        borrowed = DataTensor(source.data_values, source.tensor_layout, source.scientific_provenance,
                              (*source.companion_tensors, validity))
        borrowed.companion_values("entry_presence")[0, 0, 0] = False
        with self.assertRaisesRegex(ValueError, "entry presence"):
            borrowed.immutable_copy()

    def test_frame_views_share_storage_and_keep_real_sample_identity(self):
        for sample_position in (0, 1, 2):
            with self.subTest(sample_position=sample_position):
                source = self.make_series(sample_position).immutable_copy()
                source.sample_timeline.sample_axis
                with patch.object(DataTensor, "__post_init__", side_effect=AssertionError("rescanned tensor")), \
                     patch.object(CompanionTensor, "__post_init__", side_effect=AssertionError("rescanned companion")), \
                     patch.object(TimeSeries, "__post_init__", side_effect=AssertionError("rescanned series")):
                    frame = source.frame_view(1)
                self.assertEqual(frame.sample_count, 1)
                np.testing.assert_array_equal(frame.sample_timeline.sample_ids, [12])
                np.testing.assert_array_equal(frame.sample_timeline.timestamps_s, [.2])
                self.assertTrue(np.shares_memory(frame.data_tensor.data_values, source.data_tensor.data_values))
                self.assertTrue(np.shares_memory(frame.data_tensor.companion_values("entry_presence"),
                                                 source.data_tensor.companion_values("entry_presence")))
                self.assertTrue(np.shares_memory(frame.data_tensor.companion_values("confidence_scores"),
                                                 source.data_tensor.companion_values("confidence_scores")))
                self.assertIs(frame.data_tensor.companion_tensors[-1], source.data_tensor.companion_tensors[-1])
                self.assertIs(frame.data_tensor.scientific_provenance, source.data_tensor.scientific_provenance)

    def test_custom_sample_axis_and_negative_or_empty_slices(self):
        source = self.make_series(sample_position=1, sample_name="capture_sample").immutable_copy()
        last = source.frame_view(-1)
        self.assertEqual(last.sample_axis_name, "capture_sample")
        self.assertEqual(last.sample_timeline.sample_axis.identifiers, (18,))
        empty = source.slice_samples(2, 1)
        self.assertEqual(empty.sample_count, 0)
        self.assertEqual(empty.data_tensor.data_values.shape[1], 0)
        for index in (-4, 3):
            with self.assertRaises(IndexError):
                source.frame_view(index)

    def test_views_keep_immutable_backing_alive_after_parent_release(self):
        source = self.make_series().immutable_copy()
        frame = source.frame_view(1)
        expected = frame.data_tensor.data_values.copy()
        del source
        gc.collect()
        np.testing.assert_array_equal(frame.data_tensor.data_values, expected)
        with self.assertRaises(ValueError):
            frame.data_tensor.data_values.flags.writeable = True

    def test_published_copy_survives_reader_memory_map_close(self):
        source = self.make_series().data_tensor
        with tempfile.TemporaryDirectory() as temporary:
            mapped = np.lib.format.open_memmap(Path(temporary) / "values.npy", mode="w+",
                dtype=source.data_values.dtype, shape=source.data_values.shape)
            mapped[:] = source.data_values
            borrowed = DataTensor(mapped, source.tensor_layout, source.scientific_provenance,
                                  source.companion_tensors)
            published = borrowed.immutable_copy()
            mapped._mmap.close()
        np.testing.assert_array_equal(published.data_values, source.data_values)
        self.assertFalse(np.shares_memory(published.data_values, source.data_values))

    def test_prepared_component_gather_reorders_values_masks_and_units(self):
        source = self.make_series().immutable_copy().data_tensor
        plan = source.tensor_layout.prepare_selection("component_identity", ("auxiliary", "vertical"))
        selected = source.select_axis(plan)
        self.assertFalse(np.shares_memory(selected.data_values, source.data_values))
        np.testing.assert_array_equal(selected.data_values, source.data_values[..., [3, 0]])
        np.testing.assert_array_equal(selected.companion_values("entry_presence"), source.companion_values("entry_presence")[..., [3, 0]])
        self.assertEqual(selected.tensor_layout.component_units, ("1", "px"))
        self.assertIs(selected.companion_tensors[1], source.companion_tensors[1])
        with self.assertRaises(ValueError):
            selected.data_values.flags.writeable = True

    def test_contiguous_prepared_selection_shares_payloads(self):
        source = self.make_series().immutable_copy().data_tensor
        selected = source.select_axis(source.tensor_layout.prepare_selection("entity_identity", ("first",)))
        self.assertTrue(np.shares_memory(selected.data_values, source.data_values))
        self.assertTrue(np.shares_memory(selected.companion_values("solver_status"), source.companion_values("solver_status")))
        wrong = replace(source.tensor_layout, source_identity=SourceIdentity("different_tracker"))
        with self.assertRaisesRegex(ValueError, "source layout"):
            source.select_axis(wrong.prepare_selection("entity_identity", ("first",)))

    def test_component_slice_keeps_units_and_does_not_change_source(self):
        source = self.make_series().immutable_copy().data_tensor
        selected = source.slice_axis("component_identity", 1, 3)
        self.assertEqual(selected.tensor_layout.component_units, ("px", "mm"))
        self.assertEqual(selected.tensor_layout.axes[-1].identifiers, ("horizontal", "depth"))
        self.assertTrue(np.shares_memory(selected.data_values, source.data_values))
