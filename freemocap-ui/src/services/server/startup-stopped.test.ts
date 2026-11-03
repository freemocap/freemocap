import assert from 'node:assert/strict';
import {test} from 'node:test';
import {checkStartupStopped, isStartupStopped, StartupStoppedError} from './startup-stopped';

test('only the explicit startup_stopped 409 is treated as cancellation', async () => {
    await assert.rejects(checkStartupStopped(new Response(JSON.stringify({detail: {code: 'startup_stopped', message: 'Stopped'}}), {status: 409})), StartupStoppedError);
    const conflict = new Response(JSON.stringify({detail: {code: 'other_conflict'}}), {status: 409});
    await checkStartupStopped(conflict); assert.equal(conflict.bodyUsed, false);
    await checkStartupStopped(new Response('<html>conflict</html>', {status: 409}));
    assert.equal(isStartupStopped({name: 'StartupStoppedError'}), true);
    await import('@/store');
    const {realtimeSlice} = await import('@/store/slices/realtime/realtime-slice');
    const {applyRealtimePipeline} = await import('@/store/slices/realtime/realtime-thunks');
    const {defaultRealtimePipelineConfig} = await import('@/store/slices/realtime/realtime-types');
    const state = realtimeSlice.reducer(undefined, applyRealtimePipeline.rejected(new StartupStoppedError('Stopped'), 'id', defaultRealtimePipelineConfig));
    assert.equal(state.error, null); assert.equal(state.applyPending, false); assert.equal(state.isLoading, false);
});
