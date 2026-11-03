import assert from 'node:assert/strict';
import {test} from 'node:test';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {RealtimeStartupStatusSchema, type RealtimeStartupStatus} from '@/types/realtime-startup';
import {RealtimeStartupStatusView, startupElapsed} from './RealtimeStartupStatusView';

const snapshot = (changes: Partial<RealtimeStartupStatus> = {}): RealtimeStartupStatus => ({
    status: 'running', phase: 'starting_cameras', elapsed_seconds: 4.5, phase_elapsed_seconds: 2.5,
    pipeline_id: null, message: null, error: null, delayed: false, preview_ready: false, ...changes,
});
const noop = () => {};

test('confirmed camera preview does not imply processing readiness and older snapshots default to no preview claim', () => {
    const html = renderToStaticMarkup(<RealtimeStartupStatusView snapshot={snapshot({phase: 'loading_models', preview_ready: true})}/>);
    assert.match(html, /Camera preview has started/); assert.match(html, /Processing: Loading tracking models/);
    assert.doesNotMatch(html, /Realtime processing is ready|first processed frame has arrived/);
    const {preview_ready: _, ...older} = snapshot();
    assert.equal(RealtimeStartupStatusSchema.parse(older).preview_ready, false);
});

test('camera and model phases show measured elapsed time without invented percentages or ETA', () => {
    for (const [phase, label] of [['starting_cameras', 'Starting cameras'], ['loading_models', 'Loading tracking models'],
        ['warming_models', 'Warming up tracking models'], ['waiting_for_frames', 'Waiting for the first processed frame']]) {
        const html = renderToStaticMarkup(<RealtimeStartupStatusView snapshot={snapshot({phase})} onStop={noop}/>);
        assert.match(html, new RegExp(label));
        assert.match(html, /Elapsed: 4s/);
        assert.match(html, /Current step: 2s/);
        assert.match(html, /Stop startup/);
        assert.doesNotMatch(html, /%|remaining|Realtime processing is ready/);
        assert.match(html, /Camera preview and motion processing start separately/);
        assert.doesNotMatch(html, /Camera preview is ready/);
    }
    assert.equal(startupElapsed(187.445), '3m 07s');
});

test('a delayed step and unresponsive status endpoint remain explained', () => {
    const html = renderToStaticMarkup(<RealtimeStartupStatusView
        snapshot={snapshot({phase_elapsed_seconds: 90, elapsed_seconds: 95})}
        statusError="Request timed out" onStop={noop}/>);
    assert.match(html, /No completion estimate is available/);
    assert.match(html, /last reported phase may be out of date/);
    assert.match(html, /Stop startup/);
});

test('stop requests are not represented as native cancellation or readiness', () => {
    const html = renderToStaticMarkup(<RealtimeStartupStatusView snapshot={snapshot({status: 'stopping'})} onStop={noop} onRetry={noop}/>);
    assert.match(html, /current operation must finish/);
    assert.match(html, /disabled=""/);
    assert.doesNotMatch(html, /Retry startup|first processed frame has arrived/);
});

test('failed and stopped outcomes offer retry only when the controller permits it', () => {
    const failed = renderToStaticMarkup(<RealtimeStartupStatusView snapshot={snapshot({status: 'failed', error: 'Camera could not open'})} onRetry={noop}/>);
    assert.match(failed, /Realtime startup failed/);
    assert.match(failed, /Camera could not open/);
    assert.match(failed, /Retry startup/);
    assert.doesNotMatch(failed, /Stop startup/);
    const stopped = renderToStaticMarkup(<RealtimeStartupStatusView snapshot={snapshot({status: 'stopped'})}/>);
    assert.match(stopped, /Realtime startup stopped/);
    assert.doesNotMatch(stopped, /Retry startup/);
});

test('ready means first frame and idle is hidden; continuation is never invented by the view', () => {
    const html = renderToStaticMarkup(<RealtimeStartupStatusView snapshot={snapshot({status: 'ready'})} onStop={noop} onContinueWithDefault={noop}/>);
    assert.match(html, /first processed frame has arrived/);
    assert.doesNotMatch(html, /Stop startup|Continue with default/);
    assert.equal(renderToStaticMarkup(<RealtimeStartupStatusView snapshot={snapshot({status: 'idle'})}/>), '');
    assert.equal(renderToStaticMarkup(<RealtimeStartupStatusView snapshot={null}/>), '');
    assert.doesNotMatch(renderToStaticMarkup(<RealtimeStartupStatusView snapshot={snapshot()}/>), /Continue with default/);
});

test('startup snapshots reject unknown terminal states and invalid time', () => {
    assert.equal(RealtimeStartupStatusSchema.parse(snapshot()).status, 'running');
    assert.throws(() => RealtimeStartupStatusSchema.parse(snapshot({elapsed_seconds: -1})));
    assert.throws(() => RealtimeStartupStatusSchema.parse({...snapshot(), status: 'cancelled_immediately'}));
});

test('unsupported server capability is a concise nonblocking message with no unusable actions', () => {
    const html = renderToStaticMarkup(<RealtimeStartupStatusView snapshot={snapshot()} statusUnavailable onStop={noop} onRetry={noop}/>);
    assert.match(html, /Startup status unavailable from this server version/);
    assert.doesNotMatch(html, /role="alert"|button|Stop startup|Retry startup|loader/);
});
