"""Missing results are a normal preview state; export and read errors remain errors."""
from pathlib import Path
import tempfile
import unittest
import pyarrow as pa
import pyarrow.parquet as pq
from freemocap.core.recording.data_descriptors.recording_descriptor import RecordingMetadata
from freemocap.core.recording.sample_encoding.arrow_schema import DESCRIPTOR_KEY, SAMPLE_SCHEMA
from fastapi import FastAPI
from fastapi.testclient import TestClient
from freemocap.api.http.posthoc.exports_router import exports_router
from freemocap.system.recording_structure.recording_structure import RecordingStructure


class ExportPreviewTests(unittest.TestCase):
    def test_missing_result_is_empty_but_invalid_folder_and_export_are_errors(self):
        app = FastAPI()
        app.include_router(exports_router)
        with tempfile.TemporaryDirectory() as temporary, TestClient(app) as client:
            for route in ('scientific', 'tall-csv'):
                with self.subTest(route=route):
                    response = client.get('/exports/' + route, params={'recording_path': temporary})
                    self.assertEqual(response.status_code, 204, response.text)
                    self.assertEqual(response.content, b'')
                    self.assertEqual(client.get('/exports/' + route, params={
                        'recording_path': str(Path(temporary) / 'missing')}).status_code, 404)
                    self.assertEqual(client.post('/exports/' + route, json={
                        'recording_path': temporary, 'formats': ['wide_csv']} if route == 'scientific' else {
                        'recording_path': temporary}).status_code, 404)

    def test_preview_becomes_available_after_parquet_is_published(self):
        app = FastAPI()
        app.include_router(exports_router)
        with tempfile.TemporaryDirectory() as temporary, TestClient(app) as client:
            folder = Path(temporary)
            structure = RecordingStructure(base_directory=folder.parent, recording_name=folder.name)
            for route in ('scientific', 'tall-csv'):
                self.assertEqual(client.get('/exports/' + route, params={'recording_path': temporary}).status_code, 204)
            metadata = RecordingMetadata(recording_id=folder.name, selected_run_id=3, runs={3: dict(
                sensor_groups={}, sources={}, reference_frames={}, models={}, processing={}, channels=[])})
            table = pa.Table.from_pylist([], schema=SAMPLE_SCHEMA).replace_schema_metadata(
                {DESCRIPTOR_KEY: metadata.model_dump_json().encode()})
            pq.write_table(table, structure.data_parquet_path)
            for route in ('scientific', 'tall-csv'):
                response = client.get('/exports/' + route, params={'recording_path': temporary})
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()['selected_run_id'], 3)
                self.assertTrue(response.json()['revision'])

    def test_corrupt_result_is_not_reported_as_absent(self):
        app = FastAPI()
        app.include_router(exports_router)
        with tempfile.TemporaryDirectory() as temporary, TestClient(app, raise_server_exceptions=False) as client:
            folder = Path(temporary)
            structure = RecordingStructure(base_directory=folder.parent, recording_name=folder.name)
            structure.data_parquet_path.write_bytes(b'not parquet')
            for route in ('scientific', 'tall-csv'):
                self.assertEqual(client.get('/exports/' + route, params={'recording_path': temporary}).status_code, 500)


if __name__ == '__main__':
    unittest.main()
