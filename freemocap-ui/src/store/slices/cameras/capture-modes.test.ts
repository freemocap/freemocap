import assert from 'node:assert/strict';
import {test} from 'node:test';
import {CameraConfig, CaptureMode, createDefaultCameraConfig} from './cameras-types';
import {framerateOptionsFor, withResolution} from './capture-modes';

// MJPEG modes reported by the attached ELP AR0234 global-shutter cameras.
const RATES = [10, 15, 20, 25, 30, 50, 60, 90, 100, 120];
const ELP_MODES: CaptureMode[] = [
    {width: 1920, height: 1200, framerates: RATES},
    {width: 1920, height: 1080, framerates: RATES},
    {width: 1600, height: 1200, framerates: RATES},
    {width: 1280, height: 960, framerates: RATES},
    {width: 1280, height: 720, framerates: [...RATES, 180, 200]},
    {width: 640, height: 480, framerates: [...RATES, 180, 200]},
    {width: 512, height: 512, framerates: RATES},
];

function config(width: number, height: number, framerate: number): CameraConfig {
    return {...createDefaultCameraConfig('camera-A', 0, 'Global Shutter Camera'), resolution: {width, height}, framerate};
}

test('frame-rate options are the rates the camera reports at the chosen resolution', () => {
    assert.deepEqual(framerateOptionsFor(ELP_MODES, {width: 1280, height: 720}),
        [10, 15, 20, 25, 30, 50, 60, 90, 100, 120, 180, 200]);
    assert.deepEqual(framerateOptionsFor(ELP_MODES, {width: 1920, height: 1200}),
        [10, 15, 20, 25, 30, 50, 60, 90, 100, 120]);
    assert.deepEqual(framerateOptionsFor(ELP_MODES, {width: 1280, height: 800}), []);
});

test('changing resolution keeps a frame rate the new resolution offers', () => {
    assert.deepEqual(withResolution(config(640, 480, 60), ELP_MODES, 1920, 1200),
        {resolution: {width: 1920, height: 1200}, framerate: 60});
});

test('changing resolution replaces an unavailable frame rate with the closest offered one', () => {
    assert.deepEqual(withResolution(config(1280, 720, 200), ELP_MODES, 1920, 1200),
        {resolution: {width: 1920, height: 1200}, framerate: 120});
});

test('a frame rate midway between two offered rates becomes the lower one', () => {
    const modes: CaptureMode[] = [{width: 800, height: 600, framerates: [30, 50]}];
    assert.equal(withResolution(config(640, 480, 40), modes, 800, 600).framerate, 30);
});

test('the camera default rate and cameras without reported modes keep their frame rate', () => {
    assert.equal(withResolution(config(1280, 720, -1), ELP_MODES, 1920, 1200).framerate, -1);
    assert.deepEqual(withResolution(config(1280, 720, 200), [], 1920, 1080),
        {resolution: {width: 1920, height: 1080}, framerate: 200});
});
