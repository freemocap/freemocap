"""Generic arrays preserve semantic axes, companion metadata and actual timing."""

from dataclasses import replace
import unittest

import numpy as np

from freemocap.core.data_tensors import (
    AxisDefinition, CompanionTensor, DataTensor, SampleTimeline,
    ScientificProvenance, SourceIdentity, TensorLayout, TimeSeries,
)


class DataTensorTests(unittest.TestCase):
    def setUp(self):
        self.source = SourceIdentity("model_prediction", model_id="test_model")
        self.axes = (
            AxisDefinition("sample_identity", (10, 13)),
            AxisDefinition("entity_identity", ("z_entity", "a_entity")),
            AxisDefinition("component_identity", ("alpha", "beta", "gamma", "delta", "epsilon")),
        )
        self.layout = TensorLayout(self.axes, "float64", source_identity=self.source)
        self.values = np.arange(np.prod(self.layout.shape), dtype=np.float64).reshape(self.layout.shape)
        self.provenance = ScientificProvenance("model_prediction", "test_predictor", ("input_series",), "test_model")

    def companion(self, name, values, axes=None):
        layout = TensorLayout(self.axes if axes is None else axes, values.dtype, source_identity=self.source)
        return CompanionTensor(name, values, layout)

    def data_tensor(self, *companions, values=None, layout=None):
        return DataTensor(self.values if values is None else values,
                          self.layout if layout is None else layout,
                          self.provenance, companions)

    def timeline(self, identifiers=(10, 13), timestamps=(0.2, 0.7)):
        return SampleTimeline(timeline_id="sample_times", clock_id="recording_clock",
                              source_identity=SourceIdentity("synchronized_cameras"),
                              sample_ids=identifiers, timestamps_s=timestamps)

    def test_borrows_arrays_without_coordinate_width_or_empirical_assumption(self):
        tensor = self.data_tensor()
        self.assertIs(tensor.data_values, self.values)
        self.assertIs(tensor.tensor_layout, self.layout)
        self.assertEqual(tensor.scientific_provenance.meaning, "model_prediction")
        self.assertEqual(tensor.tensor_layout.source_identity.instance_id, 0)
        self.values[0, 0, 0] = 99.
        self.assertEqual(tensor.data_values[0, 0, 0], 99.)

    def test_point_confidence_broadcasts_without_repeated_storage(self):
        confidence = np.array([[0.1, 0.2], [0.3, np.nan]])
        companion = self.companion("confidence_scores", confidence, self.axes[:-1])
        tensor = self.data_tensor(companion)
        aligned = companion.aligned_values(self.layout)
        self.assertTrue(np.shares_memory(confidence, aligned))
        self.assertEqual(aligned.shape, self.values.shape)
        np.testing.assert_array_equal(aligned[..., 0], confidence)
        self.assertIs(tensor.companion_values("confidence_scores"), confidence)

    def test_companion_axis_identity_matters_even_when_shape_matches(self):
        reordered = (self.axes[0], AxisDefinition("entity_identity", ("a_entity", "z_entity")))
        companion = self.companion("confidence_scores", np.ones(self.layout.shape[:-1]), reordered)
        with self.assertRaisesRegex(ValueError, "identifiers or ordering"):
            self.data_tensor(companion)
        foreign_axis = AxisDefinition("camera_identity", ("z_entity", "a_entity"))
        companion = self.companion("confidence_scores", np.ones(self.layout.shape[:-1]), (self.axes[0], foreign_axis))
        with self.assertRaisesRegex(ValueError, "not declared"):
            self.data_tensor(companion)

    def test_companion_axes_follow_parent_order(self):
        companion = self.companion("confidence_scores", np.ones(self.layout.shape[:-1]), (self.axes[1], self.axes[0]))
        with self.assertRaisesRegex(ValueError, "parent axis ordering"):
            self.data_tensor(companion)

    def test_presence_and_validity_are_distinct_from_confidence(self):
        values = self.values.copy()
        presence = np.ones(values.shape, dtype=bool)
        validity = np.ones(values.shape, dtype=bool)
        values[0, 0, 0] = np.nan
        values[0, 0, 1] = np.nan
        presence[0, 0, 0] = False
        validity[0, 0, :2] = False
        tensor = self.data_tensor(self.companion("entry_presence", presence),
                                  self.companion("value_validity", validity), values=values)
        self.assertFalse(tensor.companion_values("entry_presence")[0, 0, 0])
        self.assertTrue(tensor.companion_values("entry_presence")[0, 0, 1])
        np.testing.assert_array_equal(tensor.data_values, values)
        with self.assertRaises(KeyError):
            tensor.companion_values("confidence_scores")

    def test_validity_cannot_claim_absent_or_nonfinite_values(self):
        present = np.ones(self.values.shape, dtype=bool)
        valid = np.ones(self.values.shape, dtype=bool)
        present[0, 0, 0] = False
        with self.assertRaisesRegex(ValueError, "entry presence"):
            self.data_tensor(self.companion("entry_presence", present), self.companion("value_validity", valid))
        values = self.values.copy()
        values[0, 0, 0] = np.nan
        with self.assertRaisesRegex(ValueError, "finite"):
            self.data_tensor(self.companion("value_validity", valid), values=values)
        tensor = self.data_tensor(values=values)
        self.assertTrue(np.isnan(tensor.data_values[0, 0, 0]))

    def test_companion_types_full_masks_and_unique_names_are_enforced(self):
        for name in ("entry_presence", "value_validity", "measured_support"):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "boolean"):
                self.companion(name, np.ones(self.values.shape))
        for name, dtype in (("solver_status", float), ("confidence_scores", int)):
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.companion(name, np.ones(self.values.shape, dtype=dtype))
        with self.assertRaisesRegex(ValueError, "all parent axes"):
            self.data_tensor(self.companion("entry_presence", np.ones(self.layout.shape[:-1], dtype=bool), self.axes[:-1]))
        confidence = self.companion("confidence_scores", np.ones(self.layout.shape[:-1]), self.axes[:-1])
        with self.assertRaisesRegex(ValueError, "unique"):
            self.data_tensor(confidence, confidence)

    def test_unknown_companion_preserves_declared_integer_codes(self):
        codes = np.array([4, 8], dtype=np.uint16)
        companion = self.companion("derivation_codes", codes, (self.axes[0],))
        tensor = self.data_tensor(companion)
        self.assertIs(tensor.companion_values("derivation_codes"), codes)
        self.assertEqual(tensor.companion_values("derivation_codes").dtype, np.uint16)

    def test_source_identity_mismatch_is_not_hidden_by_equal_shape(self):
        companion = self.companion("confidence_scores", np.ones(self.layout.shape[:-1]), self.axes[:-1])
        foreign = replace(companion, tensor_layout=replace(companion.tensor_layout, source_identity=SourceIdentity("other")))
        with self.assertRaisesRegex(ValueError, "source identity"):
            self.data_tensor(foreign)

    def test_static_scalars_and_complex_signals_use_same_container(self):
        static_layout = TensorLayout((), "float64")
        static = self.data_tensor(values=np.array(2.), layout=static_layout)
        self.assertEqual(static.data_values.shape, ())
        complex_layout = TensorLayout((self.axes[0],), "complex128")
        complex_values = np.array([1 + 2j, 3 + 4j])
        tensor = self.data_tensor(values=complex_values, layout=complex_layout)
        self.assertIs(tensor.data_values, complex_values)

    def test_time_series_binds_actual_samples_without_assuming_same_source(self):
        timeline = self.timeline()
        tensor = self.data_tensor()
        series = TimeSeries(tensor, timeline)
        self.assertIs(series.data_tensor, tensor)
        self.assertIs(series.sample_timeline, timeline)
        self.assertEqual(series.sample_count, len(timeline.sample_ids))
        with self.assertRaisesRegex(ValueError, "identifiers"):
            TimeSeries(tensor, self.timeline((0, 1)))

    def test_time_axis_can_be_nonleading_and_have_an_explicit_name(self):
        sample_axis = AxisDefinition("exposure_samples", (10, 13))
        axes = (self.axes[1], sample_axis, self.axes[2])
        layout = replace(self.layout, axes=axes)
        tensor = self.data_tensor(layout=layout)
        series = TimeSeries(tensor, self.timeline(), sample_axis_name="exposure_samples")
        self.assertEqual(series.sample_count, 2)
        with self.assertRaisesRegex(ValueError, "Undeclared"):
            TimeSeries(tensor, self.timeline())

    def test_empty_series_and_no_companion_fields_are_valid(self):
        timeline = self.timeline((), ())
        axes = (timeline.sample_axis, *self.axes[1:])
        layout = replace(self.layout, axes=axes)
        tensor = self.data_tensor(values=np.empty(layout.shape), layout=layout)
        series = TimeSeries(tensor, timeline)
        self.assertEqual(series.sample_count, 0)
        self.assertEqual(series.data_tensor.companion_tensors, ())

    def test_scientific_meaning_and_producing_operation_are_required(self):
        for meaning, operation in (("", "operation"), ("prediction", "")):
            with self.assertRaises(ValueError):
                ScientificProvenance(meaning, operation)


if __name__ == "__main__":
    unittest.main()
