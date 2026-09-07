import assert from 'node:assert/strict';
import {test} from 'node:test';
import {ConnectionState, WebSocketConnection} from './websocket-connection';

class SocketStub {
    static OPEN = 1;
    static instances: SocketStub[] = [];
    readyState = 0;
    binaryType = '';
    onopen: (() => void) | null = null;
    onclose: ((event: CloseEvent) => void) | null = null;
    onerror: ((event: Event) => void) | null = null;
    onmessage: ((event: MessageEvent) => void) | null = null;
    constructor(readonly url: URL) { SocketStub.instances.push(this); }
    close(): void { this.readyState = 3; }
    send(): void {}
}

test('reconnect and disposal retain a single owned socket and reject stale callbacks', () => {
    const originalSocket = globalThis.WebSocket;
    const originalWindow = Object.getOwnPropertyDescriptor(globalThis, 'window');
    const originalClearTimeout = globalThis.clearTimeout;
    const originalClearInterval = globalThis.clearInterval;
    const timers = new Map<number, () => void>();
    let nextTimer = 0;
    const schedule = (callback: () => void): number => {
        timers.set(++nextTimer, callback);
        return nextTimer;
    };
    Object.defineProperty(globalThis, 'WebSocket', {configurable: true, writable: true, value: SocketStub});
    Object.defineProperty(globalThis, 'window', {configurable: true, value: {
        setTimeout: schedule, setInterval: schedule,
    }});
    Object.defineProperty(globalThis, 'clearTimeout', {configurable: true, value: (id: number) => timers.delete(id)});
    Object.defineProperty(globalThis, 'clearInterval', {configurable: true, value: (id: number) => timers.delete(id)});
    const connection = new WebSocketConnection({url: 'ws://localhost/websocket/connect'});
    try {
        connection.connect();
        connection.connect();
        assert.equal(SocketStub.instances.length, 1);
        const first = SocketStub.instances[0];
        const staleOpen = first.onopen!;
        const staleClose = first.onclose!;
        first.onclose!({code: 1006, reason: ''} as CloseEvent);
        assert.equal(timers.size, 1);
        connection.connect();
        assert.equal(timers.size, 0, 'manual connect cancels the scheduled retry');
        const second = SocketStub.instances[1];
        staleOpen();
        staleClose({code: 1006, reason: ''} as CloseEvent);
        assert.equal(connection.getState(), ConnectionState.CONNECTING);
        assert.equal(timers.size, 0);
        assert.equal(first.url.searchParams.get('client_id'), second.url.searchParams.get('client_id'));
        assert.notEqual(first.url.searchParams.get('connection_id'), second.url.searchParams.get('connection_id'));
        second.readyState = SocketStub.OPEN;
        second.onopen!();
        assert.equal(timers.size, 1);
        connection.disconnect();
        assert.equal(timers.size, 0);
        assert.equal(second.onopen, null);
        assert.equal(second.onmessage, null);
        assert.equal(connection.getState(), ConnectionState.DISCONNECTED);
    } finally {
        connection.disconnect();
        Object.defineProperty(globalThis, 'WebSocket', {value: originalSocket});
        if (originalWindow) Object.defineProperty(globalThis, 'window', originalWindow);
        else Reflect.deleteProperty(globalThis, 'window');
        Object.defineProperty(globalThis, 'clearTimeout', {value: originalClearTimeout});
        Object.defineProperty(globalThis, 'clearInterval', {value: originalClearInterval});
    }
});
