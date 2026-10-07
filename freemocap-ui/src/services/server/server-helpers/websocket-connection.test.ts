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

test('reconnect and disposal retain a single owned socket and reject stale callbacks', (t) => {
    const consoleSpies = (['log', 'info', 'warn', 'error', 'debug'] as const).map(
        method => t.mock.method(console, method, () => {}),
    );
    const originalSocket = globalThis.WebSocket;
    const originalWindow = Object.getOwnPropertyDescriptor(globalThis, 'window');
    const originalClearTimeout = globalThis.clearTimeout;
    const originalClearInterval = globalThis.clearInterval;
    const timers = new Map<number, () => void>();
    let nextTimer = 0;
    let lastDelay = 0;
    const schedule = (callback: () => void, delay: number): number => {
        lastDelay = delay;
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
        assert.equal(timers.size, 1, 'connect cannot bypass retry backoff');
        const retry = timers.values().next().value!;
        timers.clear();
        retry();
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

        // Stay offline well beyond the old five-retry limit, including server errors.
        connection.connect();
        for (let attempt = 0; attempt < 30; attempt++) {
            const socket = SocketStub.instances.at(-1)!;
            if (attempt % 2 === 0) {
                socket.readyState = SocketStub.OPEN;
                socket.onopen!();
            }
            socket.readyState = 3;
            socket.onerror!(new Event('error'));
            socket.onclose!({code: attempt % 2 === 0 ? 1011 : 1006, reason: ''} as CloseEvent);
            assert.equal(connection.getState(), ConnectionState.RECONNECTING);
            assert.equal(connection.send({test: true}), false);
            assert.equal(timers.size, 1);
            assert.equal(lastDelay, 5000, 'every retry waits five seconds');
            const retryCallback = timers.values().next().value!;
            timers.clear();
            retryCallback();
        }
        const recovered = SocketStub.instances.at(-1)!;
        recovered.readyState = SocketStub.OPEN;
        recovered.onopen!();
        assert.equal(connection.getState(), ConnectionState.CONNECTED);
        assert.equal(connection.send({test: true}), true);
        recovered.send = () => { throw new Error('send failed'); };
        assert.equal(connection.send({test: true}), false);
        assert.equal(connection.sendRaw('ping'), false);
        recovered.readyState = 3;
        recovered.onclose!({code: 1000, reason: ''} as CloseEvent);
        assert.equal(timers.size, 1, 'even a clean server close retries');
        connection.disconnect();
        assert.equal(timers.size, 0, 'explicit disconnect cancels pending recovery');

        // Constructor failures must also recover without throwing or logging.
        Object.defineProperty(globalThis, 'WebSocket', {value: class {
            constructor() { throw new Error('temporarily unavailable'); }
        }});
        connection.connect();
        assert.equal(connection.getState(), ConnectionState.RECONNECTING);
        assert.equal(lastDelay, 5000);
        Object.defineProperty(globalThis, 'WebSocket', {value: SocketStub});
        const retryCallback = timers.values().next().value!;
        timers.clear();
        retryCallback();
        const finalSocket = SocketStub.instances.at(-1)!;
        finalSocket.readyState = SocketStub.OPEN;
        finalSocket.onopen!();
        assert.equal(connection.getState(), ConnectionState.CONNECTED);
        for (const spy of consoleSpies) assert.equal(spy.mock.callCount(), 0);
    } finally {
        connection.disconnect();
        Object.defineProperty(globalThis, 'WebSocket', {value: originalSocket});
        if (originalWindow) Object.defineProperty(globalThis, 'window', originalWindow);
        else Reflect.deleteProperty(globalThis, 'window');
        Object.defineProperty(globalThis, 'clearTimeout', {value: originalClearTimeout});
        Object.defineProperty(globalThis, 'clearInterval', {value: originalClearInterval});
    }
});
