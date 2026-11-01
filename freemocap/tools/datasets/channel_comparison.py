"""Compare scientific channel definitions and numerical results."""
import numpy as np
from freemocap.core.recording.parquet_storage.parquet_reader import read_metadata
from freemocap.core.recording.result_processing.saved_reconstruction import (
    read_saved_channel, read_saved_reconstruction, SavedReconstructionRequest, SavedPointPolicy,
)
from freemocap.system.recording_structure.recording_structure import RecordingStructure

def compare_saved_channels(left: RecordingStructure, right: RecordingStructure) -> list[dict]:
    metadata = [read_metadata(path=structure.data_parquet_path) for structure in (left, right)]
    def compare_definition(expected, actual, path):
        if path.startswith('scale_fits/') and path.endswith(('/fit/measured_segment_names', '/fit/voting_segment_names')):
            # ModelScaleFit declares these as frozensets. JSON order varies with
            # each interpreter's hash seed; membership is the scientific contract.
            if sorted(expected) != sorted(actual):
                raise ValueError(f'Scientific segment membership differs: {path}')
            return
        if path.startswith("scale_fits/") and path.endswith("/inputs/points"):
            # Roundoff-equivalent arrays can have different exact byte hashes;
            # their complete numerical channels are compared below.
            return
        if isinstance(expected, dict):
            if not isinstance(actual, dict) or expected.keys() != actual.keys():
                raise ValueError(f"Scientific definition keys differ: {path}")
            for key in expected:
                compare_definition(expected[key], actual[key], f"{path}/{key}")
        elif isinstance(expected, list):
            if not isinstance(actual, list) or len(expected) != len(actual):
                raise ValueError(f"Scientific definition lengths differ: {path}")
            for index, (first, second) in enumerate(zip(expected, actual, strict=True)):
                compare_definition(first, second, f"{path}/{index}")
        elif isinstance(expected, float):
            np.testing.assert_allclose(actual, expected, atol=1e-6, rtol=1e-8, err_msg=path)
        elif expected != actual:
            raise ValueError(f"Scientific definition differs: {path}")
    # Compare equivalent arrays across routes, but verify each local fit fingerprint
    # against its own exact saved inputs using the production resume reader.
    for structure, item in zip((left, right), metadata, strict=True):
        run = item.runs[0]
        for fit in run.scale_fits:
            source = run.sources[fit.source].definition
            read_saved_reconstruction(SavedReconstructionRequest(structure=structure, run_id=0,
                sensor_group=fit.sensor_group, point_source=source["tracker"], model_id=source["model_id"],
                point_policy=SavedPointPolicy.FILTERED, compute_center_of_mass=True))
    definitions = [item.runs[0].model_dump(mode="json") for item in metadata]
    for name in ("sensor_groups", "reference_frames", "models", "camera_geometry", "static_channels", "scale_fits"):
        compare_definition(definitions[0][name], definitions[1][name], name)
    def channel_key(channel):
        return (channel.sensor_group, channel.source, channel.reference_frame, channel.kind)
    channels = [{channel_key(channel): channel for channel in item.runs[0].channels} for item in metadata]
    if channels[0].keys() != channels[1].keys():
        raise ValueError("Saved channel coverage differs")
    reports = []
    for key, channel in channels[0].items():
        other = channels[1][key]
        if channel != other:
            raise ValueError(f"Saved channel definitions differ: {key}")
        expected = read_saved_channel(structure=left, run_id=0, metadata=metadata[0], channel=channel)
        actual = read_saved_channel(structure=right, run_id=0, metadata=metadata[1], channel=other)
        if expected.frames != actual.frames or expected.timestamps_s != actual.timestamps_s:
            raise ValueError(f"Saved sample identity differs: {key}")
        np.testing.assert_array_equal(np.isnan(expected.values), np.isnan(actual.values))
        np.testing.assert_allclose(actual.values, expected.values, atol=1e-6, rtol=1e-8)
        finite = np.isfinite(expected.values)
        maximum = float(np.max(np.abs(actual.values[finite] - expected.values[finite]), initial=0))
        reports.append(dict(channel=list(key), values=int(expected.values.size), maximum_absolute_error=maximum,
                            absolute_tolerance=1e-6, relative_tolerance=1e-8))
    return reports
