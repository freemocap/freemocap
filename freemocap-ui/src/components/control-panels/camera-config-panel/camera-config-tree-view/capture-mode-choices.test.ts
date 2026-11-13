import assert from 'node:assert/strict';
import {test} from 'node:test';
import {CameraConfig, CaptureMode, createDefaultCameraConfig} from '@/store/slices/cameras/cameras-types';
import {captureModeChoices} from './capture-mode-choices';

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

const sizes = (choices: {width: number; height: number}[]) => choices.map(choice => [choice.width, choice.height]);

test('the modal offers the camera\'s reported resolutions and the rates at the chosen one', () => {
    const wide = captureModeChoices(config(1920, 1200, 60), ELP_MODES);
    assert.deepEqual(sizes(wide.resolutions),
        [[1920, 1200], [1920, 1080], [1600, 1200], [1280, 960], [1280, 720], [640, 480], [512, 512]]);
    assert.deepEqual(wide.framerates?.map(choice => choice.framerate), RATES);
    assert.deepEqual(captureModeChoices(config(1280, 720, 30), ELP_MODES).framerates?.map(choice => choice.framerate),
        [...RATES, 180, 200]);
});

test('choice labels identify one choice each, so selecting a label picks that choice', () => {
    const choices = captureModeChoices(config(1280, 720, 30), ELP_MODES);
    for (const options of [choices.resolutions, choices.framerates ?? []]) {
        assert.equal(new Set(options.map(choice => choice.label)).size, options.length);
    }
});

test('cameras without reported modes keep the preset resolutions and no frame-rate row', () => {
    const choices = captureModeChoices(config(1280, 720, 30), []);
    assert.deepEqual(sizes(choices.resolutions), [[640, 480], [1280, 720], [1920, 1080]]);
    assert.equal(choices.framerates, null);
});
