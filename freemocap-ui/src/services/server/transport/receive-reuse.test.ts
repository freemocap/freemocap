import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {test} from 'node:test';
import {encode} from 'cbor-x';
import {decodeMessage, MessageDecoder} from './cbor-codec';
import {FrameResolver} from './frame-resolution';
import {equalBytes} from './content-equality';
import {TransportService} from './TransportService';
import {ModelDefinitionSchema, type FrameMessage} from './message-contract';
import type {ResolvedModelFrame} from './frame-types';
import {frameLayoutMatches, prepareFrameLayout, readFrameBuffer, writeFrameBuffer} from '@/components/viewport3d/viewport-frame-codec';

function frame(): FrameMessage {
    const golden = decodeMessage(readFileSync('src/services/server/transport/__fixtures__/message_frame_golden.bin'));
    assert.ok(golden?.kind === 'frame');
    return {...golden, image: new Uint8Array([1, 2, 3]), models: [ModelDefinitionSchema.parse({model_id: 'subject', segments: [],
        landmarks: [{name: 'wrist'}], connections: []})],
        instances: [{model_id: 'subject', instance_id: 0, fitted_scale_mm: null, channels: [{
            kind: 'LANDMARKS_3D', columns: ['confidence', 'z', 'x', 'y', 'error'],
            data: new Uint8Array(new Float32Array([0.5, 30, 10, 20, NaN]).buffer)}]}], trackers: []};
}
function decoded(decoder: MessageDecoder, value: FrameMessage): FrameMessage {
    const message = decoder.decode(encode(value));
    assert.ok(message?.kind === 'frame');
    return message;
}
function projected(models: ResolvedModelFrame[]): ResolvedModelFrame[] {
    const layout = prepareFrameLayout('modelFrames', models), buffer = new ArrayBuffer(layout.byteLength);
    writeFrameBuffer(buffer, layout, 'modelFrames', models);
    return readFrameBuffer(buffer, layout, 'modelFrames') as ResolvedModelFrame[];
}

test('identical metadata and numerical bytes are retained while frame identity and image ownership advance', () => {
    const decoder = new MessageDecoder(), resolver = new FrameResolver(), source = frame();
    const first = decoded(decoder, source), firstResolved = resolver.resolve(first);
    structuredClone(first.image!.buffer, {transfer: [first.image!.buffer as ArrayBuffer]});
    const second = decoded(decoder, {...source, frame_number: source.frame_number + 1, timestamp: source.timestamp + 1});
    assert.equal(second.models, first.models);
    assert.equal(second.cameras, first.cameras);
    assert.equal(second.convention, first.convention);
    assert.equal(second.instances[0].channels[0].data, first.instances[0].channels[0].data);
    assert.deepEqual([...second.image!], [1, 2, 3]);
    assert.equal(second.frame_number, first.frame_number + 1);
    assert.equal(second.timestamp, first.timestamp + 1);
    assert.equal(resolver.resolve(second).models, firstResolved.models);
    assert.ok(Object.isFrozen(first.models[0].landmarks));
    assert.deepEqual([...projected(firstResolved.models)[0].landmarks!.data], [10, 20, 30]);
});

test('changed values and changed layouts never overwrite retained source frames', () => {
    const decoder = new MessageDecoder(), resolver = new FrameResolver(), source = frame();
    const first = resolver.resolve(decoded(decoder, source));
    const changed = structuredClone(source);
    changed.instances[0].channels[0].data = new Uint8Array(new Float32Array([0.5, 31, 11, 21, NaN]).buffer);
    const second = resolver.resolve(decoded(decoder, changed));
    assert.notEqual(first.models, second.models);
    assert.deepEqual([...projected(first.models)[0].landmarks!.data], [10, 20, 30]);
    assert.deepEqual([...projected(second.models)[0].landmarks!.data], [11, 21, 31]);
    changed.instances[0].channels[0].columns = ['confidence', 'x', 'y', 'z', 'error'];
    const reordered = resolver.resolve(decoded(decoder, changed));
    assert.deepEqual([...projected(reordered.models)[0].landmarks!.data], [31, 11, 21]);
    changed.models[0].landmarks[0].name = 'ankle';
    const renamed = resolver.resolve(decoded(decoder, changed));
    assert.deepEqual(renamed.models[0].landmarks!.names, ['ankle']);
    assert.deepEqual(first.models[0].landmarks!.names, ['wrist']);
});

test('unchanged revisions cannot hide metadata changes and malformed packets do not poison caches', () => {
    const decoder = new MessageDecoder(), source = frame();
    const first = decoded(decoder, source), changed = structuredClone(source);
    changed.convention.units = 'm';
    const second = decoded(decoder, changed);
    assert.notEqual(second.convention, first.convention);
    assert.equal(second.models, first.models);
    assert.throws(() => decoder.decode(encode({...changed, frame_number: 'invalid'})));
    assert.equal(decoded(decoder, source).models, first.models);
    const bytes = first.instances[0].channels[0].data;
    decoder.reset();
    const reconnected = decoded(decoder, source);
    assert.notEqual(reconnected.models, first.models);
    assert.notEqual(reconnected.instances[0].channels[0].data, bytes);
    assert.equal(bytes.byteLength, 20);
});

test('byte equality distinguishes every tail byte, NaN payload and signed zero', () => {
    assert.ok(equalBytes(new Uint8Array([1, 2, 3]), new Uint8Array([1, 2, 3])));
    assert.ok(!equalBytes(new Uint8Array([1, 2, 3]), new Uint8Array([1, 2, 4])));
    assert.ok(!equalBytes(new Uint8Array([1, 2]), new Uint8Array([1, 2, 3])));
    assert.ok(!equalBytes(new Uint8Array(new Float32Array([0]).buffer), new Uint8Array(new Float32Array([-0]).buffer)));
    assert.ok(!equalBytes(new Uint8Array(new Uint32Array([0x7fc00001]).buffer), new Uint8Array(new Uint32Array([0x7fc00002]).buffer)));
});

test('declared point components reject mismatched sizes, missing coordinates and duplicates', () => {
    for (const columns of [['x', 'y', 'z'], ['x', 'y', 'y', 'error', 'confidence'], ['x', 'y', 'confidence', 'error', 'quality']]) {
        const source = frame(); source.instances[0].channels[0].columns = columns;
        assert.throws(() => new FrameResolver().resolve(source));
    }
});

test('reused transfer layouts still validate changed source storage', () => {
    const models = new FrameResolver().resolve(frame()).models;
    const layout = prepareFrameLayout('modelFrames', models);
    for (const invalid of [{stride: 2.5}, {coordinateOffsets: [0, 0, 1]}, {coordinateOffsets: [0, 1, 9]}, {data: new Float32Array(4)}]) {
        const changed = [{...models[0], landmarks: {...models[0].landmarks!, ...invalid}}] as ResolvedModelFrame[];
        assert.ok(frameLayoutMatches(layout, 'modelFrames', changed));
        assert.throws(() => writeFrameBuffer(new ArrayBuffer(layout.byteLength), layout, 'modelFrames', changed));
    }
});

test('transport still publishes every stationary frame for live freshness and resets connection caches', () => {
    const service = new TransportService({url: 'ws://localhost/test'}), source = frame();
    const frames: ResolvedModelFrame[][] = [], numbers: number[] = [];
    service.subscribeToModelFrames(value => frames.push(value));
    service.subscribeToDiagnostics(value => {if (value) numbers.push(value.frameNumber);});
    const dispatch = (value: FrameMessage) => {const bytes = encode(value); service['dispatchBytes'](bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength) as ArrayBuffer);};
    dispatch(source); dispatch({...source, frame_number: source.frame_number + 1});
    assert.equal(frames.length, 2); assert.equal(frames[0], frames[1]);
    assert.deepEqual(numbers, [source.frame_number, source.frame_number + 1]);
    service.reset(); dispatch(source);
    assert.notEqual(frames[2], frames[0]);
});
