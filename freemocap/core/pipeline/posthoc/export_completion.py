"""Run independent saved-recording exports concurrently, with bounded supervision."""
from concurrent.futures import CancelledError, ThreadPoolExecutor

from freemocap.core.pipeline.posthoc.pipeline_phases import AggregatorPhase


def complete_recording_exports(request, *, worker_count=2):
    from freemocap.core.pipeline.posthoc.saved_stage_processing import recording_structure
    from freemocap.core.recording.parquet_storage.recording_view import recording_view

    if worker_count not in (1, 2):
        raise ValueError('Export supervision supports one or two workers')
    structure = recording_structure(str(request.recording.full_recording_path))
    config = request.config
    cancelled = lambda: not request.ipc.should_continue
    revision = None
    if config.scientific_exports.formats or config.export_tall_csv:
        with recording_view(structure.data_parquet_path) as view:
            revision = view.revision
    labels = {}
    if config.scientific_exports.formats:
        formats = ', '.join(format.upper().replace('_', ' ') for format in config.scientific_exports.formats)
        labels['scientific_files'] = f'Save {formats} files'
    if config.export_tall_csv:
        labels['tall_csv'] = 'Save tall CSV files'
    if config.export_to_blender:
        labels['blender'] = 'Create Blender scene and animation exports'
    for task_id, label in labels.items():
        request.report_export(task_id, label, 'waiting', 'Waiting to start')

    def run_export(task_id, action):
        label = labels[task_id]
        if cancelled():
            request.report_export(task_id, label, 'cancelled', 'Stopped before starting')
            return None, None, True
        request.report_export(task_id, label, 'running', 'Starting export')
        try:
            with request.performance.measure(f'export.{task_id}'):
                output = action()
            request.report_export(task_id, label, 'complete', output)
            return output, None, False
        except CancelledError:
            request.report_export(task_id, label, 'cancelled', 'Export stopped')
            return None, None, True
        except Exception as error:
            detail = f'{label} failed: {error}. Saved motion-capture results remain available.'
            request.report_export(task_id, label, 'failed', detail)
            return None, detail, False

    def scientific_export():
        from freemocap.core.recording.exports.requests import ScientificExportRequest
        from freemocap.core.recording.exports.wide_csv import export_scientific
        result = export_scientific(structure=structure,
            request=ScientificExportRequest(**config.scientific_exports.model_dump(),
                run_id=config.base_run_id, expected_revision=revision), cancelled=cancelled,
            progress=lambda done, total, message: request.report_export('scientific_files',
                labels['scientific_files'], 'running', message, done, total))
        return f'Scientific files saved and validated in {result.manifest_path.parent}'

    def tall_export():
        from freemocap.core.recording.exports.tall_csv import TallCsvRequest, export_tall_csv
        result = export_tall_csv(structure=structure,
            request=TallCsvRequest(run_id=config.base_run_id, expected_revision=revision), cancelled=cancelled)
        return f'Tall CSV files saved in {result.manifest_path.parent}'

    def blender_export():
        from freemocap.core.blender.export_to_blender import export_to_blender
        output = export_to_blender(recording_folder_path=request.recording.full_recording_path,
            blender_exe_path=config.blender_exe_path, open_file_on_completion=config.auto_open_blend_file,
            route=config.blender_import_route, package=config.blender_package,
            development_build_hash=config.blender_development_build_hash, sensor_group=config.sensor_group,
            run_id=config.base_run_id, blender_export_config=config.blender_export.model_dump(),
            cancelled=cancelled, progress=lambda message: request.report_export(
                'blender', labels['blender'], 'running', message))
        return f'Blender scene saved to {output}'

    def file_exports():
        # Both writers publish the same manifest under an exclusive fail-fast lock.
        # Preserve shared array reuse within scientific exports and serialize these
        # two transactions; neither depends on Blender's separate output files.
        results = []
        if 'scientific_files' in labels:
            results.append(run_export('scientific_files', scientific_export))
        if 'tall_csv' in labels:
            results.append(run_export('tall_csv', tall_export))
        return results

    results = []
    with request.performance.measure('exports.total'):
        # Two independent output destinations, at most two supervising threads.
        # Exiting this context joins both branches, including after cancellation.
        with ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix='RecordingExport') as workers:
            futures = []
            if 'scientific_files' in labels or 'tall_csv' in labels:
                futures.append(workers.submit(file_exports))
            if 'blender' in labels:
                futures.append(workers.submit(lambda: [run_export('blender', blender_export)]))
            for future in futures:
                results.extend(future.result())
    detail = 'Processing complete. Motion-capture results have been saved to the recording folder.'
    outputs = [output for output, _, _ in results if output]
    failures = [failure for _, failure, _ in results if failure]
    if outputs:
        detail += ' ' + '; '.join(outputs)
    if failures:
        raise RuntimeError(detail + '; requested exports incomplete: ' + '; '.join(failures))
    if cancelled() or any(stopped for _, _, stopped in results):
        raise CancelledError('Processing results saved; remaining exports cancelled')
    request.report(AggregatorPhase.COMPLETE, detail, 1.0)
