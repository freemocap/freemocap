"""Numerical layout identity and prepared indexing independent of coordinate width."""

from dataclasses import replace

import numpy as np
import unittest
from beartype.roar import BeartypeCallHintParamViolation

from freemocap.core.data_tensors import AxisDefinition, SourceIdentity, TensorLayout


def example_layout() -> TensorLayout:
    return TensorLayout(
        axes=(
            AxisDefinition("sample_identity", (101, 105, 110)),
            AxisDefinition("entity_identity", ("right_wrist", "left_wrist", "nose")),
            AxisDefinition("component_identity", ("alpha", "beta", "gamma", "delta", "epsilon")),
        ),
        dtype=np.float64,
        component_units=("mm", "mm", "mm", "1", "rad"),
        reference_id="authored_reference",
        source_identity=SourceIdentity("tracker:configured", camera_id="camera-a"),
        channel_kind="declared_quantity",
    )


class TensorLayoutTests(unittest.TestCase):
    def test_dimensions_and_order_come_from_declared_axes(self):
        layout = example_layout()
        values = np.arange(np.prod(layout.shape), dtype=np.float64).reshape(layout.shape)
        layout.validate_array(values)
        assert layout.shape == (3, 3, 5)
        assert layout.axes[1].identifiers == ("right_wrist", "left_wrist", "nose")
        # An additional camera axis uses the same layout machinery.
        camera_layout = replace(layout, axes=(AxisDefinition("camera_identity", ("b", "a")), *layout.axes))
        camera_layout.validate_array(np.zeros(camera_layout.shape))
        assert camera_layout.shape == (2, 3, 3, 5)


    def test_static_and_empty_series_have_no_invented_dimensions(self):
        static_layout = TensorLayout((AxisDefinition("segment_identity", ("shin", "thigh")),), "float64")
        static_layout.validate_array(np.array([410.0, 430.0]))
        empty_layout = replace(static_layout, axes=(AxisDefinition("sample_identity", ()), *static_layout.axes))
        empty_layout.validate_array(np.empty((0, 2)))


    def test_invalid_axis_identifiers_are_rejected(self):
        for identifiers in [("same", "same"), ("",), (True,), (np.bool_(False),), ("one", 1)]:
            with self.assertRaises((ValueError, BeartypeCallHintParamViolation)):
                AxisDefinition("entity_identity", identifiers)


    def test_numpy_sample_identifiers_preserve_ids_instead_of_using_positions(self):
        axis = AxisDefinition("sample_identity", np.array([101, 105], dtype=np.int64))
        assert axis.identifiers == (101, 105)
        assert all(type(identifier) is int for identifier in axis.identifiers)
        with self.assertRaises(TypeError):
            AxisDefinition("entity_identity", "nose")


    def test_layout_rejects_duplicate_axes_and_incorrect_component_units(self):
        axis = AxisDefinition("component_identity", ("a", "b"))
        with self.assertRaisesRegex(ValueError, "unique"):
            TensorLayout((axis, axis), "float64")
        with self.assertRaisesRegex(ValueError, "Component units"):
            TensorLayout((axis,), "float64", component_units=("mm",))
        with self.assertRaisesRegex(ValueError, "Component units"):
            TensorLayout((AxisDefinition("entity_identity", ("a",)),), "float64", component_units=("mm",))


    def test_object_and_structured_payloads_are_rejected(self):
        for dtype in [object, "U10", np.dtype([("x", "f8")]), np.dtype(("f8", (3,)))]:
            with self.assertRaisesRegex(ValueError, "dtype"):
                TensorLayout((), dtype)


    def test_supplied_arrays_are_never_silently_cast_truncated_or_padded(self):
        layout = example_layout()
        for shape in ((3, 3, 4), (3, 3, 6), (3, 5, 3)):
            with self.assertRaisesRegex(ValueError, "shape"):
                layout.validate_array(np.zeros(shape))
        with self.assertRaisesRegex(ValueError, "dtype"):
            layout.validate_array(np.zeros(layout.shape, dtype=np.float32))
        with self.assertRaises((TypeError, BeartypeCallHintParamViolation)):
            layout.validate_array([])


    def test_contiguous_selection_is_a_view_and_preserves_authored_order(self):
        layout = example_layout()
        values = np.arange(np.prod(layout.shape), dtype=np.float64).reshape(layout.shape)
        plan = layout.prepare_selection("entity_identity", ("left_wrist", "nose"))
        selected = plan.select_values(values, source_layout=layout)
        assert plan.shares_memory
        assert np.shares_memory(selected, values)
        np.testing.assert_array_equal(selected, values[:, 1:3, :])
        assert plan.result_layout.axes[1].identifiers == ("left_wrist", "nose")
        plan.result_layout.validate_array(selected)


    def test_component_gather_reorders_values_and_units_together(self):
        layout = example_layout()
        values = np.arange(np.prod(layout.shape), dtype=np.float64).reshape(layout.shape)
        plan = layout.prepare_selection("component_identity", ("epsilon", "alpha", "delta"))
        selected = plan.select_values(values, source_layout=layout)
        assert not plan.shares_memory
        assert not np.shares_memory(selected, values)
        np.testing.assert_array_equal(selected, values[..., [4, 0, 3]])
        assert plan.result_layout.component_units == ("rad", "mm", "1")
        selected.fill(-1)
        assert np.all(values >= 0)


    def test_sample_selection_uses_sample_ids_and_can_be_empty(self):
        layout = example_layout()
        values = np.arange(np.prod(layout.shape), dtype=np.float64).reshape(layout.shape)
        selected = layout.prepare_selection("sample_identity", (110, 101)).select_values(values, source_layout=layout)
        np.testing.assert_array_equal(selected, values[[2, 0]])
        empty_plan = layout.prepare_selection("component_identity", ())
        assert empty_plan.select_values(values, source_layout=layout).shape == (3, 3, 0)
        assert empty_plan.result_layout.component_units == ()


    def test_selection_rejects_undeclared_or_duplicate_identifiers(self):
        layout = example_layout()
        with self.assertRaisesRegex(ValueError, "Undeclared tensor axis"):
            layout.prepare_selection("unknown_axis", ())
        with self.assertRaisesRegex(ValueError, "Undeclared identifier"):
            layout.prepare_selection("entity_identity", ("unknown_point",))
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            layout.prepare_selection("entity_identity", ("nose", "nose"))


    def test_selection_checks_semantic_layout_even_when_shape_matches(self):
        layout = example_layout()
        values = np.zeros(layout.shape)
        plan = layout.prepare_selection("entity_identity", ("nose",))
        mismatches = (
            replace(layout, reference_id="other_reference"),
            replace(layout, channel_kind="other_quantity"),
            replace(layout, component_units=("m",) * 5),
            replace(layout, source_identity=replace(layout.source_identity, camera_id="camera-b")),
            replace(layout, axes=(layout.axes[0], AxisDefinition("entity_identity", tuple(reversed(layout.axes[1].identifiers))), layout.axes[2])),
        )
        for other_layout in mismatches:
            with self.assertRaisesRegex(ValueError, "prepared layout"):
                plan.select_values(values, source_layout=other_layout)


    def test_instance_identity_defaults_to_zero_and_is_explicit(self):
        assert SourceIdentity("model:human").instance_id == 0
        assert SourceIdentity("model:human", instance_id=1).instance_id == 1
        for invalid in (-1, True, 1.0, None):
            with self.assertRaises((ValueError, BeartypeCallHintParamViolation)):
                SourceIdentity("model:human", instance_id=invalid)
