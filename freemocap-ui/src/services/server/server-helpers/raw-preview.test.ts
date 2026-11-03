import assert from 'node:assert/strict';
import {test} from 'node:test';
import {OverlayManager} from './image-overlay/overlay-renderer-factory';
import type {SkeletonObservation} from './image-overlay/skeleton-types';
import {encode} from 'cbor-x';
import {TransportService} from '../transport/TransportService';
import {CURRENT_VERSION, FrameMessageSchema, type FrameMessage} from '../transport/message-contract';
import {workerDataStore} from '@/components/viewport3d/WorkerDataStore';

test('self-contained raw frame delivers image and clears processed geometry without any apply state', () => {
    const service = new TransportService({url: 'ws://unused.invalid'});
    const source = FrameMessageSchema.parse({kind: 'frame', version: CURRENT_VERSION, timestamp: 1, sequence: 1,
        frame_number: 1, model_sequence: 0, convention: {units: 'mm', handedness: 'right', up_axis: '+Z', forward_axis: '+Y', rotation_frame: 'world', rotation_form: 'quaternion_wxyz'},
        cameras: [], models: [{model_id: 'subject', segments: [], landmarks: [{name: 'wrist'}], connections: []}],
        instances: [{instance_id: 0, model_id: 'subject', fitted_scale_mm: null, channels: [{kind: 'LANDMARKS_3D', columns: ['x', 'y', 'z'], data: new Uint8Array(Float32Array.from([1, 2, 3]).buffer)}]}],
        trackers: [], image: new Uint8Array([1, 2, 3])});
    const images: number[] = [], failures: unknown[] = [];
    service.subscribeToProtocolErrors(error => failures.push(error));
    service.subscribeToModelFrames(models => workerDataStore.dispatch('modelFrames', models));
    service.subscribeToKeypoints(points => workerDataStore.dispatch('keypoints', {pointNames: points.names, pointSources: points.sources}));
    service.subscribeToImages((_, number) => images.push(number));
    const dispatch = (frame: FrameMessage) => {const bytes = encode(frame); service['dispatchBytes'](bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength) as ArrayBuffer);};
    workerDataStore.dispatch('livePresentation', true);
    try {
        dispatch(source);
        assert.equal(workerDataStore.getLatestModelFrames()?.length, 1);
        dispatch({...source, frame_number: 2, sequence: 2, models: [], instances: [], trackers: []});
        assert.deepEqual(failures, []); assert.deepEqual(images, [1, 2]);
        assert.deepEqual(workerDataStore.getLatestModelFrames(), []);
        assert.deepEqual(workerDataStore.getLatestKeypoints()?.pointNames, []);
    } finally {workerDataStore.dispatch('presentationReset', null);}
});

test('raw camera frame clears prior detections in the real camera worker', async () => {
    const names = ['self', 'OffscreenCanvas', 'ImageData', 'createImageBitmap', 'requestAnimationFrame'] as const;
    const originals = names.map(name => Object.getOwnPropertyDescriptor(globalThis, name));
    let receive: (event: {data: unknown}) => void = () => {};
    let render: (() => void) | null = null;
    let composites = 0;
    const shown: unknown[] = [];
    const raw = {width: 1, height: 1, close() {}} as ImageBitmap;
    const composite = {...raw} as ImageBitmap;
    const originalProcess = OverlayManager.prototype.processFrame;
    const values = {
        self: {addEventListener: (_: string, callback: typeof receive) => {receive = callback;}, postMessage() {}},
        OffscreenCanvas: class {getContext() {return {}; }},
        ImageData: class {}, createImageBitmap: async () => raw,
        requestAnimationFrame: (callback: () => void) => {render = callback; return 1;},
    };
    for (const name of names) Object.defineProperty(globalThis, name, {configurable: true, value: values[name]});
    OverlayManager.prototype.processFrame = async () => {composites++; return composite;};
    try {
        await import('./offscreen-renderer.worker');
        receive({data: {type: 'init', canvas: {getContext: () => ({transferFromImageBitmap: (bitmap: unknown) => shown.push(bitmap)})}}});
        const send = async (skeleton: SkeletonObservation | null) => {
            receive({data: {type: 'frame', pixelBuffer: new ArrayBuffer(4), width: 1, height: 1, skeleton}});
            for (let step = 0; step < 5; step++) await Promise.resolve();
            const callback = render; render = null; callback?.();
        };
        await send({camera_id: 'camera', frame_number: 1, image_width: 1, image_height: 1, pointLayers: [], landmarkLayers: [], boxLayers: []});
        assert.equal(composites, 1); assert.equal(shown.at(-1), composite);
        await send(null);
        assert.equal(composites, 1, 'raw frame does not reapply old detections');
        assert.equal(shown.at(-1), raw, 'raw preview replaces composited camera image');
    } finally {
        OverlayManager.prototype.processFrame = originalProcess;
        names.forEach((name, index) => {const original = originals[index]; if (original) Object.defineProperty(globalThis, name, original); else Reflect.deleteProperty(globalThis, name);});
    }
});
