import {test} from 'node:test';
import assert from 'node:assert/strict';
import {FrameCadence} from './frame-cadence';
import {FramerateStore} from './framerate-store';

test('30 delivered frames remain 30 FPS despite duplicate callbacks and skipped capture IDs', () => {
    const cadence = new FrameCadence();
    for (let index = 0; index <= 30; index++) {
        cadence.record(index * 2, index * 1000 / 30);
        cadence.record(index * 2, index * 1000 / 30 + 16);
    }
    assert.ok(Math.abs(cadence.getFps(1000)! - 30) < 1e-8);
    assert.equal(cadence.getFps(2100), 0);
});

test('a short decode interval does not turn a 30 FPS stream into a 60 FPS counter', () => {
    const cadence = new FrameCadence();
    for (let index = 0; index <= 30; index++) {
        cadence.record(index, index * 1000 / 30 + (index % 2 ? 1000 / 60 : 0));
    }
    assert.ok(Math.abs(cadence.getFps(1000)! - 30) < 1e-8);
});

test('frontend statistics measure decoded groups locally and reset on disconnect', () => {
    const store = new FramerateStore();
    for (let index = 0; index <= 30; index++) {
        store.recordFrontendFrame(index * 4, index * 1000 / 15);
        store.recordFrontendFrame(index * 4, index * 1000 / 15 + 1);
    }
    const current = store.getSnapshot().currentFrontendFramerate!;
    assert.ok(Math.abs(current.mean_frames_per_second - 15) < 1e-8);
    assert.equal(current.calculation_window_size, 30);
    store.clear();
    assert.equal(store.getSnapshot().currentFrontendFramerate, null);
    store.recordFrontendFrame(0, 3000);
    store.recordFrontendFrame(1, 3100);
    assert.equal(store.getSnapshot().currentFrontendFramerate?.mean_frames_per_second, 10);
});
