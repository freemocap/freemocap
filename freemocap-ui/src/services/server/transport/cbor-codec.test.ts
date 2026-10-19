// Bundle with esbuild --bundle --platform=node --format=cjs, then run node --test.
import assert from 'node:assert/strict';
import {test} from 'node:test';
import {encode} from 'cbor-x';
import {decodeMessage} from './cbor-codec';
import {LogStore} from '../server-helpers/log-store';

function logMessage(thread: number | bigint) {
    return {kind: 'log', version: 0, timestamp: 0, sequence: 0, record: {
        name: 'backend', msg: 'test log', args: [], levelname: 'INFO', levelno: 20,
        pathname: 'backend.py', filename: 'backend.py', module: 'backend',
        lineno: 1, funcName: 'main', created: 0, msecs: 0, relativeCreated: 0,
        thread, threadName: 'MainThread', processName: 'MainProcess', process: 123,
        delta_t: '0.000ms', message: 'test log', asctime: '',
        formatted_message: 'test log', type: 'LogRecord',
    }};
}

test('Intel Mac thread IDs survive CBOR decoding and reach the frontend log store', () => {
    // Python encodes this real macOS thread identifier as a CBOR uint64.
    const decoded = decodeMessage(encode(logMessage(140704630302656n)));
    assert.equal(decoded?.kind, 'log');
    if (decoded?.kind !== 'log') throw new Error('Expected log');
    assert.equal(decoded.record.thread, 140704630302656);
    const store = new LogStore();
    store.add(decoded.record);
    assert.equal(store.getSnapshot().entries[0].message, 'test log');
});

test('safe CBOR integers preserve their exact value', () => {
    for (const thread of [123, BigInt(Number.MAX_SAFE_INTEGER), BigInt(Number.MIN_SAFE_INTEGER)]) {
        const decoded = decodeMessage(encode(logMessage(thread)));
        assert.equal(decoded?.kind, 'log');
        if (decoded?.kind === 'log') assert.equal(decoded.record.thread, Number(thread));
    }
});

test('integers outside the JavaScript safe range are rejected without rounding', () => {
    for (const thread of [9007199254740993n, -9007199254740993n]) {
        assert.throws(() => decodeMessage(encode(logMessage(thread))));
    }
});
