import assert from 'node:assert/strict';
import {test} from 'node:test';
import {latestRealtimeTask} from './realtime-progress';
import {TaskRegistrySnapshotSchema} from './transport/message-contract';

test('existing task store retains realtime progress without creating posthoc cards and accepts reconnect replay', async () => {
    await import('@/store');
    const {pipelinesSlice, taskSnapshotReceived} = await import('@/store/slices/pipelines/pipelines-slice');
    const {serverDisconnected} = await import('@/store/slices/connection/connection-slice');
    const snapshot=TaskRegistrySnapshotSchema.parse({server_instance_id:'00000000-0000-4000-8000-000000000001',revision:4,recording_owners:[],tasks:[
        {task_id:'startup:1',revision:1,task_type:'realtime_startup',recording:null,status:'running',progress:{phase:'warming_models',progress_fraction:null,detail:'warming'},cameras:[],created_at:'2026-11-02T10:00:00Z',updated_at:'2026-11-02T10:00:00Z',result:{status:'running',pipeline_id:'p'}},
        {task_id:'startup:2',revision:1,task_type:'realtime_startup',recording:null,status:'running',progress:{phase:'loading_models',progress_fraction:null,detail:'preparing'},cameras:[],created_at:'2026-11-02T10:01:00Z',updated_at:'2026-11-02T10:01:00Z',result:{status:'running',pipeline_id:'p'}},
    ]});
    const state=pipelinesSlice.reducer(undefined,taskSnapshotReceived(snapshot));
    assert.equal(state.realtimeTasks.length,2); assert.deepEqual(state.activePipelines,{}); assert.equal(state.snackbarVisible,false);
    assert.equal(latestRealtimeTask(state.realtimeTasks)?.task_id,'startup:2');
    assert.equal(latestRealtimeTask([]),null);
    const stale=pipelinesSlice.reducer(state,taskSnapshotReceived({...snapshot,revision:3,tasks:[]}));
    assert.equal(stale.realtimeTasks.length,2);
    const disconnected=pipelinesSlice.reducer(state,serverDisconnected());
    assert.deepEqual(disconnected.realtimeTasks,[]);
    assert.equal(pipelinesSlice.reducer(disconnected,taskSnapshotReceived(snapshot)).realtimeTasks.length,2);
    const newer={...snapshot.tasks[1],task_id:'startup:3',created_at:'2026-11-02T10:02:00Z'};
    assert.equal(latestRealtimeTask([newer,...snapshot.tasks])?.task_id,'startup:3');
    assert.equal(latestRealtimeTask([{...newer,created_at:'2026-11-02T10:02:00.000001Z'},
        {...newer,task_id:'startup:4',created_at:'2026-11-02T10:02:00.000002Z'}])?.task_id,'startup:4');
});
