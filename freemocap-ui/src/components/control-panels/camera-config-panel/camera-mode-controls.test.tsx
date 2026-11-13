import assert from 'node:assert/strict';
import {test} from 'node:test';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {CaptureMode} from '@/store/slices/cameras/cameras-types';
import {CameraConfigResolution} from './CameraConfigResolution';
import {CameraConfigFramerate} from './CameraConfigFramerate';

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
const ELP_RESOLUTIONS = ['1920x1200', '1920x1080', '1600x1200', '1280x960', '1280x720', '640x480', '512x512'];
const noop = () => {};

interface RenderedOption {value: string; selected: boolean; disabled: boolean}

function selects(element: React.ReactElement): RenderedOption[][] {
    const html = renderToStaticMarkup(element);
    return [...html.matchAll(/<select[^>]*>([\s\S]*?)<\/select>/g)].map(([, body]) =>
        [...body.matchAll(/<option([^>]*)>/g)].map(([, attributes]) => ({
            value: attributes.match(/value="([^"]*)"/)?.[1] ?? '',
            selected: /\bselected=""/.test(attributes),
            disabled: /\bdisabled=""/.test(attributes),
        })));
}

const values = (options: RenderedOption[]) => options.map(option => option.value);
const selected = (options: RenderedOption[]) => options.filter(option => option.selected).map(option => option.value);

test('the resolution dropdown lists exactly the camera\'s reported resolutions', () => {
    const [options] = selects(<CameraConfigResolution resolution={{width: 1280, height: 960}}
                                                      supportedModes={ELP_MODES} onChange={noop}/>);
    assert.deepEqual(values(options), ELP_RESOLUTIONS);
    assert.deepEqual(selected(options), ['1280x960']);
    assert.ok(options.every(option => !option.disabled));
});

test('a resolution the camera does not report stays visible but cannot be chosen', () => {
    const [options] = selects(<CameraConfigResolution resolution={{width: 1280, height: 800}}
                                                      supportedModes={ELP_MODES} onChange={noop}/>);
    assert.deepEqual(values(options), [...ELP_RESOLUTIONS, '1280x800']);
    assert.deepEqual(options.at(-1), {value: '1280x800', selected: true, disabled: true});
});

test('the frame-rate dropdown lists the rates reported at the chosen resolution', () => {
    const [wide] = selects(<CameraConfigFramerate framerate={60} resolution={{width: 1920, height: 1200}}
                                                  supportedModes={ELP_MODES} onChange={noop}/>);
    assert.deepEqual(values(wide), ['10', '15', '20', '25', '30', '50', '60', '90', '100', '120']);
    assert.deepEqual(selected(wide), ['60']);
    const [hd] = selects(<CameraConfigFramerate framerate={200} resolution={{width: 1280, height: 720}}
                                                supportedModes={ELP_MODES} onChange={noop}/>);
    assert.deepEqual(values(hd), ['10', '15', '20', '25', '30', '50', '60', '90', '100', '120', '180', '200']);
    assert.deepEqual(selected(hd), ['200']);
});

test('a frame rate not offered at the chosen resolution stays visible but cannot be chosen', () => {
    const [unoffered] = selects(<CameraConfigFramerate framerate={200} resolution={{width: 1920, height: 1200}}
                                                       supportedModes={ELP_MODES} onChange={noop}/>);
    assert.deepEqual(unoffered.at(-1), {value: '200', selected: true, disabled: true});
    const [cameraDefault] = selects(<CameraConfigFramerate framerate={null} resolution={{width: 1920, height: 1200}}
                                                           supportedModes={ELP_MODES} onChange={noop}/>);
    assert.deepEqual(cameraDefault.at(-1), {value: '-1', selected: true, disabled: true});
    assert.equal(cameraDefault.filter(option => !option.disabled).length, RATES.length);
});

test('cameras without reported modes keep the preset resolutions and free frame-rate entry', () => {
    const [presets] = selects(<CameraConfigResolution resolution={{width: 1280, height: 720}}
                                                      supportedModes={[]} onChange={noop}/>);
    assert.deepEqual(values(presets), ['640x480', '1280x720', '1920x1080', 'custom']);
    const framerateHtml = renderToStaticMarkup(<CameraConfigFramerate framerate={30} resolution={{width: 1280, height: 720}}
                                                                      supportedModes={[]} onChange={noop}/>);
    assert.doesNotMatch(framerateHtml, /<select/);
    assert.match(framerateHtml, /<input[^>]*type="number"[^>]*value="30.00"/);
});
