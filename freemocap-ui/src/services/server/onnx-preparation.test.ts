import assert from 'node:assert/strict';
import {test} from 'node:test';
import {boundedPreparationRequest, requestOnnxPreparation, PreparationPipelineAvailability, PreparationPipelineUnavailableError} from './onnx-preparation';
import {StartupStatusCapability, StartupStatusUnavailableError} from './realtime-startup';
import {checkStartupStopped, isStartupStopped, StartupStoppedError} from './startup-stopped';

const snapshot = {pipeline_id: 'p', status: 'running', phase: 'loading_models', elapsed_seconds: 4, model_name: 'pose',
    message: null, error: null, can_prepare: false, can_cancel: true, requested_provider: 'tensorrt', active_provider: 'cuda'};

test('preparation reads never start a build and explicit actions use separate POST routes', async () => {
    const original = globalThis.fetch;
    const requests: string[] = [];
    globalThis.fetch = async (url, init) => {requests.push(`${init?.method} ${new URL(String(url)).pathname}`); return new Response(JSON.stringify(snapshot));};
    try {
        for (const action of ['status', 'prepare', 'stop'] as const) await requestOnnxPreparation('p', action, new AbortController().signal);
        assert.deepEqual(requests, ['GET /freemocap/onnx/preparation/p', 'POST /freemocap/onnx/preparation/p', 'POST /freemocap/onnx/preparation/p/stop']);
    } finally {globalThis.fetch = original;}
});
test('preparation HTML404 capability disables repeated probes and changes identity permit retry', async () => {
    const original = globalThis.fetch; let count = 0;
    const capability = new StartupStatusCapability();
    globalThis.fetch = async () => {count++; return new Response('<html>missing</html>', {status: 404});};
    try {
        for (const id of ['old', 'old', 'new']) {
            if (!capability.allows(id)) continue;
            await assert.rejects(requestOnnxPreparation('p', 'status', new AbortController().signal), StartupStatusUnavailableError);
            capability.markUnavailable(id);
        }
        assert.equal(count, 2);
    } finally {globalThis.fetch = original;}
});
test('bounded preparation request times out without cancelling its owning operation', async () => {
    const original = globalThis.fetch; const owner = new AbortController(); let signal: AbortSignal | null | undefined;
    globalThis.fetch = async (_, init) => {signal = init?.signal; return new Promise(() => {});};
    try {
        await assert.rejects(boundedPreparationRequest('p', 'status', owner.signal, 5), /has not answered/);
        assert.equal(signal?.aborted, true); assert.equal(owner.signal.aborted, false);
    } finally {globalThis.fetch = original;}
});

test('stale pipeline 409 stops status probes until pipeline/server/reconnect changes without disabling server capability', async () => {
    const original = globalThis.fetch; let count = 0;
    const availability = new PreparationPipelineAvailability();
    const capability = new StartupStatusCapability();
    globalThis.fetch = async () => {count++; return new Response(JSON.stringify({detail: 'Pipeline is not alive'}), {status: 409});};
    async function probe(identity: string, pipelineId: string) {
        if (availability.reason(identity, pipelineId)) return;
        try {await requestOnnxPreparation(pipelineId, 'status', new AbortController().signal);}
        catch (error) {
            assert.ok(error instanceof PreparationPipelineUnavailableError);
            availability.markUnavailable(identity, pipelineId, error.message);
        }
    }
    try {
        await probe('server', 'old'); await probe('server', 'old'); await probe('server', 'old');
        assert.equal(count, 1); assert.equal(capability.allows('server'), true);
        assert.match(availability.reason('server', 'old')!, /Pipeline is not alive/);
        await probe('server', 'new'); assert.equal(count, 2);
        await probe('new-server', 'new'); assert.equal(count, 3);
        availability.reset(); await probe('new-server', 'new'); assert.equal(count, 4);
        await assert.rejects(requestOnnxPreparation('new', 'prepare', new AbortController().signal), error =>
            error instanceof Error && !(error instanceof PreparationPipelineUnavailableError));
    } finally {globalThis.fetch = original;}
});
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
