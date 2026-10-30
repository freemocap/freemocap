import assert from 'node:assert/strict';
import {test} from 'node:test';
import {ViewportFrameReceiver, ViewportFrameSender} from './viewport-frame-transfer';
import {prepareFrameLayout, readFrameBuffer, referencedFrameBuffers, writeFrameBuffer} from './viewport-frame-codec';
import {workerDataStore} from './WorkerDataStore';
import type {ResolvedModelFrame} from '@/services/server/transport/frame-types';

const modelFrame = (instanceId: number, value: number): ResolvedModelFrame => ({
    modelId: 'subject', instanceId, fittedScaleMm: 123.123456789,
    mappedKeypoints: {names: ['point'], data: new Float32Array([value, value, value])},
    landmarks: null, segmentOrigins: null, segmentLengths: {names: ['bone'], data: new Float32Array([42]), fittedScaleMm: 98.7654321},
    rotations: {boneNames: ['bone'], worldQuaternions: new Float32Array([1, 0, 0, 0]), localQuaternions: new Float32Array()},
    derived: {centerOfMass: [1.123456789, 2, 3], xcom: null},
});

function harness() {
    const toWorker: any[] = [], toMain: any[] = [], sent: any[] = [];
    workerDataStore.dispatch('livePresentation', false);
    const sender = new ViewportFrameSender((message, transfer = []) => {
        const cloned = structuredClone(message, {transfer}) as any; toWorker.push(cloned);
        if (cloned.type === 'viewportFrame') sent.push(cloned);
    });
    const receiver = new ViewportFrameReceiver(
        (message, transfer = []) => toMain.push(structuredClone(message, {transfer})),
        (stream, frame) => workerDataStore.dispatch(stream, frame),
        () => referencedFrameBuffers(workerDataStore.getLatestKeypoints(), workerDataStore.getLatestModelFrames()),
        () => workerDataStore.dispatch('frameReset', null),
    );
    const unsubscribePoints = workerDataStore.subscribeToKeypoints(() => receiver.scheduleRelease());
    const unsubscribeModels = workerDataStore.subscribeToModelFrames(() => receiver.scheduleRelease());
    const worker = async () => {while (toWorker.length) receiver.receive(toWorker.shift()); await Promise.resolve();};
    const main = () => {while (toMain.length) sender.receive(toMain.shift());};
    const drain = async () => {
        let attempts = 0;
        do {await worker(); main(); assert.ok(++attempts < 50, 'transport must settle');} while (toWorker.length || toMain.length);
    };
    const close = async () => {sender.dispose(); await drain(); unsubscribePoints(); unsubscribeModels(); workerDataStore.dispatch('livePresentation', false);};
    return {sender, receiver, toWorker, toMain, sent, worker, main, drain, close};
}

test('frame transfer copies only view bytes, preserves source ownership and reuses layout metadata', async () => {
    const h = harness();
    try {
        const recording = new Float32Array(100_000).fill(99);
        recording.set([1, 2, 3, 4, 5, 6], 30);
        const names = ['left', 'right'];
        const frame = {pointNames: names, interleaved: recording.subarray(30, 36)};
        h.sender.sendKeypoints(frame);
        assert.equal(h.sent[0].buffer.byteLength, 24);
        assert.equal(recording.byteLength, 400_000);
        await h.drain();
        const first = workerDataStore.getLatestKeypoints()!;
        assert.deepEqual(Array.from(first.interleaved), [1, 2, 3, 4, 5, 6]);
        h.sender.sendKeypoints({pointNames: names, interleaved: new Float32Array([7, 8, 9, 10, 11, 12])});
        assert.equal(h.sent[1].layout, undefined);
        await h.drain();
        assert.equal(first.interleaved.buffer.byteLength, 0, 'released worker presentation can now be recycled');
        assert.equal(recording.byteLength, 400_000, 'recording buffer never transfers');
        assert.deepEqual(Array.from(recording.subarray(30, 36)), [1, 2, 3, 4, 5, 6]);
        h.sender.sendKeypoints({pointNames: ['right', 'left'], interleaved: frame.interleaved});
        assert.ok(h.sent[2].layout);
        await h.drain();
        assert.deepEqual(workerDataStore.getLatestKeypoints()!.pointNames, ['right', 'left']);
    } finally {await h.close();}
});

test('delayed receipt coalesces latest frame and replacement does not wait for current buffer return', async () => {
    const h = harness();
    try {
        for (let value = 0; value < 100; value++) h.sender.sendKeypoints({pointNames: ['point'], interleaved: new Float32Array([value, 2, 3])});
        assert.equal(h.sent.length, 1);
        await h.worker();
        assert.equal(workerDataStore.getLatestKeypoints()!.interleaved[0], 0);
        assert.equal(h.toMain.filter(message => message.type === 'viewportBufferReturned').length, 0);
        h.main();
        assert.equal(h.sent.length, 2, 'receipt permits a replacement while previous presentation is held');
        await h.drain();
        assert.equal(workerDataStore.getLatestKeypoints()!.interleaved[0], 99);
        for (let value = 100; value < 120; value++) {
            h.sender.sendKeypoints({pointNames: ['point'], interleaved: new Float32Array([value, 2, 3])});
            await h.drain();
        }
        assert.equal(h.toWorker.length, 0);
        assert.equal(h.toMain.length, 0);
        assert.equal(workerDataStore.getLatestKeypoints()!.interleaved[0], 119);
    } finally {await h.close();}
});

test('live retention protects different model packets and releases them on timed expiry without input', async t => {
    t.mock.timers.enable({apis: ['setTimeout']});
    let now = 0;
    t.mock.method(performance, 'now', () => now);
    const h = harness();
    try {
        await h.drain();
        workerDataStore.dispatch('livePresentation', true);
        h.sender.sendModels([modelFrame(0, 1), modelFrame(1, 2)]); await h.drain();
        const firstBuffer = workerDataStore.getLatestModelFrames()![1].mappedKeypoints!.data.buffer;
        h.sender.sendModels([modelFrame(0, 3), modelFrame(1, NaN)]); await h.drain();
        let frames = workerDataStore.getLatestModelFrames()!;
        assert.deepEqual(frames.map(frame => frame.mappedKeypoints!.data[0]), [3, 2]);
        assert.ok(firstBuffer.byteLength > 0);
        const secondBuffer = frames[0].mappedKeypoints!.data.buffer;
        h.sender.sendModels([modelFrame(0, NaN), modelFrame(1, 4)]); await h.drain();
        frames = workerDataStore.getLatestModelFrames()!;
        assert.deepEqual(frames.map(frame => frame.mappedKeypoints!.data[0]), [3, 4]);
        assert.equal(firstBuffer.byteLength, 0);
        const thirdBuffer = frames[1].mappedKeypoints!.data.buffer;
        h.sender.sendModels([modelFrame(0, NaN), modelFrame(1, NaN)]); await h.drain();
        assert.ok(secondBuffer.byteLength > 0); assert.ok(thirdBuffer.byteLength > 0);
        now = 1001; t.mock.timers.tick(1001); await h.drain();
        assert.deepEqual(workerDataStore.getLatestModelFrames(), []);
        assert.equal(secondBuffer.byteLength, 0); assert.equal(thirdBuffer.byteLength, 0);
    } finally {await h.close();}
});

test('session reset drops pending delivery, preserves static models and ignores stale packets', async () => {
    const h = harness();
    try {
        await h.drain();
        const definitions = [{model_id: 'static-model'}];
        workerDataStore.dispatch('models', definitions);
        h.sender.sendKeypoints({pointNames: ['point'], interleaved: new Float32Array([1, 2, 3])});
        const stale = h.toWorker.shift();
        h.receiver.receive({type: 'viewportFrameStart', sessionId: 'next-session'});
        h.receiver.receive(stale);
        assert.equal(workerDataStore.getLatestKeypoints()!.interleaved.length, 0);
        assert.equal(workerDataStore.getModels(), definitions);
        h.sender.sendKeypoints({pointNames: ['point'], interleaved: new Float32Array([9, 8, 7])});
        h.sender.dispose();
        await h.drain();
        assert.equal(h.sent.length, 1, 'pending frame was discarded on dispose');
        assert.equal(workerDataStore.getLatestKeypoints()!.interleaved.length, 0);
    } finally {h.receiver.reset(); await h.close();}
});

test('model codec preserves double precision scalars, optional channels and either quaternion side', () => {
    for (const side of ['world', 'local'] as const) {
        const source = modelFrame(7, 4);
        if (side === 'local') source.rotations = {boneNames: ['bone'], worldQuaternions: new Float32Array(), localQuaternions: new Float32Array([0, 1, 0, 0])};
        const layout = prepareFrameLayout('modelFrames', [source]);
        const buffer = new ArrayBuffer(layout.byteLength);
        writeFrameBuffer(buffer, layout, 'modelFrames', [source]);
        const [actual] = readFrameBuffer(buffer, layout, 'modelFrames') as ResolvedModelFrame[];
        assert.deepEqual(actual, source);
        assert.equal(source.mappedKeypoints!.data.buffer.byteLength, 12);
        assert.equal(actual.rotations![side === 'world' ? 'localQuaternions' : 'worldQuaternions'].length, 0);
    }
});

test('live missing points do not detach the last valid point frame before replacement or reset', async () => {
    const h = harness();
    try {
        await h.drain(); workerDataStore.dispatch('livePresentation', true);
        h.sender.sendKeypoints({pointNames: ['point'], interleaved: new Float32Array([1, 2, 3])}); await h.drain();
        const held = workerDataStore.getLatestKeypoints()!.interleaved;
        h.sender.sendKeypoints({pointNames: ['point'], interleaved: new Float32Array([NaN, NaN, NaN])}); await h.drain();
        assert.deepEqual(Array.from(held), [1, 2, 3]);
        h.sender.sendKeypoints({pointNames: ['point'], interleaved: new Float32Array([4, 5, 6])}); await h.drain();
        assert.equal(held.buffer.byteLength, 0);
        const replacement = workerDataStore.getLatestKeypoints()!.interleaved;
        h.receiver.reset(); await h.drain();
        assert.equal(replacement.buffer.byteLength, 0);
        assert.equal(workerDataStore.getLatestKeypoints()!.interleaved.length, 0);
    } finally {await h.close();}
});

test('pool preserves replacement capacity when a smaller model set changes layout', async t => {
    t.mock.timers.enable({apis: ['setTimeout']});
    let now = 0;
    t.mock.method(performance, 'now', () => now);
    const h = harness();
    try {
        await h.drain(); workerDataStore.dispatch('livePresentation', true);
        // Each update replaces one model, leaving other models on older packets.
        for (let updated = 0; updated < 4; updated++) {
            h.sender.sendModels([0, 1, 2, 3].map(index => modelFrame(index, index === updated ? index + 1 : NaN)));
            await h.drain();
        }
        const retained = workerDataStore.getLatestModelFrames()!;
        assert.equal(retained.length, 4);
        assert.equal(new Set(retained.map(frame => frame.mappedKeypoints!.data.buffer)).size, 4);
        const before = h.sent.length;
        const changed = modelFrame(9, 99);
        changed.mappedKeypoints = {names: ['first', 'second'], data: new Float32Array([1, 2, 3, 4, 5, 6])};
        h.sender.sendModels([changed]); await h.drain();
        assert.equal(h.sent.length, before + 1, 'retained model packets must not delay a changed layout');
        assert.ok(h.sent.at(-1).layout);
        assert.deepEqual(workerDataStore.getLatestModelFrames()!.map(frame => frame.instanceId), [0, 1, 2, 3, 9]);
        assert.deepEqual(Array.from(workerDataStore.getLatestModelFrames()!.at(-1)!.mappedKeypoints!.data), [1, 2, 3, 4, 5, 6]);
        now = 1001; t.mock.timers.tick(1001); await h.drain();
        assert.equal(h.sent.length, before + 1);
        assert.deepEqual(workerDataStore.getLatestModelFrames(), []);
    } finally {await h.close();}
});

test('individually arriving live identities retain spare transfer capacity until expiry', async t => {
    t.mock.timers.enable({apis: ['setTimeout']});
    let now = 0;
    t.mock.method(performance, 'now', () => now);
    const h = harness();
    try {
        await h.drain(); workerDataStore.dispatch('livePresentation', true);
        const held: ArrayBufferLike[] = [];
        for (let instance = 0; instance < 9; instance++) {
            h.sender.sendModels([modelFrame(instance, instance + 1)]);
            await h.drain();
            const frames = workerDataStore.getLatestModelFrames()!;
            assert.equal(frames.length, instance + 1, 'new identity must arrive without waiting for older identities to expire');
            held.push(frames.at(-1)!.mappedKeypoints!.data.buffer);
        }
        assert.equal(h.sent.length, 9);
        assert.ok(held.every(buffer => buffer.byteLength > 0));
        now = 1001; t.mock.timers.tick(1001); await h.drain();
        assert.deepEqual(workerDataStore.getLatestModelFrames(), []);
        assert.ok(held.every(buffer => buffer.byteLength === 0), 'expired worker references all returned to sender');
        h.sender.sendModels([modelFrame(20, 21)]); await h.drain();
        assert.equal(workerDataStore.getLatestModelFrames()![0].instanceId, 20);
    } finally {await h.close();}
});
