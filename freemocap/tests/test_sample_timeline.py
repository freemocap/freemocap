"""Actual sample IDs and times survive shared timeline admission and slicing."""

from dataclasses import FrozenInstanceError
import gc
import unittest
from unittest.mock import patch

import numpy as np
from beartype.roar import BeartypeCallHintParamViolation

from freemocap.core.data_tensors import SampleTimeline, SourceIdentity


class SampleTimelineTests(unittest.TestCase):
    def timeline(self, sample_ids=(10, 12, 19), timestamps_s=(0.0, 0.2, 0.9), **changes):
        arguments = dict(timeline_id="recording:camera_a:capture", clock_id="recording_clock",
                         source_identity=SourceIdentity("camera_a", camera_id="camera_a"),
                         sample_ids=sample_ids, timestamps_s=timestamps_s)
        arguments.update(changes)
        return SampleTimeline(**arguments)

    def test_preserves_sample_ids_and_timestamps_without_resampling(self):
        timeline = self.timeline()
        np.testing.assert_array_equal(timeline.sample_ids, [10, 12, 19])
        np.testing.assert_array_equal(timeline.timestamps_s, [0., .2, .9])
        self.assertEqual(timeline.sample_ids.dtype, np.dtype("int64"))
        self.assertEqual(timeline.timestamps_s.dtype, np.dtype("float64"))
        self.assertEqual(timeline.sample_count, 3)
        self.assertEqual(timeline.sample_axis.identifiers, (10, 12, 19))
        self.assertIs(timeline.sample_axis, timeline.sample_axis)

    def test_published_timing_cannot_be_changed_through_input_aliases(self):
        sample_ids = np.array([10, 12, 19], dtype=np.int64)
        timestamps = np.array([0., .2, .9], dtype=np.float64)
        timeline = self.timeline(sample_ids, timestamps)
        sample_ids[0] = 99
        timestamps[0] = 99.
        self.assertEqual(timeline.sample_ids[0], 10)
        self.assertEqual(timeline.timestamps_s[0], 0.)
        for array in (timeline.sample_ids, timeline.timestamps_s):
            with self.assertRaises(ValueError):
                array.flags.writeable = True
        with self.assertRaises(FrozenInstanceError):
            timeline.clock_id = "other_clock"

    def test_slice_shares_memory_and_preserves_identity_without_validation(self):
        timeline = self.timeline()
        original_axis = timeline.sample_axis
        with patch.object(SampleTimeline, "__post_init__", side_effect=AssertionError("revalidated")):
            selected = timeline.slice_samples(1, 3)
        self.assertTrue(np.shares_memory(selected.sample_ids, timeline.sample_ids))
        self.assertTrue(np.shares_memory(selected.timestamps_s, timeline.timestamps_s))
        np.testing.assert_array_equal(selected.sample_ids, [12, 19])
        np.testing.assert_array_equal(selected.timestamps_s, [.2, .9])
        self.assertEqual(selected.sample_axis.identifiers, original_axis.identifiers[1:3])
        self.assertIs(selected.source_identity, timeline.source_identity)
        self.assertEqual(selected.timeline_id, timeline.timeline_id)
        self.assertEqual(selected.clock_id, timeline.clock_id)
        self.assertEqual(selected.clock_epoch, timeline.clock_epoch)

    def test_slice_keeps_storage_alive_after_parent_is_released(self):
        timeline = self.timeline()
        selected = timeline.slice_samples(-2)
        del timeline
        gc.collect()
        np.testing.assert_array_equal(selected.sample_ids, [12, 19])
        np.testing.assert_array_equal(selected.timestamps_s, [.2, .9])
        with self.assertRaises(ValueError):
            selected.timestamps_s.flags.writeable = True

    def test_empty_timeline_and_empty_slice_are_valid(self):
        timeline = self.timeline((), ())
        self.assertEqual(timeline.sample_count, 0)
        self.assertEqual(timeline.sample_axis.identifiers, ())
        self.assertEqual(self.timeline().slice_samples(2, 1).sample_count, 0)

    def test_invalid_sample_identifiers_are_rejected(self):
        for sample_ids in ((10, 10, 19), (10, 9, 19), (-1, 1, 2), (1., 2., 3.),
                           (True, False, True), np.array([0, 1, 2**63], dtype=np.uint64)):
            with self.subTest(sample_ids=sample_ids):
                with self.assertRaises((ValueError, BeartypeCallHintParamViolation)):
                    self.timeline(sample_ids=sample_ids)

    def test_invalid_timestamps_and_lengths_are_rejected(self):
        for timestamps in ((0., 0., 1.), (0., -1., 1.), (0., np.nan, 1.),
                           (0., np.inf, 1.), (0., 1.), ((0., .2, .9),)):
            with self.subTest(timestamps=timestamps):
                with self.assertRaises((ValueError, BeartypeCallHintParamViolation)):
                    self.timeline(timestamps_s=timestamps)

    def test_times_from_separate_sources_remain_independent(self):
        camera = self.timeline()
        sensor = self.timeline((4, 5, 6, 7), (0., .005, .010, .015),
                               timeline_id="recording:imu", clock_id="imu_clock",
                               source_identity=SourceIdentity("imu"))
        self.assertNotEqual(camera.clock_id, sensor.clock_id)
        self.assertEqual(camera.sample_count, 3)
        self.assertEqual(sensor.sample_count, 4)
        np.testing.assert_array_equal(sensor.timestamps_s, [0., .005, .010, .015])

    def test_new_epoch_is_explicit_and_negative_times_are_not_shifted(self):
        timeline = self.timeline((0, 1), (-0.5, -0.25), clock_epoch=1)
        self.assertEqual(timeline.clock_epoch, 1)
        np.testing.assert_array_equal(timeline.timestamps_s, [-.5, -.25])
        for changes in ({"clock_id": ""}, {"timeline_id": " "}, {"clock_epoch": -1}, {"clock_epoch": True}):
            with self.subTest(changes=changes):
                with self.assertRaises((ValueError, BeartypeCallHintParamViolation)):
                    self.timeline(**changes)

    def test_sample_slice_rejects_boolean_bounds(self):
        with self.assertRaises(TypeError):
            self.timeline().slice_samples(True)
