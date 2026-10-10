"""Exercise generated tutorials and the notebook through scientific publication.

Run with unittest; notebook execution additionally needs pandas in the test environment.
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
            result = self.export(('notebook',), keep=retained)
            self.assertEqual(len(result.files), 1)
            manifest = verified_manifest(result.manifest_path)
            self.assertEqual(next(iter(manifest.artifacts.values())).format, 'notebook')
            notebook = json.loads(result.files[0].read_text(encoding='utf-8'))
            self.assertEqual(notebook['nbformat'], 4)
            for cell in notebook['cells']:
                if cell['cell_type'] == 'code':
                    self.assertEqual(cell['outputs'], [])
                    compile(''.join(cell['source']), str(result.files[0]), 'exec')
            setup = ''.join(notebook['cells'][1]['source']).split('from pathlib')[0]
            scope = {}
            exec(setup, scope)
            self.assertEqual((result.files[0].parent / scope['SOURCE_PATH']).resolve(), self.structure.data_parquet_path.resolve())
            self.assertEqual(scope['RUN_ID'], 3)
            self.assertEqual(len(scope['CHANNELS']), 3)
        guide = self.structure.exports_dir / 'README.md'
        guide.write_text('Student notes', encoding='utf-8')
        self.export(('notebook',))
        self.assertEqual(guide.read_text(), 'Student notes')
        with self.assertRaises(FileExistsError):
            self.export(('notebook',), keep=True)

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

    @unittest.skipUnless(importlib.util.find_spec('pandas'), 'Notebook execution requires pandas')
    def test_notebook_matches_exported_arrays_and_rejects_changed_source(self):
        result = self.export(('notebook', 'npz'))
        notebook_path = next(p for p in result.files if p.suffix == '.ipynb')
        notebook = json.loads(notebook_path.read_text())
        codes = [''.join(c['source']) for c in notebook['cells'] if c['cell_type'] == 'code']
        with in_directory(notebook_path.parent):
            scope = {}
            exec(codes[0], scope)
            with np.load(next(p for p in result.files if p.suffix == '.npz'), allow_pickle=False) as archive:
                for index, channel in enumerate(scope['CHANNELS']):
                    exec(codes[1].replace('channel_index = 0', f'channel_index = {index}'), scope)
                    np.testing.assert_array_equal(scope['values'], archive[channel['numpy_key'] + '.values'])
                    exec(codes[2], scope)
            self.structure.data_parquet_path.write_bytes(b'changed source')
            with self.assertRaisesRegex(ValueError, 'recording changed'):
                exec(codes[0], {})


if __name__ == '__main__':
    unittest.main()
