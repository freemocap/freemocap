import assert from 'node:assert/strict';
import {test} from 'node:test';
import {recordingTimeForMedia, mediaFrameAtRecordingTime} from './playback-timing';
import {sampleAtTime, type PlaybackMedia} from './playback-data';

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

test('video time maps nonzero source frames into recording time before selecting 120 Hz samples', () => {
    const time = recordingTimeForMedia([camera], {filename: camera.video_filename, time_s: 5.5 / 30});
    assert.equal(time, 1.02);
    assert.equal(sampleAtTime([1, 1 + 1 / 120, 1 + 2 / 120, 1 + 3 / 120], time!), 2);
    assert.equal(recordingTimeForMedia([camera], {filename: camera.video_filename, time_s: 4 / 30}), null);
    assert.equal(recordingTimeForMedia([camera], {filename: camera.video_filename, time_s: 8 / 30}), null);
    assert.equal(recordingTimeForMedia([camera], {filename: camera.video_filename, time_s: 7 / 30}), 1.09);
});

test('video binding selects its own camera clock regardless of declaration order', () => {
    const eye: PlaybackMedia = {video_filename: 'eye.mp4', nominal_fps: 120,
        timeline: {sensor_group: 'eye', source: 'camera:eye', frame_numbers: [0, 1, 2], timestamps_s: [2, 2 + 1 / 120, 2 + 2 / 120]}};
    assert.equal(recordingTimeForMedia([camera, eye], {filename: eye.video_filename, time_s: 1 / 120}), 2 + 1 / 120);
    assert.equal(recordingTimeForMedia([eye, camera], {filename: camera.video_filename, time_s: 6 / 30}), 1.04);
    assert.throws(() => recordingTimeForMedia([camera], {filename: 'unknown.mp4', time_s: 0}), /timing binding/);
    assert.throws(() => recordingTimeForMedia([camera, camera], {filename: camera.video_filename, time_s: 0}), /timing binding/);
});
