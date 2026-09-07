import {test, expect} from '@playwright/test';
import {FrameLookahead} from '../src/services/recording/frame-lookahead';

test('lookahead is bounded and replenishes only consumed slots', async () => {
    const loaded: number[] = [];
    const released: number[] = [];
    const buffer = new FrameLookahead({start: 0, end: 10, capacity: 3,
        load: async (ordinal: number) => {loaded.push(ordinal); return ordinal;},
        release: (ordinal: number) => {released.push(ordinal);}});
    await buffer.fill();
    expect(loaded).toEqual([0, 1, 2]);
    expect(buffer.takeDue(0)).toBe(0);
    await buffer.fill();
    expect(loaded).toEqual([0, 1, 2, 3]);
    await buffer.close();
    expect(released).toEqual([1, 2, 3]);
});

test('closing lookahead releases a frame still being decoded', async () => {
    let finish: (value: number) => void = () => {throw new Error('Load not started');};
    const released: number[] = [];
    const buffer = new FrameLookahead({start: 0, end: 2, capacity: 2,
        load: () => new Promise<number>(resolve => {finish = resolve;}),
        release: (ordinal: number) => {released.push(ordinal);}});
    const filling = buffer.fill();
    const closing = buffer.close();
    finish(0);
    await Promise.all([filling, closing]);
    expect(buffer.size).toBe(0);
    expect(released).toEqual([0]);
});

test('catch-up drops prepared images without jumping the sequential decoder', async () => {
    const loaded: number[] = [];
    const released: number[] = [];
    const buffer = new FrameLookahead({start: 0, end: 10, capacity: 3,
        load: async (ordinal: number) => {loaded.push(ordinal); return ordinal;},
        release: (ordinal: number) => {released.push(ordinal);}});
    await buffer.fill();
    expect(buffer.takeDue(-1)).toBeUndefined();
    expect(buffer.takeDue(6)).toBe(2);
    expect(released).toEqual([0, 1]);
    await buffer.fill();
    expect(loaded).toEqual([0, 1, 2, 3, 4, 5]);
    expect(buffer.takeDue(3)).toBe(3);
    expect(buffer.takeDue(3)).toBeUndefined();
    await buffer.close();
    expect(released).toEqual([0, 1, 4, 5]);
});

test('empty-buffer catch-up cannot advance pending reads to unavailable future frames', async () => {
    let finish!: (value: number) => void;
    const loaded: number[] = [];
    const buffer = new FrameLookahead({start: 0, end: 10, capacity: 3,
        load: async (ordinal: number) => {
            loaded.push(ordinal);
            return ordinal === 0 ? new Promise<number>(resolve => {finish = resolve;}) : ordinal;
        }, release: () => {}});
    const filling = buffer.fill();
    expect(buffer.takeDue(5)).toBeUndefined();
    finish(0);
    await filling;
    expect(loaded).toEqual([0, 1, 2]);
    expect(buffer.takeDue(5)).toBe(2);
    expect(buffer.takeDue(5)).toBeUndefined();
    await buffer.close();
});
