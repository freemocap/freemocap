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
import {KeypointPackingWorkspace, keypointPosition} from '@/components/viewport3d/keypoint-storage';
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

test('temporal status stays aligned through CBOR, resolution and pooled worker transfer', () => {
    const source = frame();
    const labels = ['unavailable', 'current_input', 'predicted_support', 'retained_value'];
    source.instances[0].channels[0].sample_status = new Uint8Array([3]);
    source.instances[0].channels[0].status_labels = labels;
    source.trackers = [{tracker_id: 'body', detector_type: 'pose', model_id: 'subject', channels: [
        {kind: 'KEYPOINTS_3D', names: ['wrist'], columns: ['x', 'y', 'z'],
            data: new Uint8Array(new Float32Array([1, 2, 3]).buffer), sample_status: new Uint8Array([2]), status_labels: labels},
    ]}];
    const resolved = new FrameResolver().resolve(decoded(new MessageDecoder(), source));
    const models = projected(resolved.models);
    assert.deepEqual([...models[0].landmarks!.sampleStatus!], [3]);
    assert.deepEqual(models[0].landmarks!.statusLabels, labels);
    const points = {pointNames: resolved.keypoints!.names, pointSources: resolved.keypoints!.sources};
    const layout = prepareFrameLayout('keypoints', points), buffer = new ArrayBuffer(layout.byteLength);
    writeFrameBuffer(buffer, layout, 'keypoints', points);
    const packed = readFrameBuffer(buffer, layout, 'keypoints');
    assert.ok(!Array.isArray(packed) && 'interleaved' in packed);
    assert.deepEqual([...packed.sampleStatus!], [2]);
    assert.deepEqual(packed.statusGroups, [{startIndex: 0, count: 1, labels}]);
    assert.ok(frameLayoutMatches(layout, 'keypoints', points));
    points.pointSources[0].sampleStatus![0] = 3;
    writeFrameBuffer(buffer, layout, 'keypoints', points);
    assert.deepEqual([...packed.sampleStatus!], [3], 'the reused numerical buffer includes updated status');
    assert.equal(frameLayoutMatches(layout, 'keypoints', {...points, pointSources: [{...points.pointSources[0], sampleStatus: undefined, statusLabels: undefined}]}), false);
    for (const length of [0, 2]) {
        const malformed = {...points, pointSources: [{...points.pointSources[0], sampleStatus: new Uint8Array(length)}]};
        assert.throws(() => writeFrameBuffer(buffer, layout, 'keypoints', malformed), /Invalid point source status/);
    }
});

test('the complete golden wire frame resolves with its declared component layouts', () => {
    const golden = decodeMessage(readFileSync('src/services/server/transport/__fixtures__/message_frame_golden.bin'));
    assert.ok(golden?.kind === 'frame');
    assert.doesNotThrow(() => new FrameResolver().resolve(golden));
});

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

test('reused scalar layouts reject short, excess and empty data instead of retaining pooled values', () => {
    const base = new FrameResolver().resolve(frame()).models[0];
    const model = {...base, segmentLengths: {names: ['first', 'second'], data: new Float32Array([10, 20]), fittedScaleMm: null}};
    const layout = prepareFrameLayout('modelFrames', [model]), buffer = new ArrayBuffer(layout.byteLength);
    writeFrameBuffer(buffer, layout, 'modelFrames', [model]);
    for (const values of [[99], [99, 98, 97], []]) {
        const changed = {...model, segmentLengths: {...model.segmentLengths, data: new Float32Array(values)}};
        assert.equal(frameLayoutMatches(layout, 'modelFrames', [changed]), false);
        assert.throws(() => prepareFrameLayout('modelFrames', [changed]), /declared names/);
        assert.throws(() => writeFrameBuffer(buffer, layout, 'modelFrames', [changed]), /scalar storage/);
        const retained = readFrameBuffer(buffer, layout, 'modelFrames') as ResolvedModelFrame[];
        assert.deepEqual([...retained[0].segmentLengths!.data], [10, 20]);
    }
});

test('quaternion declarations preserve world and local meaning and canonical storage ownership', () => {
    const source = frame();
    source.models = [ModelDefinitionSchema.parse({model_id: 'subject', segments: [{name: 'root', parent: null,
        primary_axis: 'z', rest_orientation: [1, 0, 0, 0], length_proportion: 1, is_fully_specified: true}], landmarks: [], connections: []})];
    const canonical = new Float32Array([1, 0, 0, 0]), reordered = new Float32Array([1, 0, 0, 0]);
    source.instances[0].channels = [
        {kind: 'ROTATIONS_WORLD', columns: ['w', 'x', 'y', 'z'], data: new Uint8Array(canonical.buffer)},
        {kind: 'ROTATIONS_LOCAL', columns: ['x', 'y', 'z', 'w'], data: new Uint8Array(reordered.buffer)},
    ];
    const result = new FrameResolver().resolve(source).models[0].rotations!;
    assert.equal(result.worldQuaternions.buffer, canonical.buffer);
    assert.deepEqual([...result.worldQuaternions], [1, 0, 0, 0]);
    assert.deepEqual([...result.localQuaternions], [0, 1, 0, 0], '180-degree X rotation must not become identity');
    assert.deepEqual([...reordered], [1, 0, 0, 0], 'wire storage remains unchanged');
    for (const columns of [[], ['w', 'x', 'y'], ['w', 'x', 'y', 'y'], ['w', 'x', 'y', 'angle'], ['w', 'x', 'y', 'z', 'quality']]) {
        source.instances[0].channels[0].columns = columns;
        assert.throws(() => new FrameResolver().resolve(source), /Quaternion channel/);
    }
    source.instances[0].channels[0].columns = ['w', 'x', 'y', 'z'];
    for (const length of [0, 3, 5]) {
        source.instances[0].channels[0].data = new Uint8Array(new Float32Array(length).buffer);
        assert.throws(() => new FrameResolver().resolve(source), /Quaternion channel/);
    }
});

test('tracker channels remain borrowed views through changed frames and layouts', () => {
    const source = frame(), resolver = new FrameResolver();
    const firstData = new Float32Array([1, 2, 3, 100]);
    source.trackers = [{tracker_id: 'body', detector_type: 'pose', model_id: 'subject', channels: [
        {kind: 'KEYPOINTS_3D', names: ['wrist'], columns: ['x', 'y', 'z', 'error'], data: new Uint8Array(firstData.buffer)},
    ]}];
    const first = resolver.resolve(source).keypoints!;
    assert.equal(first.sources[0].data.buffer, firstData.buffer);
    assert.equal(first.sources[0].stride, 4);
    const secondData = new Float32Array([4, 5, 6, 101]);
    const changed = {...source, trackers: [{...source.trackers[0], channels: [{...source.trackers[0].channels[0], data: new Uint8Array(secondData.buffer)}]}]};
    const second = resolver.resolve(changed).keypoints!;
    assert.equal(second.names, first.names, 'stable identity metadata is reused');
    assert.equal(second.sources[0].data.buffer, secondData.buffer);
    assert.deepEqual([...first.sources[0].data], [1, 2, 3, 100]);
    const reordered = resolver.resolve({...changed, trackers: [{...changed.trackers[0], channels: [
        {...changed.trackers[0].channels[0], columns: ['error', 'z', 'x', 'y']},
    ]}]}).keypoints!;
    const packing = new KeypointPackingWorkspace();
    const packed = packing.packFrame({pointNames: first.names, pointSources: first.sources});
    assert.deepEqual([...packed], [1, 2, 3]);
    assert.equal(packing.packFrame({pointNames: second.names, pointSources: second.sources}), packed);
    assert.deepEqual([...packed], [4, 5, 6]);
    const input = {pointNames: reordered.names, pointSources: reordered.sources};
    assert.deepEqual([...packing.packFrame(input)], [6, 101, 5]);
    assert.deepEqual(keypointPosition(input, 0), [6, 101, 5]);
    assert.deepEqual([...firstData], [1, 2, 3, 100]);
});

test('camera-fit projection clones only current frame bytes from recording-backed channel views', () => {
    const recording = new Float32Array(100_000).fill(999);
    recording.set([1, 2, 3, 90, 4, 5, 6, 91], 100);
    const pointNames = ['first', 'second'];
    const frame = {pointNames, pointSources: [{names: pointNames, data: recording.subarray(100, 108), stride: 4}]};
    const workspace = new KeypointPackingWorkspace();
    const projected = workspace.packFrame(frame);
    const command = structuredClone({pointNames, interleaved: projected});
    assert.deepEqual([...command.interleaved], [1, 2, 3, 4, 5, 6]);
    assert.equal(command.interleaved.buffer.byteLength, 24);
    assert.equal(recording.buffer.byteLength, 400_000);
    assert.equal(workspace.packFrame(frame), projected);
});
