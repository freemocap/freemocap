// Run: node src/components/realtime-processing/run-realtime-processing-tests.mjs
import assert from 'node:assert/strict';
import {test} from 'node:test';
import {renderToStaticMarkup} from 'react-dom/server';
import Checkbox from './Checkbox';

/** The opening tag of the checkbox's `<input>`, the element the new props act on. */
const inputTag = (html: string) => html.match(/<input[^>]*>/)?.[0] ?? '';

test('names an unlabelled box', () => {
    const html = renderToStaticMarkup(<Checkbox label="" ariaLabel="Person" checked onChange={() => {}}/>);
    assert.ok(inputTag(html).includes('aria-label="Person"'), html);
});

test('marks a partly-on box as mixed', () => {
    const html = renderToStaticMarkup(<Checkbox label="" ariaLabel="2D tracking" indeterminate onChange={() => {}}/>);
    assert.ok(inputTag(html).includes('aria-checked="mixed"'), html);
});

test('keeps the labelled box unchanged', () => {
    const html = renderToStaticMarkup(<Checkbox label="Remember" checked onChange={() => {}}/>);
    assert.ok(html.includes('>Remember</p>'), html);
    assert.ok(!html.includes('aria-label='), html);
    assert.ok(!html.includes('aria-checked='), html);
});
