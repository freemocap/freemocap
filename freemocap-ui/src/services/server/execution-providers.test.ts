// Bundle with esbuild --bundle --platform=node --format=cjs, then node --test.
import assert from 'node:assert/strict';
import {test} from 'node:test';
import {requestExecutionProviders, executionProviderOptions} from './execution-providers';

test('unknown server support exposes Auto and the saved selection only', () => {
    assert.deepEqual(executionProviderOptions(null, []).map(option => option.value), [null]);
    assert.deepEqual(executionProviderOptions('cuda', []).map(option => option.value), [null, 'cuda']);
    assert.deepEqual(executionProviderOptions(null, ['cpu']).map(option => option.value), [null, 'cpu']);
});

test('reconnected or different servers are queried again and preserve abort signals', async () => {
    const calls: string[] = [];
    const controller = new AbortController();
    const request = (async (url, options) => {
        calls.push(String(url));
        assert.equal(options?.signal, controller.signal);
        return Response.json({available: calls.length === 1 ? ['cuda', 'cpu'] : ['cpu']});
    }) as typeof fetch;
    assert.deepEqual(await requestExecutionProviders('/first', controller.signal, request), ['cuda', 'cpu']);
    assert.deepEqual(await requestExecutionProviders('/second', controller.signal, request), ['cpu']);
    assert.deepEqual(calls, ['/first', '/second']);
});

test('HTTP failures and malformed provider lists are not advertised as support', async () => {
    for (const response of [new Response('', {status: 503}), Response.json({available: ['unknown']}), Response.json({})]) {
        await assert.rejects(requestExecutionProviders('/providers', undefined, (async () => response) as typeof fetch));
    }
});
