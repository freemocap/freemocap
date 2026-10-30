"""Stage Forge NumPy datasets within Core's existing recoverable publication."""
from contextlib import ExitStack, nullcontext
from time import perf_counter

from skellyforge.core.data_tensors import NumpyDatasetWriter, TimeSeries
from freemocap.core.recording.exports.arrays import check_cancelled
from freemocap.core.recording.exports.numpy_dataset import (
    channel_definitions, runtime_channels, saved_channel_tensor, scientific_selection, tensor_description,
)
from freemocap.core.recording.exports.publication import ExportArtifact, digest, artifact_path


def stage_numpy_exports(*, view, run_id, selected, formats, staging, directory, prefix, source_hash,
                        timings, runtime_dataset=None, cancelled=None, progress=None):
    native = scientific_selection(view.metadata.runs[run_id], selected)
    runtime = None if runtime_dataset is None else runtime_channels(runtime_dataset,
        metadata=view.metadata, run_id=run_id, selected=native)
    definitions = {document.definition_id: document for document in channel_definitions(view.metadata, run_id, native)}
    if runtime_dataset is not None:
        for document in runtime_dataset.definition_documents:
            if document.definition_id in definitions and document != definitions[document.definition_id]:
                raise ValueError('Runtime and recording definition documents conflict')
            definitions[document.definition_id] = document
    numpy_directory = 'npy'
    archive_name = f'{prefix}.npz'
    descriptions, payloads, timing_counts, timing_contexts = {}, {}, {}, {}
    writers = {}
    with ExitStack() as stack:
        for output_format in ('npy', 'npz'):
            if output_format in formats:
                destination = staging / (numpy_directory if output_format == 'npy' else archive_name)
                writers[output_format] = stack.enter_context(NumpyDatasetWriter(destination,
                    recording_id=view.metadata.recording_id, run_id=run_id, definition_documents=tuple(definitions.values()),
                    format=output_format, verify=True))
        for index, item in enumerate(native):
            check_cancelled(cancelled)
            context = item[0]
            if progress:
                progress(index, len(native), f'Exporting NumPy {context.channel} ({context.source})')
            started = perf_counter()
            manager = (nullcontext(runtime[context.key]) if runtime is not None else
                saved_channel_tensor(view, run_id, item, source_hash=source_hash, scratch=staging, cancelled=cancelled))
            with manager as data:
                timings['array_assembly'] += perf_counter() - started
                descriptions[context.key] = tensor_description(context, data)
                tensor = data.data_tensor if isinstance(data, TimeSeries) else data
                for output_format, writer in writers.items():
                    check_cancelled(cancelled)
                    started = perf_counter()
                    entry = writer.add_series(data) if isinstance(data, TimeSeries) else writer.add_static(data)
                    timing_name = f'{output_format}_write_and_verify'
                    timings[timing_name] = timings.get(timing_name, 0.) + perf_counter() - started
                descriptions[context.key]['numpy_channel'] = entry
                payloads[entry['values_file']] = dict(context_key=context.key, role='values',
                    shape=list(tensor.data_values.shape), dtype=tensor.data_values.dtype.str)
                for companion_entry, companion in zip(entry['companion_tensors'], tensor.companion_tensors, strict=True):
                    payloads[companion_entry['values_file']] = dict(context_key=context.key, role=companion.metadata_name,
                        shape=list(companion.data_values.shape), dtype=companion.data_values.dtype.str)
                if isinstance(data, TimeSeries):
                    timing_counts[entry['timing_ref']] = data.sample_count
                    timing_contexts.setdefault(entry['timing_ref'], []).append(context.key)
                if tensor.companion_tensors:
                    del companion
                # Loop locals otherwise keep the previous channel alive while
                # the next reader allocates its numerical buffers.
                del tensor, data
            check_cancelled(cancelled)
    manifest = next(iter(writers.values())).manifest
    for timing in manifest['timings']:
        for key, role, dtype in (('sample_ids_file', 'sample_ids', 'int64'), ('timestamps_s_file', 'timestamps_s', 'float64')):
            payloads[timing[key]] = dict(role=role, shape=[timing_counts[timing['timing_key']]], dtype=dtype,
                context_keys=timing_contexts[timing['timing_key']])
    payloads['dataset.json'] = dict(role='dataset_metadata', context_keys=list(descriptions))
    common = dict(source_sha256=source_hash, source_revision=view.revision, run_id=run_id, columns=())
    artifacts = {}
    if 'npy' in writers:
        for filename in writers['npy'].filenames:
            details = dict(payloads[filename], validation='reload_exact' if filename != 'dataset.json' else 'manifest_contract',
                           validator_version=1)
            name = f'{numpy_directory}/{filename}'
            artifacts[name] = ExportArtifact(filename=name, sha256=digest(staging / name),
                rows=details.get('shape', [0])[0] if details.get('shape') else 0, format='npy', details=details, **common)
    if 'npz' in writers:
        artifacts[archive_name] = ExportArtifact(filename=archive_name, sha256=digest(staging / archive_name),
            rows=len(manifest['channels']), format='npz', details=dict(context_keys=list(descriptions),
                validation='reload_exact', validator_version=1), **common)
    metadata = {output_format: dict(format=manifest['format'], version=manifest['version'],
        path=numpy_directory if output_format == 'npy' else archive_name, context_keys=list(descriptions),
        value_origin='caller_supplied_runtime_dataset' if runtime is not None else 'saved_recording_channels',
        validation='NumPy arrays reloaded exactly; runtime inputs are not compared numerically with Parquet')
        for output_format in writers}
    return artifacts, descriptions, metadata


def preflight_numpy_directory(directory, previous):
    """Never absorb or delete unrelated files to create an exact NPY inventory."""
    numpy_path = artifact_path(directory, 'npy/dataset.json').parent
    if not numpy_path.exists():
        return
    if not numpy_path.is_dir():
        raise ValueError('NumPy export destination must be a directory')
    managed = {artifact.filename for artifact in previous.artifacts.values()
               if artifact.format == 'npy' and artifact.location == 'exports'} if previous else set()
    for path in numpy_path.iterdir():
        name = f'npy/{path.name}'
        artifact_path(directory, name)
        if not path.is_file() or (name not in managed and name != 'npy/README.md'):
            raise ValueError(f'Unmanaged file in NumPy export directory; preserve it elsewhere before exporting: {name}')
