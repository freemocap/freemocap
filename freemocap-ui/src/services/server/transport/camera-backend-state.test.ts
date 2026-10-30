import assert from 'node:assert/strict';
import {test} from 'node:test';
import {AppStateMessageSchema} from './message-contract';

test('backend selection survives frontend state validation', () => {
    const parsed = AppStateMessageSchema.parse({
        kind: 'app_state', version: 1, timestamp: 0, sequence: 0, server_pid: 1,
        state: {
            camera_groups: {group: {
                id: 'group', backend: 'rust', configs: {}, cameras: {},
                alive: true, recording_in_progress: false, paused: false,
            }},
            realtime_pipelines: [],
        },
    });
    assert.equal(parsed.state.camera_groups.group.backend, 'rust');
});
