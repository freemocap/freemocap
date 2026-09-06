export interface VideoGrid {name: string; frameCount: number}

export function validateVideoGroup(videos: readonly VideoGrid[]): number {
    const first = videos[0];
    if (!first) throw new Error('Select at least one video');
    for (const video of videos) {
        if (!Number.isSafeInteger(video.frameCount) || video.frameCount <= 0) throw new Error(`Invalid frame count: ${video.name}`);
        if (video.frameCount !== first.frameCount) throw new Error(`Frame count mismatch: ${first.name} has ${first.frameCount}; ${video.name} has ${video.frameCount}. Synchronize videos before loading.`);
    }
    return first.frameCount;
}
