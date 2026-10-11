"""Column construction preserves scalar storage semantics across bounded batches."""
import unittest
import numpy as np
import pyarrow as pa
from freemocap.core.recording.sample_encoding.channel_series import ChannelSeries, SeriesSampling
from freemocap.core.recording.sample_encoding.observation_samples import observation_batches, TimedObservation
from freemocap.core.recording.data_descriptors.recording_descriptor import Channel
from skellytracker.core.data_primitives.observation import Observation, StageObservation
from skellytracker.core.data_primitives.keypoints import Keypoints


class ColumnarSerializationTests(unittest.TestCase):
    def channel(self, **changes):
        return Channel(sensor_group="camera_group", source="tracker", reference_frame="image",
            kind="OVERLAY_2D", names=("body.a", "body.b"),
            components={"x": "px", "y": "px", "visibility": "1"}, stage="observations").model_copy(update=changes)

    def test_dense_series_matches_scalar_contract_for_strided_arrays_and_chunk_sizes(self):
        values = np.arange(36, dtype=np.float64).reshape(3, 2, 6)[:, :, ::2]
        values[1, 0, 0] = np.nan
        values[2, 1, 1] = -0.0
        channel = self.channel(reference_frame=None)
        for size in (1, 5, 6, 7, 65536):
            batches = list(ChannelSeries(channel=channel, values=values).batches(SeriesSampling(
                frame_numbers=(10, 12, 15), timestamps_s=(.1, .2, .3), run_id=2, batch_size=size)))
            self.assertTrue(all(batch.num_rows <= size for batch in batches))
            rows = pa.Table.from_batches(batches).to_pylist()
            expected = []
            for frame, timestamp, frame_values in zip((10, 12, 15), (.1, .2, .3), values):
                for name, point in zip(channel.names, frame_values):
                    for (component, units), value in zip(channel.components.items(), point):
                        expected.append(dict(timestamp_s=timestamp, sensor_group="camera_group", frame_number=frame,
                            source="tracker", reference_frame=None, channel="OVERLAY_2D", name=name,
                            component=component, value=None if np.isnan(value) else float(value), units=units, run_id=2))
            self.assertEqual(rows, expected)
            self.assertTrue(np.signbit(rows[-2]["value"]))

    def observations(self):
        for frame in range(4):
            yield TimedObservation(observation=Observation(frame_number=frame, image_size=(480,640),
                stages={"body": StageObservation(name="body", keypoints=Keypoints(names=("b",),
                    xyz=np.array([[frame + .5, np.nan, 0.]]), visibility=np.array([.75])))}) if frame != 2
                else Observation(frame_number=frame,image_size=(480,640)), capture_timestamp_s=frame / 30)

    def test_sparse_observations_preserve_nulls_visibility_and_previously_yielded_batches(self):
        for size in (1, 5, 12, 65536):
            batches = list(observation_batches(samples=self.observations(), channel=self.channel(), run_id=0, batch_size=size))
            self.assertTrue(all(batch.num_rows <= size for batch in batches))
            rows = pa.Table.from_batches(batches).to_pylist()
            self.assertEqual([r["value"] for r in rows],
                [None,None,0.,.5,None,.75, None,None,0.,1.5,None,.75,
                 None,None,0.,None,None,0., None,None,0.,3.5,None,.75])
            self.assertEqual([r["frame_number"] for r in rows], [n for n in range(4) for _ in range(6)])

    def test_observation_component_order_is_declared_not_assumed(self):
        channel=self.channel(components={"visibility":"1","y":"px","x":"px"})
        batches=list(observation_batches(samples=self.observations(),channel=channel,run_id=0,batch_size=12))
        rows=pa.Table.from_batches(batches).to_pylist()
        self.assertEqual([row["component"] for row in rows[:6]], ["visibility","y","x"] * 2)
        self.assertEqual([row["value"] for row in rows[:6]], [0.,None,None,.75,None,.5])

    def test_invalid_observation_values_and_order_still_rejected(self):
        for value, visibility in ((float("inf"), .5), (1., float("nan")), (1., 1.1)):
            sample = TimedObservation(observation=Observation(frame_number=0,image_size=(480,640),
                stages={"body":StageObservation(name="body",keypoints=Keypoints(names=("a",),
                    xyz=np.array([[value,0.,0.]]),visibility=np.array([visibility]))) }),capture_timestamp_s=0.)
            with self.assertRaises(ValueError):
                list(observation_batches(samples=[sample],channel=self.channel(),run_id=0,batch_size=100))
        sample = next(self.observations())
        with self.assertRaises(ValueError):
            list(observation_batches(samples=[sample,sample],channel=self.channel(),run_id=0,batch_size=100))


class ColumnarValidationTests(unittest.TestCase):
    def setUp(self):
        from freemocap.core.recording.data_descriptors.recording_descriptor import RecordingMetadata, RunDescriptor, SensorGroup, Source
        self.channel = Channel(sensor_group="group",source="tracker",reference_frame="world",kind="ROTATIONS_WORLD",
            names=("root", "child"),components={"w":"1","x":"1","y":"1","z":"1"},stage="reconstruction")
        self.metadata = RecordingMetadata(recording_id="test",selected_run_id=0,runs={0:RunDescriptor(
            sensor_groups={"group":SensorGroup(clock_description="test",sample_count=3)},
            sources={"tracker":Source(kind="tracker",definition={})},reference_frames={"world":{}},
            models={},processing={},channels=(self.channel,))})
        values=np.zeros((3,2,4));values[:,:,0]=1.;values[1,1,:]=np.nan
        self.batch=list(ChannelSeries(channel=self.channel,values=values).batches(SeriesSampling(
            frame_numbers=(1,3,8),timestamps_s=(-0.,.3,.8),run_id=0)))[0]

    def validate(self, batches, scalar=False):
        from freemocap.core.recording.sample_encoding.arrow_schema import SampleValidator
        validator=SampleValidator(metadata=self.metadata)
        for batch in batches:
            if scalar:validator._accept_rows(batch)
            else:validator.accept(batch=batch)
        validator.finish()
        return validator

    def test_fast_and_scalar_validation_preserve_exact_state_across_chunk_boundaries(self):
        from freemocap.core.recording.sample_encoding.arrow_schema import SampleValidator
        self.assertTrue(SampleValidator(metadata=self.metadata)._accept_rectangular_batch(self.batch))
        for size in (1,3,8,16,24):
            batches=[self.batch.slice(start,min(size,self.batch.num_rows-start)) for start in range(0,self.batch.num_rows,size)]
            fast=self.validate(batches);scalar=self.validate(batches,scalar=True)
            self.assertEqual(fast.counts,scalar.counts)
            self.assertEqual(fast.last_samples,scalar.last_samples)
            self.assertEqual(fast.timing_digests,scalar.timing_digests)
            self.assertEqual(fast.pending_rotations,scalar.pending_rotations)

    def test_malformed_scientific_samples_rejected_by_both_paths(self):
        mutations=[("value",0,.5),("value",0,None),("value",0,float("inf")),("value",0,float("nan")),
            ("timestamp_s",1,0.0),("timestamp_s",9,.31),("timestamp_s",0,float("nan")),("frame_number",9,1),
            ("frame_number",0,-1),("name",0,"unknown"),("component",0,"bad"),("units",0,"mm"),
            ("source",0,"unknown"),("run_id",0,1)]
        for column,index,value in mutations:
            rows=self.batch.to_pylist();rows[index][column]=value
            bad=pa.RecordBatch.from_pylist(rows,schema=self.batch.schema)
            for scalar in (False,True):
                with self.subTest(column=column,value=value,scalar=scalar),self.assertRaises(ValueError):
                    self.validate([bad],scalar=scalar)
        for scalar in (False,True):
            with self.assertRaises(ValueError):self.validate([self.batch,self.batch],scalar=scalar)
            with self.assertRaises(ValueError):self.validate([self.batch.slice(0,23)],scalar=scalar)
