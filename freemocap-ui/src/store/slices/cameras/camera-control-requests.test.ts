import assert from 'node:assert/strict';
import {store} from '../../index';
import {pauseUnpauseCameras} from './cameras-thunks';
import {stopRecording} from '../recording/recording-thunks';
import {serverStateReceived} from '../connection/connection-slice';

async function checkControls() {
    const original = globalThis.fetch;
    const calls: string[] = [];
    try {
        globalThis.fetch = async (input, init) => {
            const path = new URL(String(input)).pathname;
            calls.push(`${init?.method} ${path}`);
            if (path.endsWith('/pause')) {
                const {paused} = JSON.parse(String(init?.body));
                assert.equal(typeof paused, 'boolean');
                // The pushed state can arrive before the HTTP response.
                store.dispatch(serverStateReceived({server_pid: 1, state: {camera_groups: {
                    group: {id: 'group', backend: 'python', configs: {}, cameras: {}, alive: true,
                        recording_in_progress: false, paused},
                }, realtime_pipelines: []}}));
                return new Response(JSON.stringify({paused}));
            }
            return new Response('[]');
        };
        await store.dispatch(pauseUnpauseCameras()).unwrap();
        assert.equal(store.getState().cameras.isPaused, true);
        await store.dispatch(pauseUnpauseCameras()).unwrap();
        assert.equal(store.getState().cameras.isPaused, false);
        assert.equal(await store.dispatch(stopRecording()).unwrap(), null);
        assert.deepEqual(calls, ['PUT /skellycam/camera/group/all/pause',
            'PUT /skellycam/camera/group/all/pause', 'POST /skellycam/camera/group/all/record/stop']);
        console.log('Camera control requests and pushed-state race passed');
    } finally {
        globalThis.fetch = original;
    }
}
void checkControls().catch(error => {console.error(error); process.exitCode = 1;});
