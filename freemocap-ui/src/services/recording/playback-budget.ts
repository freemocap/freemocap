export const DEFAULT_PLAYBACK_BYTES = 512 * 1024 ** 2;
export const MAX_PRESENTATION_BYTES = 256 * 1024 ** 2;

/** Reserve headroom for capture, inference, the viewport and native image allocations. */
export function choosePlaybackBudget(memory: {totalBytes: number; availableBytes: number}): number {
    if (!Number.isFinite(memory.totalBytes) || !Number.isFinite(memory.availableBytes)
        || memory.totalBytes <= 0 || memory.availableBytes < 0 || memory.availableBytes > memory.totalBytes) {
        throw new Error('Invalid system memory information');
    }
    const budget = Math.floor(Math.min(2 * 1024 ** 3, memory.totalBytes / 16, memory.availableBytes / 4));
    if (budget < 64 * 1024 ** 2) throw new Error('Insufficient available memory for playback: close other applications and reopen playback');
    return budget;
}
