"""Saved channel assembly preserves identity across irregular Parquet batches."""
from pathlib import Path
import tempfile
import unittest
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from freemocap.core.recording.data_descriptors.recording_descriptor import (
    Channel, RecordingMetadata, RunDescriptor, SensorGroup, Source,
)
from freemocap.core.recording.sample_encoding.channel_series import ChannelSeries, SeriesSampling
from freemocap.core.recording.result_processing.saved_reconstruction import read_saved_channel
from freemocap.system.recording_structure.recording_structure import RecordingStructure
from freemocap.core.recording.parquet_storage.parquet_reader import recording_batches
from freemocap.core.recording.sample_encoding.arrow_schema import SampleValidator, DESCRIPTOR_KEY
from freemocap.core.recording.parquet_storage.recording_view import recording_view
from freemocap.core.recording.parquet_storage.channel_arrays import ChannelArrays, read_channel_arrays
from freemocap.core.recording.parquet_storage.channel_selection import ChannelSelection
from unittest.mock import patch


class ColumnarSavedReadTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.structure = RecordingStructure(base_directory=Path(self.directory.name), recording_name="test")
        self.structure.data_parquet_path.parent.mkdir(parents=True, exist_ok=True)
        self.channel = Channel(sensor_group="group", source="tracker", reference_frame="world",
            kind="RAW_KEYPOINTS_3D", names=("second", "first"),
            components={"z":"mm", "x":"mm", "y":"mm"}, stage="triangulation")
        self.metadata = RecordingMetadata(recording_id="test", selected_run_id=0, runs={0:RunDescriptor(
            sensor_groups={"group":SensorGroup(clock_description="test", sample_count=3)},
            sources={"tracker":Source(kind="tracker", definition={})}, reference_frames={"world":{}},
            models={}, processing={}, channels=(self.channel,))})
        self.values = np.arange(18, dtype=np.float64).reshape(3,2,3)
        self.values[1,0,1] = np.nan
        self.values[2,1,2] = -0.0
        self.batch = list(ChannelSeries(channel=self.channel, values=self.values).batches(SeriesSampling(
            frame_numbers=(3,8,14), timestamps_s=(.1,.2,.3), run_id=0)))[0]
        self.batch = self.batch.replace_schema_metadata({DESCRIPTOR_KEY: self.metadata.model_dump_json().encode()})

    def read(self, batch, row_group_size):
        pq.write_table(pa.Table.from_batches([batch]), self.structure.data_parquet_path,
                       row_group_size=row_group_size)
        return read_saved_channel(structure=self.structure, run_id=0, metadata=self.metadata, channel=self.channel)

    def test_irregular_chunks_preserve_axes_nulls_timing_and_readonly_values(self):
        # Trajectory-major order also exercises noncontiguous frame components.
        orders = [np.arange(18), np.arange(18).reshape(3,6).T.reshape(-1)]
        for order in orders:
            for size in (1,5,7,65536):
                with self.subTest(size=size, order=order.tolist()):
                    saved = self.read(self.batch.take(pa.array(order)), size)
                    np.testing.assert_array_equal(saved.values, self.values)
                    self.assertTrue(np.signbit(saved.values[2,1,2]))
                    self.assertFalse(saved.values.flags.writeable)
                    self.assertEqual(saved.frames, (3,8,14))
                    self.assertEqual(saved.timestamps_s, (.1,.2,.3))

    def test_invalid_and_incomplete_streams_fail_before_returning_data(self):
        for column, index, value in (("timestamp_s",1,.11), ("name",0,"unknown"),
            ("component",0,"unknown"), ("units",0,"wrong"), ("value",0,float("inf")), ("frame_number",12,15)):
            rows=self.batch.to_pylist(); rows[index][column]=value
            with self.subTest(column=column), self.assertRaises(ValueError):
                self.read(pa.RecordBatch.from_pylist(rows,schema=self.batch.schema), 5)
        with self.assertRaises(ValueError):
            self.read(self.batch.slice(0,17), 5)
        with self.assertRaises(ValueError):
            self.read(pa.RecordBatch.from_pylist(self.batch.to_pylist() + self.batch.slice(0,1).to_pylist(),
                                                schema=self.batch.schema), 5)

    def test_shared_view_arrays_survive_closure_without_aliasing_later_reads(self):
        self.read(self.batch, 7)
        with recording_view(self.structure.data_parquet_path) as view:
            with patch.object(pq.ParquetFile, '__init__', side_effect=AssertionError('Unexpected reopen')):
                saved = read_saved_channel(structure=self.structure, run_id=0,
                    metadata=self.metadata, channel=self.channel, view=view)
                later = read_saved_channel(structure=self.structure, run_id=0,
                    metadata=self.metadata, channel=self.channel, view=view)
        self.assertIsInstance(saved.channel_arrays, ChannelArrays)
        self.assertIs(saved.values, saved.channel_arrays.values)
        self.assertFalse(np.shares_memory(saved.values, later.values))
        np.testing.assert_array_equal(saved.values, self.values)
        self.assertTrue(saved.present.all())
        self.assertTrue(np.isnan(saved.values[1,0,1]))  # Recorded null remains present.
        for array in (saved.values, saved.present, saved.channel_arrays.frames, saved.channel_arrays.timestamps):
            self.assertFalse(array.flags.writeable)
        self.assertEqual(saved.channel_arrays.components, ('z','x','y'))

    def test_shared_assembly_distinguishes_null_from_absence_and_strict_read_rejects_gap(self):
        sparse = self.batch.slice(0,17)
        pq.write_table(pa.Table.from_batches([sparse]), self.structure.data_parquet_path, row_group_size=5)
        context = ChannelSelection(sensor_group='group', source='tracker', reference_frame='world', channel='RAW_KEYPOINTS_3D')
        with recording_view(self.structure.data_parquet_path) as view:
            with read_channel_arrays(view, 0, context, self.channel) as arrays:
                self.assertTrue(arrays.present[1,0,1])
                self.assertTrue(np.isnan(arrays.values[1,0,1]))
                self.assertFalse(arrays.present[2,1,2])
                self.assertTrue(np.isnan(arrays.values[2,1,2]))
            with self.assertRaises(ValueError):
                read_saved_channel(structure=self.structure, run_id=0,
                    metadata=self.metadata, channel=self.channel, view=view)

    def test_saved_reader_uses_declared_component_count_and_order(self):
        components = {name: '1' for name in ('fifth', 'second', 'first', 'fourth', 'third')}
        channel = self.channel.model_copy(update={'components': components})
        run = self.metadata.runs[0].model_copy(update={'channels': (channel,)})
        metadata = self.metadata.model_copy(update={'runs': {0: run}})
        values = np.arange(30, dtype=np.float64).reshape(3,2,5)
        values[1,1,4] = np.nan
        batches = [batch.replace_schema_metadata({DESCRIPTOR_KEY: metadata.model_dump_json().encode()})
            for batch in ChannelSeries(channel=channel, values=values).batches(SeriesSampling(
                frame_numbers=(3,8,14), timestamps_s=(.1,.2,.3), run_id=0))]
        pq.write_table(pa.Table.from_batches(batches), self.structure.data_parquet_path, row_group_size=7)
        saved = read_saved_channel(structure=self.structure, run_id=0, metadata=metadata, channel=channel)
        np.testing.assert_array_equal(saved.values, values)
        self.assertEqual(saved.channel_arrays.components, tuple(components))

    def test_writer_row_groups_keep_columnar_validation_and_bound_large_external_groups(self):
        count = 11000
        run = self.metadata.runs[0].model_copy(update={"sensor_groups": {
            "group": SensorGroup(clock_description="test",sample_count=count)}})
        metadata = self.metadata.model_copy(update={"runs": {0:run}})
        batches = list(ChannelSeries(channel=self.channel,values=np.zeros((count,2,3))).batches(
            SeriesSampling(frame_numbers=tuple(range(count)),timestamps_s=tuple(i/30 for i in range(count)),
                           run_id=0,batch_size=60000)))
        expected = pa.Table.from_batches(batches)
        pq.write_table(expected,self.structure.data_parquet_path,row_group_size=60000)
        with pq.ParquetFile(self.structure.data_parquet_path) as parquet:
            actual = list(recording_batches(parquet))
        self.assertEqual([batch.num_rows for batch in actual], [60000,6000])
        self.assertTrue(pa.Table.from_batches(actual).equals(expected))
        validator=SampleValidator(metadata=metadata)
        with patch.object(SampleValidator,"_accept_rows",side_effect=AssertionError("Unexpected scalar fallback")):
            for batch in actual:validator.accept(batch=batch)
            validator.finish()
        self.assertEqual(validator.columnar_rows,66000)
        self.assertEqual(validator.scalar_rows,0)
        # External files may have huge groups; preserving boundaries must not
        # remove the memory bound. Such batches retain the general validator path.
        pq.write_table(expected,self.structure.data_parquet_path,row_group_size=100000)
        with pq.ParquetFile(self.structure.data_parquet_path) as parquet:
            actual=list(recording_batches(parquet))
        self.assertTrue(all(batch.num_rows <= 65536 for batch in actual))
        self.assertTrue(pa.Table.from_batches(actual).equals(expected))
        validator=SampleValidator(metadata=metadata)
        for batch in actual:validator.accept(batch=batch)
        validator.finish()
        self.assertEqual(validator.columnar_rows+validator.scalar_rows,66000)
        self.assertGreater(validator.scalar_rows,0)
