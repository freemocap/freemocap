import {test, expect} from '@playwright/test';
import {PlaybackClock} from '../src/services/recording/playback-clock';

test('playback position follows elapsed time and selected speed despite missed presentations', () => {
    const clock = new PlaybackClock(12, 1000, 60);
    expect(clock.frameAt(1000)).toBe(12);
    clock.presented(1100);
    expect(clock.frameAt(1500)).toBe(42);
    expect(clock.frameAt(2000)).toBe(72);
});

test('display rate counts completed presentations, including stalls, not ordinal distance', () => {
    const clock = new PlaybackClock(0, 0, 30);
    expect(clock.displayFps(0)).toBeNull();
    for (const time of [100, 200, 400, 800]) clock.presented(time);
    expect(clock.displayFps(1000)).toBe(4);
    expect(clock.displayFps(1500)).toBe(1);
    expect(clock.displayFps(2000)).toBe(0);
});

test('resuming after starvation rebases position without hiding stalled display FPS', () => {
    const clock = new PlaybackClock(0, 0, 30);
    clock.presented(100);
    expect(clock.frameAt(1000)).toBe(30);
    clock.resumeAt(4, 1000);
    expect(clock.frameAt(1000)).toBe(4);
    expect(clock.frameAt(1500)).toBe(19);
    expect(clock.displayFps(1000)).toBe(1);
});
