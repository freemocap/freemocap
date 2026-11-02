import assert from 'node:assert/strict';
import {test} from 'node:test';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {StreamingOutputsPanel, outputStartBody, outputStatusLabel} from './StreamingOutputsPanel';
import {Provider} from 'react-redux';
import {configureStore} from '@reduxjs/toolkit';

test('VMC and LSL have sibling sections with their own controls and settings', () => {
    const store = configureStore({reducer: () => ({connection: {isConnected: false, serverPid: null, realtimePipelines: []}})});
    const html = renderToStaticMarkup(<Provider store={store}><StreamingOutputsPanel/></Provider>);
    assert.match(html, /^<section aria-label="Streaming outputs" class="flex flex-col gap-1 p-1 text text-white">/);
    const advanced = html.indexOf('<details');
    assert.ok(advanced > 0);
    const visible = html.slice(0, advanced);
    assert.match(visible, /subaction-header-container/);
    assert.match(visible, /button-sm-group[^\"]*secondary/);
    assert.match(visible, />Start VMC<\/p>/);
    assert.match(visible, /Status not checked/);
    for (const match of visible.matchAll(/class="([^"]*)"/g)) {
        assert.ok(!match[1].split(/\s+/).includes('hidden'));
    }
    assert.doesNotMatch(visible, /display:\s*none/);
    for (const protocol of ['VMC', 'LSL']) {
        assert.match(html, new RegExp(`aria-label="${protocol} output"`));
        assert.match(html, new RegExp(`>Start ${protocol}</p>`));
        assert.match(html, new RegExp(`<details[^>]*><summary[^>]*>${protocol} settings</summary>`));
    }
    assert.doesNotMatch(html, /aria-label="Protocol"|Start output|Include fingers|Advanced output settings/);
});

test('VMC defaults include fingers and advanced settings preserve an explicit opt-out', () => {
    const schema = {properties: {host: {default: '127.0.0.1'}, port: {default: 39539}, include_fingers: {default: true}}};
    const draft = {config: {host: '127.0.0.1', port: 39539, include_fingers: true}, pipeline: '', queueCapacity: 8};
    assert.equal(outputStartBody('vmc', schema, draft), null);
    assert.deepEqual(outputStartBody('vmc', schema, {...draft, config: {...draft.config, port: 39540, include_fingers: false}, pipeline: ' selected ', queueCapacity: 16}),
        {protocol: 'vmc', pipeline_id: 'selected', queue_capacity: 16, config: {host: '127.0.0.1', port: 39540, include_fingers: false}});
    assert.deepEqual(outputStartBody('vmc', schema, {...draft, config: {...draft.config, include_fingers: false}}),
        {protocol: 'vmc', pipeline_id: null, queue_capacity: 8, config: {...draft.config, include_fingers: false}});
    assert.deepEqual(outputStartBody('lsl', {}, {config: {stream_name: 'My session'}, pipeline: 'lsl-source', queueCapacity: 32}),
        {protocol: 'lsl', pipeline_id: 'lsl-source', queue_capacity: 32, config: {stream_name: 'My session'}});
});

test('an old backend uses explicit settings instead of its incompatible quick-start default', () => {
    const schema = {properties: {include_fingers: {default: false}}};
    assert.deepEqual(outputStartBody('vmc', schema, {config: {include_fingers: true}, pipeline: '', queueCapacity: 8}),
        {protocol: 'vmc', pipeline_id: null, queue_capacity: 8, config: {include_fingers: true}});
});


test('LSL status distinguishes preparation, subscription, sending and failure', () => {
    const base = {protocol: 'lsl', status: 'idle'} as Parameters<typeof outputStatusLabel>[0];
    assert.equal(outputStatusLabel(base), 'Waiting for source data');
    assert.equal(outputStatusLabel({...base, readiness: 'preparing'}), 'Preparing streams');
    assert.equal(outputStatusLabel({...base, readiness: 'waiting_for_receiver'}), 'Available - waiting for a receiver');
    assert.equal(outputStatusLabel({...base, status: 'running', readiness: 'sending'}), 'Sending to connected receivers');
    assert.equal(outputStatusLabel({...base, status: 'failed', readiness: 'sending'}), 'LSL stopped');
    assert.equal(outputStatusLabel({...base, status: 'stopped', readiness: 'sending'}), 'Stopped');
});
