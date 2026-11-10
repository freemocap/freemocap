// Run: node src/components/realtime-processing/run-realtime-processing-tests.mjs
import assert from 'node:assert/strict';
import {test} from 'node:test';
import {renderToStaticMarkup} from 'react-dom/server';
import ValueSelector from './ValueSelector';

/** The opening tag of the number field. */
const inputTag = (html: string) => html.match(/<input[^>]*>/)?.[0] ?? '';
/** The opening tag of the stepper button with this accessible name. */
const stepperTag = (html: string, name: string) =>
    (html.match(/<button[^>]*>/g) ?? []).find(tag => tag.includes(`aria-label="${name}"`)) ?? '';
const STEPPERS = ['Decrease Minimum cutoff', 'Increase Minimum cutoff'];

test('an empty field shows no value', () => {
    const empty = renderToStaticMarkup(<ValueSelector value={3} min={0} max={10} empty ariaLabel="Minimum cutoff"/>);
    assert.ok(inputTag(empty).includes('placeholder="—"'), empty);
    assert.ok(inputTag(empty).includes('value=""'), empty);
    for (const name of STEPPERS) assert.ok(stepperTag(empty, name).includes('disabled=""'), `${name}: ${empty}`);

    const filled = renderToStaticMarkup(<ValueSelector value={3} min={0} max={10} ariaLabel="Minimum cutoff"/>);
    assert.ok(inputTag(filled).includes('value="3"'), filled);
    assert.ok(!filled.includes('placeholder='), filled);
    for (const name of STEPPERS) {
        assert.notEqual(stepperTag(filled, name), '', `${name}: ${filled}`);
        assert.ok(!stepperTag(filled, name).includes('disabled'), `${name}: ${filled}`);
    }
});
