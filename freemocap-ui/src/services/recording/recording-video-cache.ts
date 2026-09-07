import {ClientVideoGroup, type VideoEntry} from './client-video-group';
import {PlaybackSource} from './playback-protocol';

/** Retains raw and annotated JPEG payloads within one recording allocation. */
export class RecordingVideoCache {
    private readonly groups = new Map<PlaybackSource, ClientVideoGroup>();
    constructor(private readonly socketUrl: string, private readonly sourceCount: number, private readonly totalBytes: number) {}
    getGroup(videos: readonly VideoEntry[], source: PlaybackSource): ClientVideoGroup {
        const existing = this.groups.get(source);
        if (existing) return existing;
        const group = new ClientVideoGroup(videos, Math.floor(this.totalBytes * 3 / 4 / this.sourceCount), {socketUrl: this.socketUrl, source});
        this.groups.set(source, group);
        return group;
    }
    close(): void {this.groups.forEach(group => group.close()); this.groups.clear();}
}
