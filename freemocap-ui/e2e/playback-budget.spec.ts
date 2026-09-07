import {test, expect} from '@playwright/test';
import {choosePlaybackBudget} from '../src/services/recording/playback-budget';

const gibibyte = 1024 ** 3;
test('playback memory grows with resources without exceeding physical or available RAM limits', () => {
    for (const totalGiB of [4, 8, 16, 32, 64]) for (const availableGiB of [0.5, 1, 2, 4]) {
        const totalBytes = totalGiB * gibibyte;
        const availableBytes = availableGiB * gibibyte;
        const budget = choosePlaybackBudget({totalBytes, availableBytes});
        expect(budget).toBeLessThanOrEqual(totalBytes / 16);
        expect(budget).toBeLessThanOrEqual(availableBytes / 4);
        expect(budget).toBeLessThanOrEqual(2 * gibibyte);
    }
    expect(choosePlaybackBudget({totalBytes: 32 * gibibyte, availableBytes: 16 * gibibyte})).toBe(2 * gibibyte);
});
test('memory exhaustion and invalid OS readings fail explicitly', () => {
    for (const availableBytes of [0, -1, NaN, Infinity, 9 * gibibyte]) {
        expect(() => choosePlaybackBudget({totalBytes: 8 * gibibyte, availableBytes})).toThrow();
    }
});
