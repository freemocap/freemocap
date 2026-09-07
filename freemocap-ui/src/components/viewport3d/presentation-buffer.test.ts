import assert from 'node:assert/strict';
import {test} from 'node:test';
import {PresentationBuffer} from './presentation-buffer';

test('missing observations expire without another incoming frame and fresh observations renew them', t => {
    t.mock.timers.enable({apis: ['setTimeout']});
    let now = 0;
    t.mock.method(performance, 'now', () => now);
    let visible: number[] = [];
    const buffer = new PresentationBuffer<number>(values => {visible = values;}, 1000);
    buffer.update([1, 2], String, Number.isFinite);
    now = 500;
    buffer.update([2], String, Number.isFinite);
    assert.deepEqual(visible, [1, 2]);
    now = 1000;
    t.mock.timers.tick(500);
    assert.deepEqual(visible, [2]);
    now = 1500;
    t.mock.timers.tick(500);
    assert.deepEqual(visible, []);
    buffer.update([3], String, Number.isFinite);
    buffer.clear();
    assert.deepEqual(visible, []);
});
