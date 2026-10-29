"""Tensor adapters consume production test-data outputs without rerunning inference.

Set FREEMOCAP_PROVENANCE_PREPARED_ROOT to the isolated output of the existing
datasets process test_data command. Numerical-profile results are sufficient for
these tensor checks; this is not complete-run Blender/export acceptance.
"""

import json
from dataclasses import replace
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from freemocap.core.data_tensors.data_tensor import ScientificProvenance
from freemocap.core.data_tensors.layout_definitions import SourceIdentity
from freemocap.core.data_tensors.sample_timeline import SampleTimeline
from freemocap.core.data_tensors.recording_dataset import DefinitionDocument, RecordingDataset
from freemocap.core.recording.exports.arrays import available_channels, ordered_arrays
from freemocap.core.recording.parquet_storage.recording_view import recording_view
from freemocap.tests.reference_paths import prepared_root
from freemocap.tools.datasets.catalog import TEST_DATA
from freemocap.tools.datasets.preparation import file_digest, validate_parquet


@unittest.skipUnless(os.environ.get("FREEMOCAP_PROVENANCE_PREPARED_ROOT"), "Set the prepared reference-data root")
class TensorConsumerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = prepared_root() / TEST_DATA.name
        ready = json.loads((root / "ready.json").read_text(encoding="utf-8"))
        cls.recording = Path(ready["recording"])
        if not cls.recording.resolve().is_relative_to((root / "current").resolve()):
            raise ValueError("Reference recording escapes the selected prepared root")
        from freemocap.system.recording_structure.recording_structure import RecordingStructure
        cls.structure = RecordingStructure(base_directory=cls.recording.parent, recording_name=cls.recording.name)
        cls.validation = validate_parquet(cls.recording, expected_frames=222)
        cls.original_digest = file_digest(cls.structure.data_parquet_path)

    @classmethod
    def tearDownClass(cls):
        if file_digest(cls.structure.data_parquet_path) != cls.original_digest:
            raise AssertionError("Tensor consumer changed the reference Parquet")

    def test_saved_channels_bind_values_presence_identities_and_times_without_copying(self):
        checked = set()
        required = {"OVERLAY_2D", "LANDMARKS_3D", "ROTATIONS_WORLD", "JOINT_ANGLES", "SEGMENT_LENGTHS"}
        with tempfile.TemporaryDirectory() as temporary, recording_view(self.structure.data_parquet_path) as view:
            run_id = view.metadata.selected_run_id
            for item in available_channels(view.metadata.runs[run_id]):
                context = item[0]
                if context.channel not in required or context.channel in checked:
                    continue
                provenance = ScientificProvenance(meaning=f"saved:{context.channel}", operation_id="parquet_read",
                                                   input_refs=(view.revision,))
                with ordered_arrays(view, run_id, item, scratch=Path(temporary)) as arrays:
                    tensor = arrays.to_data_tensor(scientific_provenance=provenance)
                    self.assertTrue(np.shares_memory(tensor.data_values, arrays.values))
                    self.assertTrue(np.shares_memory(tensor.companion_tensors[0].data_values, arrays.present))
                    self.assertEqual(tensor.tensor_layout.component_units, arrays.units)
                    self.assertEqual(tensor.tensor_layout.axes[-2].identifiers, arrays.names)
                    self.assertEqual(tensor.tensor_layout.axes[-1].identifiers, arrays.source_components or arrays.components)
                    self.assertEqual(tensor.tensor_layout.source_identity.instance_id, 0)
                    with self.assertRaises(ValueError):
                        replace(arrays, source_components=()).to_data_tensor(scientific_provenance=provenance)
                    if context.static:
                        self.assertEqual(len(tensor.tensor_layout.axes), 2)
                    else:
                        timeline = SampleTimeline(timeline_id=f"{context.source}:{context.channel}",
                            clock_id=f"{context.sensor_group}:recording_relative",
                            source_identity=SourceIdentity(source_id=context.source, sensor_group=context.sensor_group),
                            sample_ids=arrays.frames, timestamps_s=arrays.timestamps)
                        series = arrays.to_time_series(sample_timeline=timeline, scientific_provenance=provenance)
                        self.assertIs(series.sample_timeline, timeline)
                        self.assertEqual(timeline.sample_count, 222)
                        np.testing.assert_array_equal(series.data_tensor.data_values, arrays.values)
                        shifted = SampleTimeline(timeline_id=timeline.timeline_id, clock_id=timeline.clock_id,
                            source_identity=timeline.source_identity, sample_ids=arrays.frames,
                            timestamps_s=arrays.timestamps + 0.01)
                        with self.assertRaisesRegex(ValueError, "timestamps"):
                            arrays.to_time_series(sample_timeline=shifted, scientific_provenance=provenance)
                    checked.add(context.channel)
        self.assertEqual(checked, required)

    def test_owned_series_survives_closed_parquet_memmaps(self):
        with tempfile.TemporaryDirectory() as temporary, recording_view(self.structure.data_parquet_path) as view:
            run_id = view.metadata.selected_run_id
            item = next(item for item in available_channels(view.metadata.runs[run_id])
                        if item[0].channel == "LANDMARKS_3D")
            with patch("freemocap.core.recording.exports.arrays.MAX_RESIDENT_ARRAY_BYTES", 0):
                with ordered_arrays(view, run_id, item, scratch=Path(temporary)) as arrays:
                    self.assertIsInstance(arrays.values, np.memmap)
                    timeline = SampleTimeline(timeline_id="landmark_samples", clock_id="recording_clock",
                        source_identity=SourceIdentity(source_id=arrays.context.source),
                        sample_ids=arrays.frames, timestamps_s=arrays.timestamps)
                    borrowed = arrays.to_time_series(sample_timeline=timeline,
                        scientific_provenance=ScientificProvenance(meaning="model_landmarks", operation_id="parquet_read"))
                    published = borrowed.immutable_copy()
                    expected_frame = arrays.values[7:8].copy()
        selected = published.frame_view(7)
        np.testing.assert_array_equal(selected.data_tensor.data_values, expected_frame)
        self.assertTrue(np.shares_memory(selected.data_tensor.data_values, published.data_tensor.data_values))
        self.assertEqual(selected.sample_timeline.sample_ids.tolist(), [7])
        with self.assertRaises(ValueError):
            selected.data_tensor.data_values.flags.writeable = True

    def test_dataset_retains_recorded_channels_static_fits_and_model_definitions(self):
        series_items = []
        static_items = []
        timelines = {}
        required = {"OVERLAY_2D", "LANDMARKS_3D", "ROTATIONS_WORLD", "JOINT_ANGLES", "SEGMENT_LENGTHS"}
        with tempfile.TemporaryDirectory() as temporary, recording_view(self.structure.data_parquet_path) as view:
            run_id = view.metadata.selected_run_id
            descriptor = view.metadata.runs[run_id]
            definitions = tuple(DefinitionDocument(f"model:{model_id}", model.model_dump_json())
                                for model_id, model in descriptor.models.items()) + tuple(
                DefinitionDocument(f"reference:{reference_id}", json.dumps(definition, allow_nan=False))
                for reference_id, definition in descriptor.reference_frames.items())
            for item in available_channels(descriptor):
                context = item[0]
                if context.channel not in required:
                    continue
                provenance = ScientificProvenance(meaning=f"saved:{context.channel}", operation_id="parquet_read",
                                                   input_refs=(view.revision,))
                with ordered_arrays(view, run_id, item, scratch=Path(temporary)) as arrays:
                    if context.static:
                        static_items.append(arrays.to_data_tensor(scientific_provenance=provenance).immutable_copy())
                        continue
                    # Different camera/source streams retain separate timing identities.
                    timing_key = (context.sensor_group, context.source, context.reference_frame)
                    if timing_key not in timelines:
                        timelines[timing_key] = SampleTimeline(timeline_id=json.dumps(timing_key),
                            clock_id=f"{context.sensor_group}:recording_relative",
                            source_identity=SourceIdentity(source_id=context.source, sensor_group=context.sensor_group),
                            sample_ids=arrays.frames, timestamps_s=arrays.timestamps)
                    series_items.append(arrays.to_time_series(sample_timeline=timelines[timing_key],
                        scientific_provenance=provenance).immutable_copy())
            dataset = RecordingDataset(recording_id=self.recording.name, run_id=run_id,
                time_series=tuple(series_items), static_tensors=tuple(static_items), definition_documents=definitions)
        # Assembly and selection retain already-owned payloads after every reader closes.
        self.assertTrue(static_items)
        self.assertGreater(len(series_items), len(required))
        self.assertEqual({key.channel_kind for key in dataset.channel_identities}, required)
        for actual, original in zip(dataset.time_series, series_items, strict=True):
            self.assertIs(actual, original)
            self.assertEqual(actual.sample_count, 222)
            self.assertIs(actual.sample_timeline, timelines[(actual.data_tensor.tensor_layout.source_identity.sensor_group,
                                                           actual.data_tensor.tensor_layout.source_identity.source_id,
                                                           actual.data_tensor.tensor_layout.reference_id)])
        for actual, original in zip(dataset.static_tensors, static_items, strict=True):
            self.assertIs(actual, original)
            self.assertNotIn("sample_identity", [axis.axis_name for axis in actual.tensor_layout.axes])
        for document, original in zip(dataset.definition_documents, definitions, strict=True):
            self.assertIs(document, original)
            if document.definition_id.startswith("model:"):
                self.assertEqual(json.loads(document.content_json)["model_id"], document.definition_id.removeprefix("model:"))
        selected_ids = dataset.channel_identities[::2]
        selected = dataset.select_channels(selected_ids)
        for identity in selected_ids:
            self.assertIs(selected.channel_data(identity), dataset.channel_data(identity))
