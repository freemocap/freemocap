export const DEFAULT_PLAYBACK_BYTES = 512 * 1024 ** 2;

export function choosePlaybackBudget(memory: {totalBytes: number; availableBytes: number}): number {
    if (!Number.isFinite(memory.totalBytes) || !Number.isFinite(memory.availableBytes)
        || memory.totalBytes <= 0 || memory.availableBytes < 0) throw new Error('Invalid system memory information');
    const gibibyte = 1024 ** 3;
    return memory.totalBytes >= 16 * gibibyte && memory.availableBytes >= 4 * gibibyte
        ? gibibyte : DEFAULT_PLAYBACK_BYTES;
}
