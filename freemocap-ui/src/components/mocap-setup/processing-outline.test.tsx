// Run: node src/components/realtime-processing/run-realtime-processing-tests.mjs
// The posthoc baseline in fixtures/processing-outline.posthoc.html is recorded by the same command with
// RECORD_BASELINE=1. Record it again only when the posthoc outline is meant to change.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {test} from 'node:test';
import {renderToStaticMarkup} from 'react-dom/server';
import {Provider} from 'react-redux';
// The store import follows the application entry order: the outline's posthoc switches read it.
import {store} from '@/store';
import ProcessingOutline from './processing-outline';
import type {ProcessingSection} from './processing-sections';
import StageSection from './stage-section';

// The tests run from freemocap-ui.
const BASELINE = 'src/components/mocap-setup/fixtures/processing-outline.posthoc.html';

/** Posthoc sections as the Mocap processing window passes them, without their settings. */
const POSTHOC: ProcessingSection[] = [
    {id: 'recording', number: null, title: 'Recording', stage: null, summary: null, content: null},
    {id: 'observations', number: 1, title: '2D tracking', stage: 'observations', summary: null, content: null},
    {id: 'triangulation', number: 2, title: 'Triangulation', stage: 'triangulation', summary: null, content: null},
];
/** The outline's rows, in order. */
const rows = (html: string): string[] => html.match(/<li .*?<\/li>/g) ?? [];

test('posthoc outline markup is unchanged', () => {
    const html = renderToStaticMarkup(<ProcessingOutline sections={POSTHOC} active="observations" playback={false} states={null} onPick={() => {}}/>);
    if (process.env.RECORD_BASELINE === '1') fs.writeFileSync(BASELINE, `${html}\n`);
    assert.equal(html, fs.readFileSync(BASELINE, 'utf8').trimEnd());
});

test('own switches and states replace the posthoc ones', () => {
    const sections: ProcessingSection[] = [
        {id: 'triangulation', number: 2, title: 'Triangulation', stage: 'triangulation', summary: null, content: null,
            toggle: <input aria-label="Triangulation"/>, state: <span data-state="on"/>},
        {id: 'filtering', number: 3, title: 'Gap filling and filtering', stage: 'filtering', summary: null, content: null},
    ];
    const html = renderToStaticMarkup(<Provider store={store}>
        <ProcessingOutline sections={sections} active={null} playback states={null} onPick={() => {}}/>
    </Provider>);
    const [own, posthoc] = rows(html);
    assert.equal(own, '<li class="mp-outline-row"><input aria-label="Triangulation"/>'
        + '<button type="button" class="mp-outline-link" aria-label="Triangulation"><span class="mp-outline-number">2</span>Triangulation</button>'
        + '<span class="mp-outline-state"><span data-state="on"></span></span></li>');
    // The stage beside it brings neither, so the same outline draws its posthoc switch and outcome from the store.
    assert.match(posthoc, /^<li class="mp-outline-row"><input type="checkbox" class="mp-stage-toggle" aria-label="Gap filling and filtering"[^>]*\/><button /);
    assert.match(posthoc, /<\/button><span class="mp-outline-state">[^<]+<\/span><\/li>$/);
});

test('a list section header draws the own switch too', () => {
    const posthoc: ProcessingSection = {id: 'triangulation', number: 2, title: 'Triangulation', stage: 'triangulation', summary: null, content: null};
    const header = (section: ProcessingSection): string => renderToStaticMarkup(<Provider store={store}>
        <StageSection section={section} playback>{null}</StageSection>
    </Provider>).match(/<div class="settings-section-header mp-section-header">.*?<\/div>/)?.[0] ?? '';
    const own = header({...posthoc, toggle: <input aria-label="Triangulation"/>});
    assert.ok(own.startsWith('<div class="settings-section-header mp-section-header"><input aria-label="Triangulation"/><button type="button" class="mp-section-title"'), own);
    assert.equal(own.match(/<input/g)?.length, 1, own);
    // Without one, the header draws the posthoc stage switch from the store.
    assert.match(header(posthoc), /^<div class="settings-section-header mp-section-header"><input type="checkbox" class="mp-stage-toggle" aria-label="Triangulation"[^>]*\/><button /);
});

test('items and key rows render only with controls', () => {
    const sections: ProcessingSection<'observations'>[] = [
        {id: 'observations', number: 1, title: '2D tracking', stage: null, summary: null, content: null, quick: <div data-quick="observations"/>,
            items: [{id: 'person', title: 'Person', toggle: <input aria-label="Person"/>, quick: <div data-quick="person"/>}]},
    ];
    const section = '<li class="mp-outline-row"><button type="button" class="mp-outline-link" aria-label="2D tracking">'
        + '<span class="mp-outline-number">1</span>2D tracking</button></li>';
    const item = '<li class="mp-outline-row mp-outline-item"><input aria-label="Person"/>'
        + '<button type="button" class="mp-outline-link" aria-label="Person">Person</button></li>';
    const keyRows = (id: string): string => `<li class="mp-outline-controls settings-layout"><div data-quick="${id}"></div></li>`;
    const outline = renderToStaticMarkup(<ProcessingOutline sections={sections} active={null} playback={false} states={null} onPick={() => {}}/>);
    assert.deepEqual(rows(outline), [section, item]);
    const menu = renderToStaticMarkup(<ProcessingOutline sections={sections} active={null} playback={false} states={null} onPick={() => {}} controls/>);
    assert.deepEqual(rows(menu), [section, keyRows('observations'), item, keyRows('person')]);
});

test('after sections go under afterTitle', () => {
    const sections: ProcessingSection<'cameras' | 'vmc' | 'lsl'>[] = [
        {id: 'cameras', number: null, title: 'Cameras', stage: null, summary: null, content: null},
        {id: 'vmc', number: null, title: 'VMC', stage: null, summary: null, content: null, after: true},
        {id: 'lsl', number: null, title: 'LSL', stage: null, summary: null, content: null, after: true},
    ];
    const html = renderToStaticMarkup(<ProcessingOutline sections={sections} active="vmc" playback={false} states={null} onPick={() => {}}
        afterTitle="Streaming outputs" label="Realtime processing sections"/>);
    assert.ok(html.startsWith('<nav class="mp-outline" aria-label="Realtime processing sections">'), html);
    const [pipeline, after, ...more] = html.split('<span class="mp-outline-heading">Streaming outputs</span>');
    assert.ok(after !== undefined && more.length === 0, html);
    assert.deepEqual(rows(pipeline).map(row => row.match(/aria-label="([^"]+)"/)?.[1]), ['Cameras']);
    assert.deepEqual(rows(after).map(row => row.match(/aria-label="([^"]+)"/)?.[1]), ['VMC', 'LSL']);
    assert.ok(!html.includes('After processing'), html);
});
