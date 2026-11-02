import assert from 'node:assert/strict';
import {test} from 'node:test';
import {createHttpClient, ApiError} from '../dist/http.js';

test('VMC quick start sends POST without requiring a JSON body', async () => {
    const client = createHttpClient({baseUrl: 'http://example.invalid', fetch: async (url, init) => {
        assert.equal(new URL(url).pathname, '/freemocap/streaming/vmc/start');
        assert.equal(init.method, 'POST');
        assert.equal(init.body, undefined);
        return new Response(JSON.stringify({id: 'default-vmc', status: 'idle'}));
    }});
    assert.equal((await client.operations.streaming_start_vmc()).status, 200);
});

test('output commands preserve configuration, observed state, exact timestamp and error distinctions', async () => {
    const calls = [];
    const state = {id: 'out #1', protocol: 'vmc', status: 'idle', pipeline_id: 'pipeline-a', config: {host: '127.0.0.1', port: 39539}, last_capture_timestamp_ns: '9007199254740993'};
    const client = createHttpClient({baseUrl: 'http://example.invalid', fetch: async (url, init) => {
        calls.push({path: new URL(url).pathname, method: init.method, body: init.body ? JSON.parse(init.body) : undefined});
        return new Response(JSON.stringify({...state, status: init.method === 'DELETE' ? 'stopped' : 'idle'}), {status: init.method === 'POST' ? 201 : 200, headers: {'content-type': 'application/json'}});
    }});
    const body = {protocol: 'vmc', pipeline_id: 'pipeline-a', config: {host: '127.0.0.1', port: 39539}, queue_capacity: 8};
    assert.equal((await client.operations.streaming_create_output({body})).data.status, 'idle');
    assert.equal((await client.operations.streaming_get_output({path: {output_id: state.id}})).data.last_capture_timestamp_ns, '9007199254740993');
    assert.equal((await client.operations.streaming_stop_output({path: {output_id: state.id}})).data.status, 'stopped');
    assert.deepEqual(calls, [
        {path: '/freemocap/streaming/outputs', method: 'POST', body},
        {path: '/freemocap/streaming/outputs/out%20%231', method: 'GET', body: undefined},
        {path: '/freemocap/streaming/outputs/out%20%231', method: 'DELETE', body: undefined},
    ]);
    for (const status of [404, 409, 422, 503]) {
        let count = 0;
        const broken = createHttpClient({baseUrl: 'http://example.invalid', fetch: async () => {
            count++; return new Response(JSON.stringify({detail: 'observed failure'}), {status, headers: {'content-type': 'application/json'}});
        }});
        await assert.rejects(() => broken.operations.streaming_create_output({body}), error => error instanceof ApiError && error.status === status && error.body.detail === 'observed failure');
        assert.equal(count, 1, 'Mutations must not be retried automatically');
    }
});
