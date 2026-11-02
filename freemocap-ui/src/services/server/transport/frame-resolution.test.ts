import assert from 'node:assert/strict';
import {test} from 'node:test';
import {FrameMessageSchema} from './message-contract';
import {resolveFrameChannels} from './frame-resolution';
import {workerDataStore} from '@/components/viewport3d/WorkerDataStore';
import type {ResolvedModelFrame} from './frame-types';

test('arbitrary DLC image keypoints and connections require no model definition', () => {
    const data = new Uint8Array(Float32Array.from([10, 20, .9, 30, 40, .8]).buffer);
    const frame = FrameMessageSchema.parse({kind: 'frame', version: 1, timestamp: 1, sequence: 1,
        frame_number: 1, model_sequence: 0, convention: {units: 'mm', handedness: 'right', up_axis: '+Z', forward_axis: '+Y', rotation_frame: 'world', rotation_form: 'quaternion_wxyz'},
        cameras: [], models: [], instances: [], trackers: [{tracker_id: 'custom_keypoints', detector_type: 'dlc', model_id: null,
            connection_groups: [{name: 'outer_edges', pairs: [['corner_alpha', 'corner_beta']], color: '#abcdef'}],
            channels: [{kind: 'OVERLAY_2D', camera_id: 'camera', names: ['corner_alpha', 'corner_beta'], columns: ['x', 'y', 'visibility'], image_size: [640, 480], data}]}]});
    const result = resolveFrameChannels(frame);
    assert.equal(result.models.length, 0);
    assert.equal(result.overlays.length, 1);
    assert.deepEqual(result.overlays[0].names, ['corner_alpha', 'corner_beta']);
    assert.equal(result.overlays[0].data.buffer, data.buffer, 'dense values stay in received storage');
    assert.deepEqual(result.overlays[0].connectionGroups, frame.trackers[0].connection_groups);
    assert.deepEqual(result.overlays[0].imageSize, [640, 480]);
});

test('live resolution keeps all three trajectory products distinct', () => {
    const block = (kind: string, xyz: number[], names?: string[]) => ({kind, names,
        columns: ['x', 'y', 'z', 'reprojection_error'], data: new Uint8Array(Float32Array.from([...xyz, NaN]).buffer)});
    const frame = FrameMessageSchema.parse({kind: 'frame', version: 1, timestamp: 1, sequence: 1,
        frame_number: 4, model_sequence: 0, convention: {units: 'mm', handedness: 'right', up_axis: '+Z', forward_axis: '+Y', rotation_frame: 'world', rotation_form: 'quaternion_wxyz'},
        cameras: [], models: [{model_id: 'subject', segments: [], landmarks: [{name: 'wrist'}], connections: []}],
        instances: [{instance_id: 0, model_id: 'subject', fitted_scale_mm: 1800,
            channels: [block('MAPPED_KEYPOINTS_3D', [10, 20, 30]), block('LANDMARKS_3D', [100, 200, 300])]}],
        trackers: [{tracker_id: 'tracker', detector_type: 'rtmpose', model_id: 'subject',
            channels: [block('KEYPOINTS_3D', [1, 2, 3], ['detector_wrist'])]}]});
    const resolved = resolveFrameChannels(frame);
    assert.deepEqual(Array.from(resolved.keypoints!.sources[0].data), [1, 2, 3, NaN]);
    assert.deepEqual(Array.from(resolved.models[0].mappedKeypoints!.data), [10, 20, 30, NaN]);
    assert.deepEqual(Array.from(resolved.models[0].landmarks!.data), [100, 200, 300, NaN]);
    assert.equal(resolved.models[0].landmarks!.stride, 4);
});

test('live viewer accepts mapped observations without a solved pose and replaces old geometry', () => {
    const mappedKeypoints = {names: ['wrist'], data: Float32Array.from([1, 2, 3])};
    const frame: ResolvedModelFrame = {modelId: 'subject', instanceId: 0, fittedScaleMm: null,
        mappedKeypoints, landmarks: null, segmentOrigins: null, rotations: null,
        segmentLengths: null, derived: {centerOfMass: null, xcom: null}};
    workerDataStore.dispatch('livePresentation', true);
    try {
        workerDataStore.dispatch('modelFrames', [{...frame, landmarks: mappedKeypoints}]);
        workerDataStore.dispatch('modelFrames', [frame]);
        const visible = workerDataStore.getLatestModelFrames!()!;
        assert.deepEqual(visible, [frame]);
        assert.equal(visible[0].landmarks, null);
    } finally {
        workerDataStore.dispatch('livePresentation', false);
    }
});
