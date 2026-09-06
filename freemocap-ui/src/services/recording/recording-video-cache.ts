import {ClientVideoGroup, type VideoEntry, type VideoCacheBudget} from './client-video-group';

/** Lazily retains source groups within a recording-wide allocation. */
export class RecordingVideoCache {
    private readonly groups = new Map<string, ClientVideoGroup>();
    private readonly budget: VideoCacheBudget;
    private readonly files = new Map<string, Promise<File>>();
    private readonly abort = new AbortController();
    private allocatedVideos = 0;
    private closed = false;
    constructor(private readonly videoCount: number, totalBytes: number) {
        if (!Number.isSafeInteger(videoCount) || videoCount < 1) throw new Error('Recording has no media cache slots');
        this.budget = {decodedBytes: Math.floor(totalBytes / 4 / videoCount),
            encodedBytes: Math.floor(totalBytes / 2 / videoCount)};
    }
    getGroup(videos: readonly VideoEntry[]): ClientVideoGroup {
        if (this.closed) throw new Error('Recording cache is closed');
        const key = JSON.stringify(videos);
        const existing = this.groups.get(key);
        if (existing) return existing;
        if (!videos.length || this.allocatedVideos + videos.length > this.videoCount) {
            throw new Error('Video selection exceeds the recording media inventory');
        }
        const group = new ClientVideoGroup(videos, this.budget, video => this.loadFile(video));
        this.groups.set(key, group);
        this.allocatedVideos += videos.length;
        return group;
    }
    private loadFile(video: VideoEntry): Promise<File | null> {
        if (!Number.isSafeInteger(video.sizeBytes) || video.sizeBytes <= 0) throw new Error('Invalid video byte length');
        if (video.sizeBytes > this.budget.encodedBytes) return Promise.resolve(null);
        const existing = this.files.get(video.streamUrl);
        if (existing) return existing;
        if (this.files.size >= this.videoCount) throw new Error('Media download exceeds recording inventory');
        const loading = (async (): Promise<File> => {
            const response = await fetch(video.streamUrl, {signal: this.abort.signal});
            if (!response.ok) throw new Error(`Video download failed: ${response.status} ${video.filename}`);
            if (Number(response.headers.get('Content-Length')) !== video.sizeBytes) {
                await response.body?.cancel();
                throw new Error(`Video size changed: ${video.filename}; refresh the recording`);
            }
            const blob = await response.blob();
            if (blob.size !== video.sizeBytes) throw new Error(`Video size changed: ${video.filename}; refresh the recording`);
            return new File([blob], video.filename);
        })();
        this.files.set(video.streamUrl, loading);
        return loading;
    }
    async prefetch(videos: readonly VideoEntry[], shouldContinue: () => boolean): Promise<void> {
        for (const video of videos) {
            if (this.closed || !shouldContinue()) return;
            await this.loadFile(video);
        }
    }
    close(): void {
        this.closed = true;
        this.abort.abort();
        this.files.clear();
        this.groups.forEach(group => group.close());
        this.groups.clear();
    }
}
