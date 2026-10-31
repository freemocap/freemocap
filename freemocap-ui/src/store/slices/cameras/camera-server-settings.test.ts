// Run tools/test-camera-settings.mjs with an ignored output path.
import assert from 'node:assert/strict';
import {store} from '../../index';
import {cameraSlice, cameraDesiredConfigUpdated} from './cameras-slice';
import {createDefaultCameraConfig} from './cameras-types';
import {serverStateReceived} from '../connection/connection-slice';

const config = {...createDefaultCameraConfig('camera-A', 2, 'Physical camera'),
    exposure: -5, framerate: 30, rotation: 1 as const};
assert.ok(store.getState());
Object.defineProperty(globalThis, 'localStorage', {value: {
    getItem: () => null, setItem: () => {}, removeItem: () => {}, clear: () => {}, key: () => null, length: 0,
}});
const snapshot = serverStateReceived({server_pid:1, state:{camera_groups:{group:{id:'group', backend:'python', configs:{'camera-A':config},
        cameras:{},alive:true,recording_in_progress:false,paused:false}},realtime_pipelines:[]}});
const connected = cameraSlice.reducer(undefined, snapshot);
assert.equal(connected.cameras.length, 1);
assert.deepEqual(connected.cameras[0].desiredConfig, config);
assert.deepEqual(connected.cameras[0].actualConfig, config);
assert.equal(connected.cameras[0].connectionStatus, 'connected');
assert.strictEqual(cameraSlice.reducer(connected, snapshot), connected, 'Equal server state must not cause rerenders');
const edited = cameraSlice.reducer(connected, cameraDesiredConfigUpdated({cameraId:'camera-A',config:{exposure:-6}}));
const refreshed = cameraSlice.reducer(edited, snapshot);
assert.equal(refreshed.cameras[0].desiredConfig.exposure, -6, 'Unapplied user edits must survive state updates');
assert.equal(refreshed.cameras[0].actualConfig.exposure, -5);
assert.equal(refreshed.cameras[0].hasConfigMismatch, true);
const reindexed = cameraSlice.reducer(edited, serverStateReceived({server_pid:1, state:{
    camera_groups:{group:{id:'group',backend:'python',configs:{'camera-A':{...config,camera_index:5}},
        cameras:{},alive:true,recording_in_progress:false,paused:false}},realtime_pipelines:[]}}));
assert.equal(reindexed.cameras[0].actualConfig.camera_index, 5);
assert.equal(reindexed.cameras[0].desiredConfig.camera_index, 5);
assert.equal(reindexed.cameras[0].desiredConfig.exposure, -6);
console.log('Camera server-settings reconciliation passed');
