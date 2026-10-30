import assert from 'node:assert/strict';
import {test} from 'node:test';
import {appendOverlay, type SkeletonObservation} from './skeleton-types';
import {SkeletonOverlayRenderer} from './skeleton-overlay-renderer';
import {OverlayLayer, type OverlayFrame} from '../../transport/frame-types';

const observation = (): SkeletonObservation => ({camera_id: 'camera', frame_number: 8, image_width: 100, image_height: 100,
    pointLayers: [], landmarkLayers: [], boxLayers: []});
const points = (layer: OverlayLayer, x = 10): OverlayFrame => ({cameraId: 'camera', frameNumber: 8, layer,
    names: ['left_wrist', 'right_wrist'], columns: ['visibility', 'y', 'x'], data: new Float32Array([1, 20, x, NaN, 40, 30])});

test('camera aggregation preserves multiple numerical layers and companion connections without scalar objects', () => {
    const value = observation(), first = points(OverlayLayer.DETECTIONS), second = points(OverlayLayer.DETECTIONS, 99);
    const landmarks = points(OverlayLayer.REPROJECTIONS), connections = [['left_wrist', 'right_wrist']] as const;
    appendOverlay(value, first); appendOverlay(value, second); appendOverlay(value, landmarks, connections);
    assert.equal(value.pointLayers.length, 2);
    assert.equal(value.pointLayers[0].data, first.data); assert.equal(value.pointLayers[1].data, second.data);
    assert.equal(value.landmarkLayers[0].connections, connections);
    const worker = structuredClone(value);
    assert.ok(worker.pointLayers[0].data instanceof Float32Array);
    assert.deepEqual(worker.landmarkLayers[0].values.data, landmarks.data);
    assert.equal(first.data.byteLength, 24, 'image transfer does not detach numerical overlay storage');
});

test('camera renderer reads declared columns, reuses prepared indices, and preserves box provenance', () => {
    const calls: {name: string; args: unknown[]; color: unknown}[] = [];
    const context = new Proxy({} as Record<string, unknown>, {get(target, name: string) {
        if (name in target) return target[name];
        return (...args: unknown[]) => calls.push({name, args, color: target.strokeStyle});
    }});
    const previous = Object.getOwnPropertyDescriptor(globalThis, 'OffscreenCanvas');
    Object.defineProperty(globalThis, 'OffscreenCanvas', {configurable: true, value: class {getContext() {return context;}}});
    try {
        const renderer = new SkeletonOverlayRenderer(), value = observation();
        appendOverlay(value, points(OverlayLayer.DETECTIONS));
        appendOverlay(value, points(OverlayLayer.REPROJECTIONS), [['left_wrist', 'right_wrist']]);
        appendOverlay(value, {cameraId: 'camera', frameNumber: 8, layer: OverlayLayer.BOXES, names: ['body', 'hand', 'missing'],
            columns: ['detector_ran', 'confidence', 'y2', 'x2', 'y1', 'x1'],
            data: new Float32Array([1, 0.75, 40, 30, 20, 10, 0, 0.5, 80, 70, 60, 50, 1, NaN, NaN, NaN, NaN, NaN])});
        renderer['drawSkeletonOverlay'](value);
        const arcs = calls.filter(call => call.name === 'arc');
        assert.deepEqual(arcs.slice(0, 4).map(call => call.args.slice(0, 2)), [[10, 20], [30, 40], [10, 20], [30, 40]]);
        assert.deepEqual(calls.find(call => call.name === 'moveTo')!.args, [10, 20]);
        assert.deepEqual(calls.find(call => call.name === 'lineTo')!.args, [30, 40]);
        assert.deepEqual(calls.filter(call => call.name === 'strokeRect').map(call => [call.args, call.color]),
            [[[10, 20, 20, 20], '#00FF00'], [[50, 60, 20, 20], '#FF8C00']]);
        const prepared = renderer['preparedLayers'][1];
        renderer['drawSkeletonOverlay'](structuredClone(value));
        assert.equal(renderer['preparedLayers'][1], prepared, 'worker-cloned unchanged labels reuse cached indices');
        const changed = structuredClone(value); changed.landmarkLayers[0].connections = [];
        renderer['drawSkeletonOverlay'](changed);
        assert.notEqual(renderer['preparedLayers'][1], prepared);
        changed.pointLayers[0].data = new Float32Array(5);
        assert.throws(() => renderer['drawSkeletonOverlay'](changed));
        assert.equal(calls.at(-1)!.name, 'restore', 'malformed data cannot leak saved canvas state');

        const shared: OverlayFrame = {cameraId: 'camera', frameNumber: 9, layer: OverlayLayer.DETECTIONS,
            names: ['body'], columns: ['x', 'y', 'visibility', 'x1', 'y1', 'x2', 'y2', 'confidence', 'detector_ran'],
            data: new Float32Array([2, 3, 1, 10, 20, 30, 40, 0.75, 1])};
        const detections = observation(); appendOverlay(detections, shared);
        renderer['drawSkeletonOverlay'](detections);
        const detectionLayout = renderer['preparedLayers'][0];
        const boxes = observation(); appendOverlay(boxes, {...shared, layer: OverlayLayer.BOXES});
        calls.length = 0;
        renderer['drawSkeletonOverlay'](boxes);
        assert.notEqual(renderer['preparedLayers'][0], detectionLayout, 'layer kind is part of the prepared layout identity');
        assert.deepEqual(calls.find(call => call.name === 'strokeRect')!.args, [10, 20, 20, 20]);
    } finally {
        if (previous) Object.defineProperty(globalThis, 'OffscreenCanvas', previous);
        else Reflect.deleteProperty(globalThis, 'OffscreenCanvas');
    }
});
