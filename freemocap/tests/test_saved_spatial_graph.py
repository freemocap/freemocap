"""Numerical graph boundaries reuse real canonical checkpoint readers/writers."""
from unittest.mock import patch
import unittest

from freemocap.tests import test_recording_pipeline as fixtures
from freemocap.core.pipeline.dataflow.recording_executor import execute_recording_graph
from freemocap.core.pipeline.dataflow.saved_spatial_source import load_saved_spatial_source, load_saved_model_fits
from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig
from freemocap.core.pipeline.posthoc.saved_stage_processing import inspect_saved_stages


class SavedSpatialGraphTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.RecordingPipelineTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.fixture.root

    def prepare(self, stop='scale_fit', **options):
        graph, handlers = self.fixture.graph(stop_stage=stop, **options)
        result = execute_recording_graph(graph=graph, handlers=handlers)
        self.assertTrue(result.complete, result.failures)
        return graph, result

    def test_scale_fit_finish_saves_reloadable_fits_without_reconstruction(self):
        graph, result = self.prepare()
        self.assertNotIn('reconstruct_skeletons', result.outputs)
        stages = inspect_saved_stages(str(self.root))['runs'][0]['groups'][0]['stages']
        self.assertTrue(stages['scale_fit'])
        self.assertFalse(stages['reconstruction'])
        config = PosthocMocapPipelineConfig(start_stage='reconstruction', export_to_blender=False)
        source = load_saved_spatial_source(path=self.root, config=config)
        fits = load_saved_model_fits(source, source.numerical)
        self.assertEqual(set(fits), {b.model_id for b in source.numerical.bundles})

    def test_all_six_saved_3d_ranges_run_only_requested_operations(self):
        from freemocap.core.pipeline.dataflow.saved_spatial_pipeline import build_saved_spatial_pipeline
        stages = ('filtering', 'scale_fit', 'reconstruction')
        prerequisites = {'filtering': 'triangulation', 'scale_fit': 'filtering', 'reconstruction': 'scale_fit'}
        for index, start in enumerate(stages):
            for stop in stages[index:]:
                with self.subTest(start=start, stop=stop):
                    # Each range starts with its own minimal recording. Rerunning
                    # an earlier stage must NOT remove existing later products.
                    self.fixture = fixtures.RecordingPipelineTests()
                    self.fixture.setUp()
                    self.addCleanup(self.fixture.doCleanups)
                    self.root = self.fixture.fixture.root
                    self.prepare(prerequisites[start])
                    config = PosthocMocapPipelineConfig(start_stage=start, stop_stage=stop, export_to_blender=False)
                    source = load_saved_spatial_source(path=self.root, config=config)
                    reference = source.reference
                    graph, handlers = build_saved_spatial_pipeline(source=source, config=config)
                    self.assertNotIn('align_reference', handlers)
                    self.assertNotIn('match_and_triangulate', handlers)
                    self.assertNotIn('load_and_track', handlers)
                    self.assertEqual('filter_trajectories' in handlers, start == 'filtering')
                    self.assertEqual('reconstruct_skeletons' in handlers, stop == 'reconstruction')
                    result = execute_recording_graph(graph=graph, handlers=handlers)
                    self.assertTrue(result.complete, result.failure_tracebacks)
                    saved = inspect_saved_stages(str(self.root))['runs'][0]['groups'][0]['stages']
                    for stage in stages:
                        self.assertEqual(saved[stage], stages.index(stage) <= stages.index(stop))
                    from freemocap.core.recording.parquet_storage.parquet_reader import read_metadata
                    metadata = read_metadata(path=source.structure.data_parquet_path)
                    self.assertEqual(metadata.runs[source.run_id].reference_frames[reference.name],
                                     source.metadata.runs[source.run_id].reference_frames[reference.name])

    def restart(self):
        from freemocap.core.pipeline.dataflow.saved_spatial_pipeline import build_saved_spatial_pipeline
        config = PosthocMocapPipelineConfig(start_stage='reconstruction', export_to_blender=False)
        source = load_saved_spatial_source(path=self.root, config=config)
        graph, handlers = build_saved_spatial_pipeline(source=source, config=config)
        return source, graph, handlers

    def test_failed_reconstruction_preserves_previous_file(self):
        self.prepare('reconstruction')
        source, graph, handlers = self.restart()
        path = source.structure.data_parquet_path
        original = path.read_bytes()
        def fail(inputs):
            raise ValueError('Injected numerical failure')
        handlers['reconstruct_skeletons'] = fail
        result = execute_recording_graph(graph=graph, handlers=handlers)
        self.assertIn('save_stage_result', result.blocked)
        self.assertEqual(path.read_bytes(), original)

    def test_changed_fit_inputs_are_rejected(self):
        from dataclasses import replace
        import numpy as np
        self.prepare()
        source, _, _ = self.restart()
        changed = replace(source.numerical, keypoints_3d=np.nan_to_num(source.points.values) + 1)
        with self.assertRaisesRegex(ValueError, 'inputs changed'):
            load_saved_model_fits(source, changed)

    def test_changed_recording_revision_prevents_replacement(self):
        import os
        self.prepare()
        source, graph, handlers = self.restart()
        path = source.structure.data_parquet_path
        original = path.read_bytes()
        # Even identical metadata cannot authorize replacing a different snapshot.
        stat = path.stat()
        os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))
        result = execute_recording_graph(graph=graph, handlers=handlers)
        self.assertIn('Recording changed', result.failures['save_stage_result'])
        self.assertEqual(path.read_bytes(), original)

    def test_cancel_after_temporary_write_preserves_file_and_removes_temp(self):
        from concurrent.futures import CancelledError
        from freemocap.core.recording.parquet_storage import parquet_writer
        import pyarrow as pa
        self.prepare()
        source, _, _ = self.restart()
        path = source.structure.data_parquet_path
        original = path.read_bytes()
        # Cancellation arrives after the last batch: test the final rename guard.
        cancelled = False
        def batches():
            nonlocal cancelled
            yield pa.record_batch({'value': [1, 2, 3]})
            cancelled = True
        with self.assertRaises(CancelledError):
            parquet_writer.publish_parquet(path=path, schema=pa.schema([('value', pa.int64())]),
                batches=batches(), cancelled=lambda: cancelled)
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(list(path.parent.glob('*.parquet.tmp')), [])

    def test_application_saved_fit_route_never_opens_videos_or_calibration(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from freemocap.core.pipeline.dataflow.application_pipeline import run_application_graph
        self.prepare('filtering')
        request = SimpleNamespace(
            config=PosthocMocapPipelineConfig(start_stage='scale_fit', stop_stage='scale_fit', calibration_toml_path=None),
            recording=SimpleNamespace(full_recording_path=self.root),
            ipc=SimpleNamespace(should_continue=True), report=Mock(), report_operation=Mock(), performance=Mock())
        with patch('freemocap.core.pipeline.dataflow.application_pipeline.RecordingVideoSources.resolve',
                   side_effect=AssertionError('Opened videos')), patch(
                   'freemocap.core.tracking.recording_board_selection.resolve_recording_board',
                   side_effect=AssertionError('Scanned board')), patch(
                   'freemocap.core.tasks.calibration.shared.calibration_result.CalibrationResult.load_toml',
                   side_effect=AssertionError('Opened calibration')):
            run_application_graph(request=request)
        self.assertEqual(request.report.call_args.args[2], 1.0)
        self.assertIn('scale_fit', request.report.call_args.args[1])

    def test_new_runs_preserve_original_channels_and_exclude_unrequested_descendants(self):
        import numpy as np
        from freemocap.core.pipeline.posthoc.processing_request import ProcessingStage
        from freemocap.core.recording.parquet_storage.parquet_reader import read_metadata
        from freemocap.core.recording.result_processing.saved_reconstruction import read_saved_channel
        self.prepare('reconstruction')
        source, _, _ = self.restart()
        structure = source.structure
        stages = ('observations', 'triangulation', 'filtering', 'scale_fit', 'reconstruction')
        for stop in stages[:-1]:
            with self.subTest(stop=stop):
                before = read_metadata(path=structure.data_parquet_path)
                run = before.runs[0]
                later = {ProcessingStage(stage) for stage in stages[stages.index(stop) + 1:]}
                later.add(ProcessingStage.BIOMECHANICS)
                channels = [c for c in run.channels if c.stage in later]
                self.assertTrue(channels)
                values = [read_saved_channel(structure=structure, run_id=0, metadata=before, channel=c) for c in channels]
                graph, result = self.prepare(stop, run_save_mode='new_run')
                self.assertNotIn('reconstruct_skeletons', result.outputs)
                after = read_metadata(path=structure.data_parquet_path)
                target = after.runs[after.selected_run_id]
                self.assertNotEqual(after.selected_run_id, 0)
                self.assertFalse(any(c.stage in later for c in target.channels))
                self.assertEqual(after.runs[0], run)
                for channel, expected in zip(channels, values, strict=True):
                    self.assertIn(channel, after.runs[0].channels)
                    actual = read_saved_channel(structure=structure, run_id=0, metadata=after, channel=channel)
                    np.testing.assert_array_equal(actual.values, expected.values)
                    self.assertEqual(actual.frames, expected.frames)
                    self.assertEqual(actual.timestamps_s, expected.timestamps_s)
                self.assertTrue(all(c in after.runs[0].checkpoints for c in run.checkpoints if c.stage in later))
                if stop != 'scale_fit':
                    self.assertEqual(after.runs[0].scale_fits, run.scale_fits)

    def test_filter_only_overwrite_removes_dependent_fits_and_reconstruction(self):
        import numpy as np
        from freemocap.core.pipeline.dataflow.saved_spatial_pipeline import build_saved_spatial_pipeline
        from freemocap.core.recording.parquet_storage.parquet_reader import read_metadata
        from freemocap.core.recording.result_processing.saved_reconstruction import read_saved_channel
        from freemocap.core.pipeline.posthoc.processing_request import ProcessingStage
        self.prepare('reconstruction')
        config = PosthocMocapPipelineConfig(start_stage='filtering', stop_stage='filtering', export_to_blender=False)
        source = load_saved_spatial_source(path=self.root, config=config)
        before = source.metadata.runs[0]
        channels = [c for c in before.channels if c.stage in (ProcessingStage.RECONSTRUCTION, ProcessingStage.BIOMECHANICS)]
        values = [read_saved_channel(structure=source.structure, run_id=0, metadata=source.metadata, channel=c) for c in channels]
        graph, handlers = build_saved_spatial_pipeline(source=source, config=config)
        self.assertNotIn('fit_model_dimensions', handlers)
        self.assertNotIn('reconstruct_skeletons', handlers)
        result = execute_recording_graph(graph=graph, handlers=handlers)
        self.assertTrue(result.complete, result.failure_tracebacks)
        after = read_metadata(path=source.structure.data_parquet_path)
        self.assertFalse(after.runs[0].scale_fits)
        for channel in channels:
            self.assertNotIn(channel, after.runs[0].channels)

    def test_shared_coordinate_change_cannot_relabel_unselected_results(self):
        from freemocap.core.pipeline.posthoc.stage_execution_plan import StageExecutionPlan, retained_run
        from freemocap.core.pipeline.posthoc.processing_request import ProcessingStage
        from freemocap.core.recording.parquet_storage.checkpoint_publication import publish_checkpoint
        from freemocap.core.recording.parquet_storage.parquet_writer import recording_write_lock
        self.prepare('reconstruction')
        source, _, _ = self.restart()
        original = source.structure.data_parquet_path.read_bytes()
        plan = StageExecutionPlan(0, 0, (source.group,), (ProcessingStage.FILTERING,), ())
        retained = retained_run(base=source.metadata.runs[0], plan=plan)
        references = dict(retained.reference_frames)
        references[source.reference.name] = dict(references[source.reference.name], units='m')
        result = retained.model_copy(update={'reference_frames': references})
        with recording_write_lock(structure=source.structure):
            with self.assertRaisesRegex(ValueError, 'coordinate definitions'):
                publish_checkpoint(structure=source.structure, metadata=source.metadata,
                    plan=plan, result=result, computed_batches=())
        self.assertEqual(source.structure.data_parquet_path.read_bytes(), original)

    def test_new_numerical_run_preserves_source_and_overwrites_its_own_slot(self):
        from freemocap.core.pipeline.dataflow.saved_spatial_pipeline import build_saved_spatial_pipeline
        from freemocap.core.recording.parquet_storage.parquet_reader import read_metadata
        self.prepare('reconstruction')
        config = PosthocMocapPipelineConfig(start_stage='filtering', stop_stage='reconstruction',
            run_save_mode='new_run', export_to_blender=False)
        source = load_saved_spatial_source(path=self.root, config=config)
        original = source.metadata.runs[0]
        graph, handlers = build_saved_spatial_pipeline(source=source, config=config)
        result = execute_recording_graph(graph=graph, handlers=handlers)
        self.assertTrue(result.complete, result.failure_tracebacks)
        metadata = read_metadata(path=source.structure.data_parquet_path)
        self.assertEqual(set(metadata.runs), {0, 1})
        self.assertEqual(metadata.selected_run_id, 1)
        self.assertEqual(metadata.runs[0], original)
        config = config.model_copy(update={'base_run_id': 1, 'run_save_mode': 'overwrite', 'stop_stage': 'filtering'})
        source = load_saved_spatial_source(path=self.root, config=config)
        graph, handlers = build_saved_spatial_pipeline(source=source, config=config)
        result = execute_recording_graph(graph=graph, handlers=handlers)
        self.assertTrue(result.complete, result.failure_tracebacks)
        metadata = read_metadata(path=source.structure.data_parquet_path)
        self.assertEqual(set(metadata.runs), {0, 1})
        self.assertEqual(metadata.runs[0], original)
        self.assertFalse(metadata.runs[1].scale_fits)

    def test_changed_alignment_overwrite_replaces_3d_and_removes_old_skeleton(self):
        import numpy as np
        from freemocap.core.reconstruction.alignment_config import MocapAlignmentConfig
        from freemocap.core.reconstruction.reference_transform import ReferenceTransform
        from freemocap.core.pipeline.posthoc.processing_request import ProcessingStage
        from freemocap.core.recording.parquet_storage.parquet_reader import read_metadata
        self.prepare('reconstruction')
        source, _, _ = self.restart()
        matrix = np.eye(4); matrix[:3, 3] = [100., 200., 300.]
        self.prepare('triangulation', alignment=MocapAlignmentConfig(mode='calibration',
            additional_transform=ReferenceTransform(matrix=tuple(matrix.ravel()))))
        updated = read_metadata(path=source.structure.data_parquet_path).runs[0]
        self.assertFalse(updated.scale_fits)
        self.assertFalse(any(c.stage in (ProcessingStage.FILTERING, ProcessingStage.RECONSTRUCTION, ProcessingStage.BIOMECHANICS)
                             for c in updated.channels))

    def test_failed_new_run_reservation_is_not_reused(self):
        from freemocap.core.recording.result_processing.run_save_session import RunSaveSession
        self.prepare('reconstruction')
        source, _, _ = self.restart()
        original = source.structure.data_parquet_path.read_bytes()
        first = RunSaveSession.resolve(structure=source.structure, source_run_id=0, mode='new_run')
        second = RunSaveSession.resolve(structure=source.structure, source_run_id=0, mode='new_run')
        self.assertEqual((first.target_run_id, second.target_run_id), (1, 2))
        self.assertEqual(source.structure.data_parquet_path.read_bytes(), original)
        graph, result = self.prepare('reconstruction', run_save_mode='new_run')
        from freemocap.core.recording.parquet_storage.parquet_reader import read_metadata
        metadata = read_metadata(path=source.structure.data_parquet_path)
        self.assertEqual(set(metadata.runs), {0, 3})
        self.assertEqual(metadata.runs[0], source.metadata.runs[0])
        self.assertEqual(metadata.selected_run_id, 3)

    def test_cancelled_observation_save_preserves_existing_parquet(self):
        import multiprocessing
        from freemocap.core.recording.parquet_storage import parquet_writer
        self.prepare('reconstruction')
        source, _, _ = self.restart()
        original = source.structure.data_parquet_path.read_bytes()
        flag = multiprocessing.Value('b', False)
        graph, handlers = self.fixture.graph(stop_stage='observations', shutdown_flag=flag)
        real_fsync = parquet_writer.os.fsync
        def cancel_after_temporary_write(descriptor):
            real_fsync(descriptor)
            flag.value = True
        with patch.object(parquet_writer.os, 'fsync', side_effect=cancel_after_temporary_write):
            result = execute_recording_graph(graph=graph, handlers=handlers)
        self.assertFalse(result.complete)
        self.assertEqual(source.structure.data_parquet_path.read_bytes(), original)

    def test_saved_2d_new_run_reuses_tracking_and_preserves_source(self):
        from freemocap.core.recording.parquet_storage.parquet_reader import read_metadata
        from freemocap.core.pipeline.posthoc.processing_request import ProcessingStage
        self.prepare('reconstruction')
        source, _, _ = self.restart()
        original = source.metadata.runs[0]
        graph, result = self.prepare('reconstruction', start_stage='triangulation', run_save_mode='new_run')
        self.assertNotIn('load_and_track', result.outputs)
        updated = read_metadata(path=source.structure.data_parquet_path)
        self.assertEqual(updated.runs[0], original)
        self.assertEqual(updated.selected_run_id, 1)
        self.assertTrue(any(c.stage == ProcessingStage.RECONSTRUCTION for c in updated.runs[1].channels))
        from freemocap.core.recording.result_processing.saved_reconstruction import read_saved_channel
        import numpy as np
        for channel in original.channels:
            if channel.stage != ProcessingStage.OBSERVATIONS:
                continue
            old = read_saved_channel(structure=source.structure, metadata=updated, run_id=0, channel=channel)
            new = read_saved_channel(structure=source.structure, metadata=updated, run_id=1, channel=channel)
            np.testing.assert_array_equal(new.values, old.values)
            self.assertEqual(new.frames, old.frames)
            self.assertEqual(new.timestamps_s, old.timestamps_s)
