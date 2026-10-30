"""Real prepared recording -> scientific runtime tensors -> portable NumPy datasets."""
import json
import os
from pathlib import Path
import shutil

import numpy as np
import pytest

from skellyforge.core.data_tensors import read_numpy_dataset
from freemocap.core.recording.exports import arrays, numpy_dataset, publication, wide_csv
from freemocap.core.recording.exports.requests import ScientificExportRequest
from freemocap.core.recording.parquet_storage.channel_arrays import read_channel_arrays
from freemocap.core.recording.parquet_storage.recording_view import recording_view
from freemocap.system.recording_structure.recording_structure import RecordingStructure
from freemocap.tests.reference_paths import prepared_root
from freemocap.tools.datasets.catalog import TEST_DATA
from freemocap.tools.datasets.workflow import checked_ready


def test_reference_numpy_channels_fit_evidence_and_definitions(tmp_path):
    if not os.environ.get('FREEMOCAP_PROVENANCE_PREPARED_ROOT'):
        pytest.skip('Set the prepared reference-data root')
    # Numerical-profile preparation is sufficient input. This test validates its
    # newly produced exports; it does not require preexisting Blender/CSV outputs.
    ready = checked_ready(prepared_root() / TEST_DATA.name, require_complete=False, check_exports=False)
    assert ready is not None
    source_path = Path(ready['recording']) / f'{TEST_DATA.name}_data.parquet'
    original_hash = publication.digest(source_path)
    structure = RecordingStructure(base_directory=tmp_path, recording_name=TEST_DATA.name)
    structure.full_path.mkdir()
    shutil.copy2(source_path, structure.data_parquet_path)
    request = ScientificExportRequest(formats=('npy', 'npz'),
        data=('LANDMARKS_3D', 'RAW_KEYPOINTS_3D', 'KEYPOINTS_3D', 'OVERLAY_2D', 'SEGMENT_POSES'))
    result = wide_csv.export_scientific(structure=structure, request=request)
    manifest = publication.verified_manifest(result.manifest_path)
    descriptors = manifest.snapshots[result.source_sha256]['numpy_datasets']
    npy = read_numpy_dataset(result.manifest_path.parent / descriptors['npy']['path'])
    npz = read_numpy_dataset(result.manifest_path.parent / descriptors['npz']['path'])
    assert npy.channel_identities == npz.channel_identities
    assert npy.definition_documents == npz.definition_documents
    all_data = (*npy.time_series, *npy.static_tensors)
    documents = {item.definition_id: json.loads(item.content_json) for item in npy.definition_documents}
    with recording_view(structure.data_parquet_path) as view:
        run_id, selected = arrays.resolve_selection(view, request)
        run = view.metadata.runs[run_id]
        native = numpy_dataset.scientific_selection(run, selected)
        assert len(all_data) == len(native)
        by_context = {}
        for data in all_data:
            tensor = data.data_tensor if hasattr(data, 'data_tensor') else data
            layout = tensor.tensor_layout
            identity = layout.source_identity
            key = (identity.sensor_group, identity.source_id, layout.reference_id, layout.channel_kind)
            by_context[key] = data
        for context, channel, static_values in native:
            data = by_context[(context.sensor_group, context.source, context.reference_frame, context.channel)]
            tensor = data if context.static else data.data_tensor
            assert tensor.tensor_layout.source_identity == numpy_dataset.declared_source(run, context)
            assert numpy_dataset.axis_definition(tensor.tensor_layout, 'component_identity').identifiers == tuple(channel.components)
            assert tensor.tensor_layout.component_units == tuple(channel.components.values())
            with read_channel_arrays(view, run_id, context, channel, static_values=static_values) as expected:
                np.testing.assert_array_equal(tensor.data_values, expected.values)
                np.testing.assert_array_equal(tensor.companion_values('entry_presence'), expected.present)
                if not context.static:
                    np.testing.assert_array_equal(data.sample_timing.sample_ids, expected.frames)
                    np.testing.assert_array_equal(data.sample_timing.timestamps_s, expected.timestamps)
            assert not {'solver_status', 'hydration_status'} & {item.metadata_name for item in tensor.companion_tensors}
            if context.channel == 'OVERLAY_2D':
                assert 'visibility' in channel.components
                assert tensor.tensor_layout.source_identity.camera_id == run.reference_frames[context.reference_frame]['camera_id']
            if context.channel in {'SEGMENT_SCALES', 'SEGMENT_LENGTHS'}:
                fit = next(saved.fit for saved in run.scale_fits if saved.source == context.source
                           and saved.sensor_group == context.sensor_group)
                np.testing.assert_array_equal(tensor.companion_values('measured_support'),
                                              np.isin(channel.names, tuple(fit.measured_segment_names)))
                np.testing.assert_array_equal(tensor.companion_values('voting_support'),
                                              np.isin(channel.names, tuple(fit.voting_segment_names)))
                assert tensor.data_values.ndim == len(tensor.tensor_layout.axes) == 2
            if tensor.tensor_layout.source_identity.model_id is not None:
                model_id = tensor.tensor_layout.source_identity.model_id
                assert documents[f'model:{model_id}'] == run.models[model_id].model_dump(mode='json')
                assert documents[f'fit_inputs:{context.sensor_group}:{context.source}']['inputs']
                upstream = run.sources[context.source].definition['tracker']
                assert f'source:{upstream}' in documents
        assert 'SEGMENT_POSES' not in {identity.channel_kind for identity in npy.channel_identities}
        assert {'SEGMENT_ORIGINS', 'ROTATIONS_WORLD'} <= {identity.channel_kind for identity in npy.channel_identities}
    for first, second in zip(all_data, (*npz.time_series, *npz.static_tensors), strict=True):
        first_tensor = first.data_tensor if hasattr(first, 'data_tensor') else first
        second_tensor = second.data_tensor if hasattr(second, 'data_tensor') else second
        assert first_tensor.tensor_layout == second_tensor.tensor_layout
        assert first_tensor.scientific_provenance == second_tensor.scientific_provenance
        assert first_tensor.data_values.dtype.str == second_tensor.data_values.dtype.str
        np.testing.assert_array_equal(first_tensor.data_values, second_tensor.data_values)
        for first_companion, second_companion in zip(first_tensor.companion_tensors, second_tensor.companion_tensors, strict=True):
            assert first_companion.metadata_name == second_companion.metadata_name
            assert first_companion.tensor_layout == second_companion.tensor_layout
            assert first_companion.data_values.dtype.str == second_companion.data_values.dtype.str
            np.testing.assert_array_equal(first_companion.data_values, second_companion.data_values)
        if hasattr(first, 'sample_timing'):
            first_timing, second_timing = first.sample_timing, second.sample_timing
            assert first.sample_axis_name == second.sample_axis_name
            assert first_timing.timeline_id == second_timing.timeline_id
            assert first_timing.clock_id == second_timing.clock_id
            assert first_timing.clock_epoch == second_timing.clock_epoch
            assert first_timing.source_identity == second_timing.source_identity
            np.testing.assert_array_equal(first_timing.sample_ids, second_timing.sample_ids)
            np.testing.assert_array_equal(first_timing.timestamps_s, second_timing.timestamps_s)
    assert publication.digest(source_path) == original_hash == publication.digest(structure.data_parquet_path)
