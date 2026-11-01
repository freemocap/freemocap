import assert from 'node:assert/strict';
import {test} from 'node:test';
import {createRecordingExport, recordingExportUrl, waitForTaskResult} from './recording-exports';

test('export identity uses encoded recording paths and preserves kind-specific options', async () => {
    const path = 'C:\\recordings & trials\\clip 1';
    const url = new URL(recordingExportUrl(path, '/export-options'));
    assert.equal(url.pathname, '/freemocap/recordings/clip%201/export-options');
    assert.equal(url.searchParams.get('recording_parent_directory'), 'C:\\recordings & trials');
    const original = globalThis.fetch;
    globalThis.fetch = async (input, init) => {
        assert.equal(new URL(String(input)).pathname, '/freemocap/recordings/clip%201/exports');
        assert.deepEqual(JSON.parse(String(init?.body)), {kind: 'blender', blenderExportConfig: {formats: ['fbx', 'bvh']}});
        return new Response(JSON.stringify({task_id: 'export:one'}), {status: 202});
    };
    try {
        assert.deepEqual(await createRecordingExport(path, {kind: 'blender', blenderExportConfig: {formats: ['fbx', 'bvh']}}), {task_id: 'export:one'});
    } finally {globalThis.fetch = original;}
});

test('task observation returns only completed results and surfaces cancellation or failure', async () => {
    const original = globalThis.fetch;
    try {
        for (const status of ['complete', 'failed', 'cancelled']) {
            globalThis.fetch = async input => {
                assert.ok(String(input).endsWith('/tasks/export%3Aone'));
                return new Response(JSON.stringify({status, result: {files: ['a.csv']}, error: null, progress: {detail: 'Stopped'}}));
            };
            if (status === 'complete') assert.deepEqual(await waitForTaskResult('export:one'), {files: ['a.csv']});
            else await assert.rejects(waitForTaskResult('export:one'), /Stopped/);
        }
        const stopped = new AbortController();
        stopped.abort(new Error('Observation stopped'));
        globalThis.fetch = async () => {throw new Error('Aborted observer must not issue a request');};
        await assert.rejects(waitForTaskResult('export:one', stopped.signal), /Observation stopped/);
    } finally {globalThis.fetch = original;}
});
