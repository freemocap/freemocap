"""Exercise generated tutorials and the notebook through scientific publication.

Run with unittest; notebook execution additionally needs pandas and plotly in the test environment.
"""
import importlib.util
import json
import os
from pathlib import Path
import re
import tempfile
import unittest
from contextlib import contextmanager

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from freemocap.core.recording.data_descriptors.recording_descriptor import RecordingMetadata
from freemocap.core.recording.exports.publication import verified_manifest
from freemocap.core.recording.exports.requests import ScientificExportRequest
from freemocap.core.recording.exports.wide_csv import export_scientific
from freemocap.core.recording.sample_encoding.arrow_schema import DESCRIPTOR_KEY, SAMPLE_SCHEMA
from freemocap.system.recording_structure.recording_structure import RecordingStructure


@contextmanager
def in_directory(path):
    previous = Path.cwd()
    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(previous)
        plt.close('all')



class AnimationBoundsTests(unittest.TestCase):
    def test_fixed_cube_ignores_outliers_and_missing_samples(self):
        import ast
        from freemocap.core.recording.exports.notebook import ANIMATION

        # Execute the actual generated scene setup without optional Plotly/Pandas.
        body = next(node for node in ast.parse(ANIMATION).body if isinstance(node, ast.If)).orelse
        start = next(i for i, node in enumerate(body) if isinstance(node, ast.Assign)
                     and any(isinstance(t, ast.Name) and t.id == 'scene' for t in node.targets))
        stop = next(i for i, node in enumerate(body) if isinstance(node, ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id == 'frames' for t in node.targets))
        setup = compile(ast.Module(body=body[start:stop], type_ignores=[]), '<animation bounds>', 'exec')
        points = np.array([[100., 200., 300.]] * 5 + [[900000., -800000., 700000.],
                                                  [np.nan, np.inf, -np.inf]])[:, None, :]
        for unit, scale, half_width in [('mm', 1., 1500.), ('m', .001, 1.5), ('cm', .1, 150.)]:
            with self.subTest(unit=unit):
                scope = dict(np=np, xyz=points * scale, xyz_indices=[0, 1, 2],
                             channel=dict(units=[unit] * 3))
                exec(setup, scope)
                self.assertEqual(scope['scene']['aspectmode'], 'cube')
                for axis, center in zip('xyz', [100., 200., 300.]):
                    settings = scope['scene'][axis + 'axis']
                    np.testing.assert_allclose(settings['range'],
                                               [center * scale - half_width, center * scale + half_width])
                    self.assertFalse(settings['autorange'])
        scope['xyz'] = np.full((2, 1, 3), np.nan)
        exec(setup, scope)
        np.testing.assert_array_equal(scope['scene']['xaxis']['range'], [-150., 150.])


class ExplorerExportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.structure = RecordingStructure(base_directory=Path(self.temporary.name), recording_name='recording')
        self.structure.full_path.mkdir()
        channels = [dict(sensor_group='camera', source='model', reference_frame='world', kind=kind,
            names=['body.nose'], components=components, stage='reconstruction')
            for kind, components in [
                ('LANDMARKS_3D', dict(x='mm', y='mm', z='mm')),
                ('OVERLAY_2D', dict(x='px', y='px', visibility='1')),
                ('SEGMENT_ORIGINS', dict(x='mm', y='mm', z='mm')),
                ('ROTATIONS_WORLD', dict(w='1', x='1', y='1', z='1'))]]
        run = dict(sensor_groups={'camera': dict(clock_description='camera', sample_count=2)},
            sources={'model': dict(kind='tracker', definition={})},
            reference_frames={'world': dict(units='mm')}, models={}, processing={}, channels=channels)
        metadata = RecordingMetadata(recording_id='recording', selected_run_id=3, runs={0: run, 3: run})
        rows = []
        for rid in (0, 3):
            for channel in channels:
                for frame, timestamp in ((10, .125), (42, .987)):
                    for ci, (component, unit) in enumerate(channel['components'].items()):
                        rows.append(dict(run_id=rid, sensor_group='camera', source='model', reference_frame='world',
                            channel=channel['kind'], name='body.nose', component=component, units=unit,
                            frame_number=frame, timestamp_s=timestamp,
                            value=None if frame == 42 and component == 'x' else float(rid + ci)))
        table = pa.Table.from_pylist(rows, schema=SAMPLE_SCHEMA).replace_schema_metadata(
            {DESCRIPTOR_KEY: metadata.model_dump_json().encode()})
        pq.write_table(table, self.structure.data_parquet_path)

    def export(self, formats, **kwargs):
        return export_scientific(structure=self.structure, request=ScientificExportRequest(
            formats=formats, data=('LANDMARKS_3D', 'OVERLAY_2D', 'SEGMENT_POSES'), **kwargs))

    def test_publication_relative_paths_and_preserved_guides(self):
        for retained in (False, True):
            result = self.export(('notebook',), keep=retained, run_id=3 if retained else 0)
            self.assertEqual(len(result.files), 1)
            manifest = verified_manifest(result.manifest_path)
            self.assertEqual(next(iter(manifest.artifacts.values())).format, 'notebook')
            notebook = json.loads(result.files[0].read_text(encoding='utf-8'))
            self.assertEqual(notebook['nbformat'], 4)
            self.assertEqual(result.files[0].parent, self.structure.full_path)
            self.assertFalse((result.manifest_path.parent / result.files[0].name).exists())
            self.assertEqual(next(iter(manifest.artifacts.values())).location, 'recording')
            for cell in notebook['cells']:
                if cell['cell_type'] == 'code':
                    self.assertEqual(cell['outputs'], [])
                    compile(''.join(cell['source']), str(result.files[0]), 'exec')
            codes = [''.join(c['source']) for c in notebook['cells'] if c['cell_type'] == 'code']
            # Loading the snapshot needs only the standard library; generation and
            # portable paths must work even without an analysis environment.
            with in_directory(result.files[0].parent):
                import hashlib
                scope = dict(Path=Path, json=json, hashlib=hashlib)
                exec(codes[1], scope)
                exec(codes[2], scope)
                self.assertEqual(scope['parquet_path'].resolve(), self.structure.data_parquet_path.resolve())
                self.assertEqual(scope['notebook_path'].resolve(), result.files[0].resolve())
            self.assertEqual(scope['RUN_ID'], 3 if retained else 0)
            self.assertEqual(len(scope['CHANNELS']), 3)
            self.assertNotIn('CHANNELS = json.loads(', ''.join(codes))
            self.assertLess(len(''.join(notebook['cells'][0]['source'])), 250)
        guide = self.structure.exports_dir / 'README.md'
        guide.write_text('Student notes', encoding='utf-8')
        self.export(('notebook',))
        self.assertEqual(guide.read_text(), 'Student notes')
        with self.assertRaises(FileExistsError):
            self.export(('notebook',), keep=True)

    def test_root_notebook_publication_recovers_after_manifest_failure(self):
        from unittest.mock import patch
        from freemocap.core.recording.exports import publication

        replace = os.replace
        def interrupt_manifest(source, target):
            if Path(target).name.endswith('_recording_info.json'):
                raise OSError('interrupted manifest publication')
            return replace(source, target)

        with patch.object(publication.os, 'replace', side_effect=interrupt_manifest):
            with self.assertRaisesRegex(OSError, 'interrupted manifest'):
                self.export(('notebook',))
        directory = self.structure.exports_dir / 'run-3'
        notebook = self.structure.full_path / 'recording.run-3.explorer.ipynb'
        self.assertTrue(notebook.is_file())
        manifest_path = directory / 'recording.run-3_recording_info.json'
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            verified_manifest(manifest_path)
        publication.finish_publication(directory)
        manifest = verified_manifest(manifest_path)
        self.assertEqual(manifest.artifacts[notebook.name].location, 'recording')
        self.assertFalse((directory / notebook.name).exists())

    def test_notebook_is_only_created_when_requested(self):
        self.export(('npz',))
        self.assertEqual(list(self.structure.full_path.glob('*.ipynb')), [])

    def test_root_notebook_edits_are_preserved(self):
        result = self.export(('notebook',))
        result.files[0].write_text('My analysis', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'missing or changed'):
            self.export(('notebook',))
        self.assertEqual(result.files[0].read_text(), 'My analysis')

    def test_unmanaged_root_notebook_is_preserved(self):
        target = self.structure.full_path / 'recording.run-3.explorer.ipynb'
        target.write_text('My analysis', encoding='utf-8')
        with self.assertRaisesRegex(FileExistsError, 'outside this export'):
            self.export(('notebook',))
        self.assertEqual(target.read_text(), 'My analysis')

    def test_notebook_rejects_changed_source_without_plotting_dependencies(self):
        import hashlib
        result = self.export(('notebook',))
        notebook_path = result.files[0]
        notebook = json.loads(notebook_path.read_text(encoding='utf-8'))
        codes = [''.join(c['source']) for c in notebook['cells'] if c['cell_type'] == 'code']
        with in_directory(notebook_path.parent):
            scope = dict(Path=Path, json=json, hashlib=hashlib)
            exec(codes[1], scope)
            self.structure.data_parquet_path.write_bytes(b'changed source')
            with self.assertRaisesRegex(ValueError, 'recording changed'):
                exec(codes[2], scope)

    def test_numpy_tutorial_examples_execute(self):
        result = self.export(('npy', 'npz', 'wide_csv'))
        root = result.manifest_path.parent
        for folder in (root, root / 'npy'):
            code = re.search(r'```python\n(.*?)```', (folder / 'README.md').read_text(), re.S).group(1)
            with in_directory(folder):
                scope = {}
                exec(compile(code, 'README.md', 'exec'), scope)
                self.assertEqual(scope['values'].shape, (2, 1, 3))
                np.testing.assert_array_equal(scope['frames'], [10, 42])
        self.assertTrue((root / 'csv' / 'README.md').is_file())

    @unittest.skipUnless(importlib.util.find_spec('pandas') and importlib.util.find_spec('plotly'),
                         'Notebook execution requires pandas and plotly')
    def test_notebook_matches_exported_arrays_and_rejects_changed_source(self):
        result = self.export(('notebook', 'npz'))
        notebook_path = next(p for p in result.files if p.suffix == '.ipynb')
        notebook = json.loads(notebook_path.read_text())
        codes = [''.join(c['source']) for c in notebook['cells'] if c['cell_type'] == 'code']
        with in_directory(notebook_path.parent):
            scope = {}
            from unittest.mock import patch
            self.addCleanup(patch.stopall)
            patch('plotly.graph_objects.Figure.show').start()
            for code in codes[:3]:
                exec(code, scope)
            with np.load(next(p for p in result.files if p.suffix == '.npz'), allow_pickle=False) as archive:
                for index, channel in enumerate(scope['CHANNELS']):
                    exec(codes[3].replace('channel_index = 0', f'channel_index = {index}'), scope)
                    exec(codes[4], scope)
                    np.testing.assert_array_equal(scope['values'], archive[channel['numpy_key'] + '.values'])
                    for code in codes[5:]:
                        exec(code, scope)
                    coordinates = [axis for axis in ('x', 'y', 'z') if axis in channel['components']]
                    self.assertEqual(len(scope['fig'].data), len(coordinates))
                    np.testing.assert_array_equal(scope['fig'].data[0].x, [0, .862])
                    if 'z' in coordinates:
                        self.assertEqual([f.name for f in scope['animation'].frames], ['10', '42'])
                        self.assertEqual(scope['animation'].layout.scene.xaxis.title.text, 'X (mm)')
            self.structure.data_parquet_path.write_bytes(b'changed source')
            with self.assertRaisesRegex(ValueError, 'recording changed'):
                exec(codes[2], scope)


if __name__ == '__main__':
    unittest.main()
