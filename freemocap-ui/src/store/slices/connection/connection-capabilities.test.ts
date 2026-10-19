import assert from 'node:assert/strict';
import {test} from 'node:test';
import {AppStateMessageSchema} from '../../../services/server/transport/message-contract';
import {connectionSlice, serverStateReceived, serverDisconnected} from './connection-slice';

test('backend MediaPipe restriction survives decoding and clears on disconnect', () => {
    const reason = 'Sorry, MediaPipe is not supported on Intel Macs yet.';
    const message = AppStateMessageSchema.parse({kind: 'app_state', version: 0,
        timestamp: 0, sequence: 0, server_pid: 123, mediapipe_unavailable_reason: reason,
        state: {camera_groups: {}, realtime_pipelines: []}});
    const state = connectionSlice.reducer(undefined, serverStateReceived(message));
    assert.equal(state.mediapipeUnavailableReason, reason);
    assert.equal(connectionSlice.reducer(state, serverDisconnected()).mediapipeUnavailableReason, null);
    const supported = {...message, mediapipe_unavailable_reason: null};
    assert.equal(connectionSlice.reducer(state, serverStateReceived(supported)).mediapipeUnavailableReason, null);
});
