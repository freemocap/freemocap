import assert from 'node:assert/strict';
import {test} from 'node:test';
import {RealtimeStartupStatusSchema} from '@/types/realtime-startup';
import {requestRealtimeStartup, stopRealtimeStartup, StartupStatusCapability, StartupStatusUnavailableError} from './realtime-startup';
import {readStartupWithDeadline, startupStillPending} from './startup-polling';
import {defaultRealtimePipelineConfig} from '@/store/slices/realtime/realtime-types';

const snapshot = (status = 'running') => RealtimeStartupStatusSchema.parse({status,
    phase: 'starting_cameras', elapsed_seconds: 16, phase_elapsed_seconds: 16,
    pipeline_id: null, message: null, error: null, delayed: true});

test('startup status and stop use the generated SDK routes with independent requests', async () => {
    const original = globalThis.fetch;
    const requests: {url: string; method: string; signal: AbortSignal | null | undefined}[] = [];
    globalThis.fetch = async (input, init) => {
        requests.push({url: String(input), method: init?.method ?? 'GET', signal: init?.signal});
        return new Response(JSON.stringify(snapshot(requests.length === 1 ? 'running' : 'stopping')), {status: 200});
    };
    try {
        const controller = new AbortController();
        assert.equal((await requestRealtimeStartup(controller.signal)).delayed, true);
        assert.equal((await stopRealtimeStartup(controller.signal)).status, 'stopping');
        assert.deepEqual(requests.map(({url, method}) => [new URL(url).pathname, method]), [
            ['/freemocap/realtime/startup', 'GET'], ['/freemocap/realtime/startup/stop', 'POST'],
        ]);
        assert.ok(requests.every(request => request.signal === controller.signal));
    } finally {globalThis.fetch = original;}
});

test('bounded status read reports an unresponsive endpoint and aborts only its request', async () => {
    let requestSignal: AbortSignal | undefined;
    const owner = new AbortController();
    await assert.rejects(readStartupWithDeadline(signal => {
        requestSignal = signal;
        return new Promise(() => {});
    }, owner.signal, 5), /has not answered/);
    assert.equal(requestSignal?.aborted, true);
    assert.equal(owner.signal.aborted, false);
});

test('completed status read does not leave a timeout and startup remains pending through stop request', async () => {
    const owner = new AbortController();
    const ready = snapshot('ready');
    assert.equal(await readStartupWithDeadline(async () => ready, owner.signal, 5), ready);
    for (const state of ['running', 'stopping']) assert.equal(startupStillPending(snapshot(state)), true);
    for (const state of ['idle', 'ready', 'failed', 'stopped']) assert.equal(startupStillPending(snapshot(state)), false);
});

test('failed apply retains the exact requested configuration for retry', async () => {
    await import('@/store');
    const {realtimeSlice} = await import('@/store/slices/realtime/realtime-slice');
    const {applyRealtimePipeline} = await import('@/store/slices/realtime/realtime-thunks');
    const requested = structuredClone(defaultRealtimePipelineConfig);
    requested.camera_node_config.skeleton_tracking_enabled = !requested.camera_node_config.skeleton_tracking_enabled;
    const pending = realtimeSlice.reducer(undefined, applyRealtimePipeline.pending('request', requested));
    assert.equal(pending.applyPending, true);
    assert.deepEqual(pending.lastApplyConfig, requested);
    const failed = realtimeSlice.reducer(pending, applyRealtimePipeline.rejected(new Error('Camera unavailable'), 'request', requested));
    assert.equal(failed.applyPending, false);
    assert.deepEqual(failed.lastApplyConfig, requested);
    assert.equal(failed.error, 'Camera unavailable');
    assert.notDeepEqual(failed.pipelineConfig, requested, 'the accepted config is not fabricated on failure');
});

test('HTTP apply completion does not invent startup readiness', async () => {
    await import('@/store');
    const {realtimeSlice} = await import('@/store/slices/realtime/realtime-slice');
    const {applyRealtimePipeline} = await import('@/store/slices/realtime/realtime-thunks');
    const requested = structuredClone(defaultRealtimePipelineConfig);
    const pending = realtimeSlice.reducer(undefined, applyRealtimePipeline.pending('request', requested));
    const completed = realtimeSlice.reducer(pending, applyRealtimePipeline.fulfilled({
        pipeline_id: 'pipeline', camera_group_id: 'group', resolved_config: requested,
    }, 'request', requested));
    assert.equal(completed.isConnected, true, 'existing pipeline lifecycle signal stays compatible');
    assert.equal(completed.applyPending, false);
    assert.equal('startupReady' in completed, false, 'only the independent server status can establish ready');
});

test('HTML 404 is probed once per server identity and reconnect permits a new probe', async () => {
    const original = globalThis.fetch;
    const capability = new StartupStatusCapability();
    let calls = 0;
    globalThis.fetch = async () => {calls++; return new Response('<html>Not Found</html>', {status: 404});};
    async function probe(identity: string) {
        if (!capability.allows(identity)) return;
        try {await requestRealtimeStartup();}
        catch (error) {
            assert.ok(error instanceof StartupStatusUnavailableError);
            capability.markUnavailable(identity);
        }
    }
    try {
        await probe('server:old'); await probe('server:old'); await probe('server:old');
        assert.equal(calls, 1);
        await probe('server:new');
        assert.equal(calls, 2);
        capability.reset();
        await probe('server:new');
        assert.equal(calls, 3);
    } finally {globalThis.fetch = original;}
});
