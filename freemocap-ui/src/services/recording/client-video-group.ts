import {DecoderCommand, DecoderReply, type DecoderRequest, type DecoderResponse} from './media-decoder-protocol';
import {validateVideoGroup} from './synchronized-video-group';

export type GroupFrames = Extract<DecoderResponse, {kind: DecoderReply.Frame}>[];
export interface VideoCacheBudget {decodedBytes: number; encodedBytes: number}
export interface VideoEntry {videoId: string; filename: string; streamUrl: string; sizeBytes: number}
export function releaseGroupFrames(frames: GroupFrames): void {frames.forEach(frame => frame.bitmap.close());}

class DecoderClient {
    private readonly worker = new Worker(new URL('./media-decoder.worker.ts', import.meta.url), {type: 'module'});
    private pending: {resolve: (response: DecoderResponse) => void; reject: (error: Error) => void} | null = null;
    private closed = false;
    constructor() {
        this.worker.onmessage = (event: MessageEvent<DecoderResponse>): void => {
            const pending = this.pending; this.pending = null;
            if (!pending) {if (event.data.kind === DecoderReply.Frame) event.data.bitmap.close(); return;}
            if (event.data.kind === DecoderReply.Error) pending.reject(new Error(event.data.message));
            else pending.resolve(event.data);
        };
        this.worker.onerror = (event): void => {this.pending?.reject(new Error(event.message)); this.pending = null;};
    }
    request(message: DecoderRequest): Promise<DecoderResponse> {
        if (this.closed || this.pending) throw new Error('Decoder is closed or busy');
        return new Promise((resolve, reject) => {this.pending = {resolve, reject}; this.worker.postMessage(message);});
    }
    close(): void {
        this.closed = true; this.worker.terminate();
        this.pending?.reject(new Error('Video group closed')); this.pending = null;
    }
}

/** Owns one decoder per input. Group reads serialize; presentation owns returned images. */
export class ClientVideoGroup {
    private readonly clients: DecoderClient[];
    private tail: Promise<void> = Promise.resolve();
    private closed = false;
    readonly ready: Promise<number>;
    constructor(readonly videos: readonly VideoEntry[], private readonly budget: VideoCacheBudget, private readonly loadFile: (video: VideoEntry) => Promise<File | null>) {
        this.clients = videos.map(() => new DecoderClient());
        this.ready = this.open();
    }
    private async open(): Promise<number> {
        try {
            const grids = await Promise.all(this.clients.map(async (client, index) => {
                const file = await this.loadFile(this.videos[index]);
                const response = await client.request(file ? {kind: DecoderCommand.Open, file, budgetBytes: this.budget.decodedBytes} : {kind: DecoderCommand.OpenUrl,
                    url: this.videos[index].streamUrl,
                    budgetBytes: this.budget.decodedBytes,
                    encodedBudgetBytes: this.budget.encodedBytes});
                if (response.kind !== DecoderReply.Ready) throw new Error('Expected video metadata');
                return {name: this.videos[index].filename, frameCount: response.frameCount};
            }));
            return validateVideoGroup(grids);
        } catch (error) {this.close(); throw error;}
    }
    read(ordinal: number): Promise<GroupFrames> {
        const result = this.tail.then(async () => {
            await this.ready;
            if (this.closed) throw new Error('Video group closed');
            const results = await Promise.allSettled(this.clients.map(client => client.request({kind: DecoderCommand.Read, ordinal})));
            const frames = results.flatMap(result => result.status === 'fulfilled' && result.value.kind === DecoderReply.Frame ? [result.value] : []);
            const failed = results.find(result => result.status === 'rejected');
            if (failed?.status === 'rejected' || frames.length !== this.clients.length || frames.some(frame => frame.ordinal !== ordinal)) {
                releaseGroupFrames(frames);
                this.close();
                throw failed?.status === 'rejected' ? failed.reason : new Error('Incomplete video frame group');
            }
            return frames;
        });
        // The returned promise reports failure; this tail only serializes subsequent callers.
        this.tail = result.then(() => undefined, () => undefined);
        return result;
    }
    close(): void {this.closed = true; this.clients.forEach(client => client.close());}
}
