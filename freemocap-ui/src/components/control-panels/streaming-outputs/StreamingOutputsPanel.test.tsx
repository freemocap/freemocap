import assert from 'node:assert/strict';
import {test} from 'node:test';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {StreamingOutputsPanel} from './StreamingOutputsPanel';
import {Provider} from 'react-redux';
import {configureStore} from '@reduxjs/toolkit';

test('streaming output header and VMC quick action are outside hidden advanced settings', () => {
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
    assert.match(html, /<details[^>]*><summary[^>]*>Advanced output settings<\/summary>/);
});
