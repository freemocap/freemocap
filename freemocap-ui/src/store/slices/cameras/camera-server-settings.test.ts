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

async function checkAutoApply() {
    const empty = serverStateReceived({server_pid: 1, state: {camera_groups: {}, realtime_pipelines: []}});
    const edit = cameraDesiredConfigUpdated({cameraId: 'camera-A', config: {exposure: -8}});
    const settle = () => new Promise(resolve => setTimeout(resolve, 450));
    const originalFetch = globalThis.fetch;
    const requests: string[] = [];
    globalThis.fetch = async input => {
        requests.push(String(input));
        return new Response(JSON.stringify({group_id: 'group', camera_configs: {}}));
    };
    try {
        store.dispatch(snapshot);
        store.dispatch(empty);
        store.dispatch(edit);
        await settle();
        assert.equal(store.getState().cameras.cameras[0].desiredConfig.exposure, -8);
        assert.equal(requests.length, 0, 'Disconnected edits must stay local');
        store.dispatch(snapshot);
        store.dispatch(edit);
        store.dispatch(empty);
        await settle();
        assert.equal(requests.length, 0, 'Closing the group must cancel a pending update');
        store.dispatch(snapshot);
        store.dispatch(edit);
        await settle();
        assert.equal(requests.length, 1, 'An edit to a live group still auto-applies');
    } finally {
        globalThis.fetch = originalFetch;
    }
}
void checkAutoApply().catch(error => {console.error(error); process.exitCode = 1;});
