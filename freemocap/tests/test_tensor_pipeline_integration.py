"""Tensor contracts against installed Tracker objects and real Forge results.

Reference checks use the numerical profile produced by the existing dataset CLI.
They do not require a GUI, Blender, pytest, or regenerated tracker inference.
"""

import json
import os
from pathlib import Path
import tempfile
import unittest

import numpy as np
from skellytracker.core.data_primitives.keypoints import Keypoints
from skellyforge.core.skeleton.pose.hydration_batch import LandmarkPoseGeometry

from skellyforge.core.data_tensors import (
    AxisDefinition, CompanionTensor, DataTensor, SampleTiming, ScientificProvenance,
    SourceIdentity, TensorLayout, TimeSeries,
)
from freemocap.core.recording.exports.arrays import available_channels, ordered_arrays
from freemocap.core.recording.parquet_storage.recording_view import recording_view
from freemocap.core.recording.sample_encoding.reconstruction_samples import model_source_name
from freemocap.system.recording_structure.recording_structure import RecordingStructure
from freemocap.tests.reference_paths import prepared_root
from freemocap.tools.datasets.catalog import TEST_DATA
from freemocap.tools.datasets.preparation import file_digest, validate_parquet


def reference_structure() -> RecordingStructure:
    root = prepared_root() / TEST_DATA.name
    ready = json.loads((root / "ready.json").read_text(encoding="utf-8"))
    recording = Path(ready["recording"])
    if not recording.resolve().is_relative_to((root / "current").resolve()):
        raise ValueError("Reference recording escapes the selected prepared root")
    validate_parquet(recording, expected_frames=222)
    return RecordingStructure(base_directory=recording.parent, recording_name=recording.name)


def tracker_tensor(keypoints: Keypoints, source_identity: SourceIdentity) -> DataTensor:
    """Test adapter for Keypoints' explicitly declared xyz/visibility contract.

    This preserves the installed Tracker representation, including its existing z
    field. It does not claim every detector supplies an empirical depth value.
    """
    entities = AxisDefinition("entity_identity", keypoints.names)
    components = AxisDefinition("component_identity", ("x", "y", "z"))
    layout = TensorLayout(axes=(entities, components), dtype=keypoints.xyz.dtype,
                          source_identity=source_identity, channel_kind="TRACKER_COORDINATES")
    confidence = CompanionTensor("confidence_scores", keypoints.visibility,
                                 TensorLayout(axes=(entities,), dtype=keypoints.visibility.dtype))
    return DataTensor(keypoints.xyz, layout,
                      ScientificProvenance("tracker_output", "keypoints_admission"), (confidence,))


class TrackerTensorTests(unittest.TestCase):
    def test_installed_keypoints_preserves_authored_names_and_separate_confidence(self):
        points = Keypoints(names=("right_point", "left_point"),
                           xyz=np.array([[7.0, 8.0, 0.0], [np.nan, np.nan, np.nan]]),
                           visibility=np.array([0.8, 0.0]))
        identity = SourceIdentity(source_id="tracker_source", camera_id="camera_A", model_id="tracker_model")
        tensor = tracker_tensor(points, identity)
        self.assertIs(tensor.data_values, points.xyz)
        self.assertIs(tensor.companion_values("confidence_scores"), points.visibility)
        self.assertEqual(tensor.tensor_layout.axes[0].identifiers, points.names)
        self.assertEqual(tensor.tensor_layout.source_identity.instance_id, 0)
        self.assertEqual(tensor.tensor_layout.source_identity.camera_id, "camera_A")
        published = tensor.immutable_copy()
        points.xyz[0] = -1.0
        np.testing.assert_array_equal(published.data_values[0], [7.0, 8.0, 0.0])
        self.assertNotIn("entry_presence", [item.metadata_name for item in tensor.companion_tensors])


@unittest.skipUnless(os.environ.get("FREEMOCAP_PROVENANCE_PREPARED_ROOT"), "Set the prepared reference-data root")
class ForgeTensorTests(unittest.TestCase):
    def test_reference_landmarks_recover_dense_poses_with_declared_status(self):
        structure = reference_structure()
        original = file_digest(structure.data_parquet_path)
        try:
            with tempfile.TemporaryDirectory() as temporary, recording_view(structure.data_parquet_path) as view:
                run_id = view.metadata.selected_run_id
                descriptor = view.metadata.runs[run_id]
                checked_models = set()
                for model_id, model in descriptor.models.items():
                    source = model_source_name(model_id)
                    channels = available_channels(descriptor)
                    item = next(entry for entry in channels
                                if entry[0].source == source and entry[0].channel == "LANDMARKS_3D")
                    geometry = LandmarkPoseGeometry.from_skeleton(skeleton=model.skeleton.restore(),
                                                                  landmark_names=item[1].names)
                    with ordered_arrays(view, run_id, item, scratch=Path(temporary)) as arrays:
                        # Bounded real frame batch; every numerical operation stays array based.
                        usable = arrays.present.all(axis=-1) & np.isfinite(arrays.values).all(axis=-1)
                        first = min(int(np.argmax(usable.sum(axis=-1))), max(0, len(arrays.frames) - 8))
                        selected = slice(first, min(first + 8, len(arrays.frames)))
                        positions = arrays.values[selected]
                        present = arrays.present[selected].all(axis=-1) & np.isfinite(positions).all(axis=-1)
                        recovered = geometry.recover(positions=positions, landmark_present=present)
                        identity = SourceIdentity(source_id=source, sensor_group=item[0].sensor_group,
                                                  model_id=model_id)
                        timeline = SampleTiming(timeline_id=f"{source}:reference_samples",
                            clock_id=f"{item[0].sensor_group}:recording_relative", source_identity=identity,
                            sample_ids=arrays.frames[selected], timestamps_s=arrays.timestamps[selected])
                    axes = (timeline.sample_axis, AxisDefinition("entity_identity", geometry.segment_names))
                    status = CompanionTensor("solver_status", recovered.status,
                                             TensorLayout(axes=axes, dtype=recovered.status.dtype))
                    self.assertTrue(np.any(recovered.status == 1), model_id)
                    for kind, values in (("SEGMENT_ORIGINS", recovered.origins),
                                         ("ROTATIONS_WORLD", recovered.orientations)):
                        declared = next(channel for channel in descriptor.channels
                                        if channel.source == source and str(channel.kind) == kind)
                        self.assertEqual(geometry.segment_names, declared.names)
                        layout = TensorLayout(axes=(*axes, AxisDefinition("component_identity", tuple(declared.components))),
                            dtype=values.dtype, component_units=tuple(declared.components.values()),
                            source_identity=identity, channel_kind=kind, reference_id=declared.reference_frame)
                        tensor = DataTensor(values, layout,
                            ScientificProvenance("model_estimate", "landmark_pose_recovery", model_id=model_id), (status,))
                        series = TimeSeries(tensor, timeline)
                        self.assertIs(series.data_tensor.data_values, values)
                        self.assertIs(series.data_tensor.companion_values("solver_status"), recovered.status)
                        selected_frame = series.immutable_copy().frame_view(2)
                        np.testing.assert_array_equal(selected_frame.data_tensor.data_values, values[2:3])
                        np.testing.assert_array_equal(selected_frame.data_tensor.companion_values("solver_status"),
                                                      recovered.status[2:3])
                        self.assertEqual(selected_frame.sample_timing.sample_ids.tolist(), timeline.sample_ids[2:3].tolist())
                    # PoseSolution objects remain scientific metadata, never a dense numeric payload.
                    with self.assertRaisesRegex(ValueError, "scalar boolean or numeric"):
                        TensorLayout(axes=axes, dtype=recovered.solutions.dtype)
                    checked_models.add(model_id)
                self.assertEqual(checked_models, set(descriptor.models))
        finally:
            self.assertEqual(file_digest(structure.data_parquet_path), original)
