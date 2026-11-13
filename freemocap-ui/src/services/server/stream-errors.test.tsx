import assert from 'node:assert/strict';
import {test} from 'node:test';
import React from 'react';
import {Provider} from 'react-redux';
import {configureStore} from '@reduxjs/toolkit';
import {renderToStaticMarkup} from 'react-dom/server';
import {encode} from 'cbor-x';
import {TransportService} from './transport/TransportService';
import {subscribeToStreamErrors} from './stream-errors';
import {connectionSlice, streamErrorReceived, streamErrorCleared} from '@/store/slices/connection/connection-slice';
import {OperationErrorBanner} from '@/components/common/OperationErrorBanner';

test('malformed stream packets reach the visible error banner without disconnecting or flooding it', () => {
    let onmessage: ((event: MessageEvent) => void) | null = null;
    const socket = {
        readyState: 0,
        binaryType: '',
        get onmessage() {return onmessage;},
        set onmessage(callback: ((event: MessageEvent) => void) | null) {onmessage = callback;},
        close() {},
        send() {},
    };
    const transport = new TransportService({url: 'ws://server.invalid/websocket/connect',
        socketFactory: () => socket as unknown as WebSocket});
    const store = configureStore({reducer: {
        connection: connectionSlice.reducer,
        recording: () => ({error: null}), calibration: () => ({error: null}),
        mocap: () => ({error: null}), realtime: () => ({error: null}), cameras: () => ({error: null}),
    }});
    let reported = 0;
    const unsubscribe = subscribeToStreamErrors(transport, message => {
        reported++;
        store.dispatch(streamErrorReceived(message));
    });
    const packet = encode({kind: 'frame', version: 0});
    const sendInvalid = () => onmessage?.({data: packet.buffer.slice(packet.byteOffset, packet.byteOffset + packet.byteLength)} as MessageEvent);
    transport.connect();
    try {
        sendInvalid();
        sendInvalid();
        assert.equal(reported, 1);
        const html = renderToStaticMarkup(<Provider store={store}><OperationErrorBanner/></Provider>);
        assert.match(html, /role="alert"/);
        assert.match(html, /Live stream/);
        assert.match(html, /Some frames may be missing/);
        store.dispatch(streamErrorCleared());
        sendInvalid();
        assert.equal(store.getState().connection.streamError, null, 'dismissed repeated error does not flash every frame');
        unsubscribe();
        sendInvalid();
        assert.equal(reported, 1);
    } finally {
        unsubscribe();
        transport.disconnect();
    }
});

test('a failed camera start shows its explanation in the banner, line by line', () => {
    const explanation = 'Could not start 5 camera(s) with these settings.\nWhy: the USB controller reset.\nWhat to try: lower the frame rate or resolution.';
    const store = configureStore({reducer: {
        connection: connectionSlice.reducer,
        recording: () => ({error: null}), calibration: () => ({error: null}),
        mocap: () => ({error: null}), realtime: () => ({error: null}), cameras: () => ({error: explanation}),
    }});
    const html = renderToStaticMarkup(<Provider store={store}><OperationErrorBanner/></Provider>);
    assert.match(html, /Cameras:/);
    assert.match(html, /pre-wrap/);
    assert.ok(html.includes('Why: the USB controller reset.\nWhat to try: lower the frame rate or resolution.'));
});

test('a different protocol failure can be reported after a previous one', () => {
    let receive: (error: unknown) => void = () => {};
    const errors: string[] = [];
    subscribeToStreamErrors({subscribeToProtocolErrors: callback => {receive = callback; return () => {}; }}, message => errors.push(message));
    receive(new Error('first failure'));
    receive(new Error('first failure'));
    receive('second failure');
    assert.equal(errors.length, 2);
    assert.match(errors[1], /second failure/);
});
