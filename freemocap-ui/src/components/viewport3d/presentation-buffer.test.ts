import assert from 'node:assert/strict';
import {test} from 'node:test';
import {PresentationBuffer} from './presentation-buffer';
import {workerDataStore} from './WorkerDataStore';
import type {ResolvedModelFrame} from '@/services/server/transport/frame-types';

test('missing observations expire without another incoming frame and fresh observations renew them', t => {
    t.mock.timers.enable({apis: ['setTimeout']});
    let now = 0;
    t.mock.method(performance, 'now', () => now);
    let visible: number[] = [];
    const buffer = new PresentationBuffer<number>(values => {visible = values;}, 1000);
    buffer.update([1, 2], String, Number.isFinite);
    now = 500;
    buffer.update([2], String, Number.isFinite);
    assert.deepEqual(visible, [1, 2]);
    now = 1000;
    t.mock.timers.tick(500);
    assert.deepEqual(visible, [2]);
    now = 1500;
    t.mock.timers.tick(500);
    assert.deepEqual(visible, []);
    buffer.update([3], String, Number.isFinite);
    buffer.clear();
    assert.deepEqual(visible, []);
});

test('a complete missing frame clears the previous model immediately, without extending backend retention', () => {
    const model = {modelId: 'subject', instanceId: 0} as ResolvedModelFrame;
    workerDataStore.dispatch('livePresentation', true);
    workerDataStore.dispatch('modelFrames', [model]);
    assert.equal(workerDataStore.getLatestModelFrames()?.length, 1);
    workerDataStore.dispatch('modelFrames', []);
    assert.deepEqual(workerDataStore.getLatestModelFrames(), []);
    const points = {pointNames: ['wrist'], interleaved: new Float32Array([1, 2, 3])};
    workerDataStore.dispatch('keypoints', points);
    const missing = {pointNames: ['wrist'], interleaved: new Float32Array([NaN, NaN, NaN])};
    workerDataStore.dispatch('keypoints', missing);
    assert.equal(workerDataStore.getLatestKeypoints(), missing);
    workerDataStore.dispatch('presentationReset', null);
});
