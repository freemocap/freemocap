import assert from 'node:assert/strict';
import {test} from 'node:test';
import {mediaFrameAtRecordingTime} from './playback-timing';
import {type PlaybackMedia} from './playback-data';

const camera: PlaybackMedia = {
    video_filename: 'camera.mp4', nominal_fps: 30,
    timeline: {sensor_group: 'mocap', source: 'camera:a', frame_numbers: [5, 6, 7], timestamps_s: [1, 1.04, 1.09]},
};

test('follower seeking selects native frames with offsets and independent rates', () => {
    const eye: PlaybackMedia = {video_filename: 'eye.mp4', nominal_fps: 120,
        timeline: {sensor_group: 'eye', source: 'eye', frame_numbers: [10, 11, 12, 13],
            timestamps_s: [1, 1 + 1 / 120, 1 + 2 / 120, 1 + 3 / 120]}};
    assert.equal(mediaFrameAtRecordingTime(camera, 1.02), 5);
    assert.equal(mediaFrameAtRecordingTime(eye, 1.02), 12);
    assert.equal(mediaFrameAtRecordingTime(camera, 0.9), null);
    assert.equal(mediaFrameAtRecordingTime(camera, 1.1), null);
    assert.equal(mediaFrameAtRecordingTime(camera, 1.09), 7);
});

test('every declared capture timestamp selects its exact native frame', () => {
    const binding: PlaybackMedia = {...camera, nominal_fps: 29.97,
        timeline: {...camera.timeline, frame_numbers: Array.from({length: 500}, (_, index) => index + 100),
            timestamps_s: Array.from({length: 500}, (_, index) => 0.001 + index / 29.97)}};
    binding.timeline.timestamps_s.forEach((time, index) => {
        assert.equal(mediaFrameAtRecordingTime(binding, time), binding.timeline.frame_numbers[index]);
    });
});

test('invalid sample grids and invalid recording times fail explicitly', () => {
    assert.throws(() => mediaFrameAtRecordingTime(camera, NaN), /sample grid/);
    assert.throws(() => mediaFrameAtRecordingTime({...camera, timeline: {...camera.timeline, frame_numbers: []}}, 1), /sample grid/);
});
