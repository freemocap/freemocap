import {ScheduledRenderer} from '../server/server-helpers/scheduled-renderer';
import type {PreparedImage} from '../server/server-helpers/render-protocol';
import {decode} from 'cbor-x';
import {FrameProcessor} from '../server/server-helpers/frame-processor/frame-processor';
import {PlaybackCommand, PlaybackEvent, PlaybackResolution, PLAYBACK_ENCODING, PlaybackMessage, type PlaybackLocation} from './playback-protocol';

export interface VideoEntry {videoId: string; filename: string; streamUrl: string; sizeBytes: number}
export interface PlaybackFrame {ordinal: number; image: PreparedImage; renderer: ScheduledRenderer}
export type GroupFrames = PlaybackFrame[];
export function releaseGroupFrames(frames: GroupFrames): void {frames.forEach(frame => frame.renderer.release(frame.image));}
interface PendingRead {resolve: (payload: Uint8Array) => void; reject: (error: Error) => void}
interface RequestedRange {generation: number; next: number; end: number; cancelled: boolean}

/** Client-owned range scheduling, compressed image residency and outstanding-byte reservations. */
export class ClientVideoGroup {
    private readonly socket: WebSocket;
    private readonly processor = new FrameProcessor();
    private readonly caches = new Map<PlaybackResolution, Map<number, Uint8Array>>([
        [PlaybackResolution.Preview, new Map()], [PlaybackResolution.Detail, new Map()],
    ]);
    private resolution = PlaybackResolution.Detail;
    private get cache(): Map<number, Uint8Array> {return this.caches.get(this.resolution)!;}
    private readonly waiting = new Map<number, PendingRead[]>();
    private incoming: Promise<void> = Promise.resolve();
    private failure: Error | null = null;
    private closed = false;
    private generation = 0;
    private active: RequestedRange | null = null;
    private frameCount = 0;
    private multiframeBytes = 0;
    private maximumPayloadBytes = 0;
    private decodeTail: Promise<void> = Promise.resolve();
    private focus = 0;
    private viewConfigured = false;
    private lookaheadFrames = 1;
    private allocatedBytes = 0;
    private resolveReady!: (count: number) => void;
    private rejectReady!: (error: Error) => void;
    readonly ready: Promise<number>;

    constructor(readonly videos: readonly VideoEntry[], private readonly budgetBytes: number, location: PlaybackLocation) {
        this.ready = new Promise((resolve, reject) => {this.resolveReady = resolve; this.rejectReady = reject;});
        this.socket = new WebSocket(location.socketUrl);
        this.socket.binaryType = 'arraybuffer';
        this.socket.onopen = (): void => this.socket.send(JSON.stringify({source: location.source,
            encoded_group_bytes: Math.min(budgetBytes, 128 * 1024 ** 2)}));
        this.socket.onmessage = (event: MessageEvent<ArrayBuffer>): void => {
            this.incoming = this.incoming.then(() => this.receive(event.data)).catch(error => this.fail(error));
        };
        this.socket.onerror = (): void => this.fail(new Error('Playback connection failed'));
        this.socket.onclose = (): void => {if (!this.closed) this.fail(new Error('Playback connection closed'));};
    }

    /** Presentation supplies its position and desired horizon, never a server allowance. */
    setView(frame: number, lookaheadFrames: number, resolution: PlaybackResolution): void {
        const encodingChanged = resolution !== this.resolution;
        this.resolution = resolution;
        this.viewConfigured = true;
        this.focus = frame;
        this.lookaheadFrames = Math.max(1, Math.floor(lookaheadFrames));
        for (const [ordinal, readers] of this.waiting) {
            if (encodingChanged || ordinal < frame || ordinal >= frame + this.lookaheadFrames) {
                readers.forEach(reader => reader.reject(new Error('Playback request superseded by a new view')));
                this.waiting.delete(ordinal);
            }
        }
        const range = this.active;
        if (range && !range.cancelled && (encodingChanged || range.next < frame || range.end > frame + this.lookaheadFrames
            || range.end <= frame)) {
            range.cancelled = true;
            this.socket.send(JSON.stringify({command: PlaybackCommand.Cancel, payload: {generation: range.generation}}));
        }
        this.schedule();
    }

    private schedule(): void {
        if (this.closed || !this.viewConfigured || !this.frameCount || this.active) return;
        const maxFrames = this.frameCount;
        const end = Math.min(this.frameCount, this.focus + Math.min(this.lookaheadFrames, maxFrames));
        let start = this.focus;
        while (start < end && this.cache.has(start)) start++;
        if (start >= end) return;
        let stop = start + 1;
        while (stop < end && !this.cache.has(stop)) stop++;
        // Reserve the enforced maximum wire size for every outstanding multiframe.
        stop = Math.min(stop, start + Math.floor(this.budgetBytes / this.maximumPayloadBytes));
        const reservedBytes = (stop - start) * this.maximumPayloadBytes;
        for (const [quality, cache] of this.caches) for (const [ordinal, frames] of cache) {
            if (this.allocatedBytes + reservedBytes <= this.budgetBytes) break;
            if (quality === this.resolution && ordinal >= this.focus && ordinal < start) continue;
            cache.delete(ordinal); this.allocatedBytes -= frames.byteLength;
        }
        stop = Math.min(stop, start + Math.floor((this.budgetBytes - this.allocatedBytes) / this.maximumPayloadBytes));
        if (stop <= start) return;
        this.active = {generation: ++this.generation, next: start, end: stop, cancelled: false};
        this.socket.send(JSON.stringify({command: PlaybackCommand.Range,
            payload: {generation: this.generation, start_frame: start, end_frame: stop, encoding: PLAYBACK_ENCODING[this.resolution]}}));
    }

    private async receive(data: ArrayBuffer): Promise<void> {
        if (this.closed) return;
        const message = PlaybackMessage.parse(decode(new Uint8Array(data)));
        switch (message.kind) {
            case PlaybackEvent.Ready:
                if (message.filenames.length !== this.videos.length
                    || message.filenames.some((name, index) => name !== this.videos[index].filename)) {
                    throw new Error('Playback media inventory changed; reload the recording');
                }
                this.multiframeBytes = message.decoded_group_bytes;
                this.maximumPayloadBytes = message.maximum_payload_bytes;
                if (this.budgetBytes < this.maximumPayloadBytes) throw new Error('JPEG cache cannot hold one multiframe payload');
                this.frameCount = message.frame_count;
                this.resolveReady(message.frame_count);
                this.schedule();
                return;
            case PlaybackEvent.Failed: throw new Error(message.detail);
            case PlaybackEvent.End:
                if (!this.active || message.generation !== this.active.generation) throw new Error('Unexpected playback range completion');
                if (!this.active.cancelled && this.active.next !== this.active.end) throw new Error('Playback range ended before all requested frames arrived');
                this.active = null;
                this.schedule();
                return;
            case PlaybackEvent.Frame: {
                const range = this.active;
                if (!range || message.generation !== range.generation) throw new Error('Unexpected playback range');
                if (message.frame_number !== range.next || message.frame_number >= range.end) throw new Error('Unexpected playback frame ordinal');
                range.next++;
                if (range.cancelled) return;
                const payload = message.image.slice();
                if (payload.byteLength > this.maximumPayloadBytes) throw new Error('Playback payload exceeds its reserved wire size');
                this.cache.set(message.frame_number, payload);
                this.allocatedBytes += payload.byteLength;
                const readers = this.waiting.get(message.frame_number) ?? [];
                this.waiting.delete(message.frame_number);
                readers.forEach(reader => reader.resolve(payload));
            }
        }
    }

    private async loadPayload(ordinal: number, resolution: PlaybackResolution): Promise<Uint8Array> {
        const count = await this.ready;
        if (this.failure) throw this.failure;
        if (this.closed) throw new Error('Playback source is closed');

        if (!Number.isSafeInteger(ordinal) || ordinal < 0 || ordinal >= count) throw new Error('Playback frame is outside the recording');
        const cache = this.caches.get(resolution)!;
        const payload = cache.get(ordinal);
        if (payload) {
            cache.delete(ordinal); cache.set(ordinal, payload);
            return payload;
        }
        if (resolution !== this.resolution) throw new Error('Playback encoding request superseded');
        if (!this.viewConfigured || ordinal < this.focus || ordinal >= this.focus + this.lookaheadFrames) this.setView(ordinal, this.lookaheadFrames, resolution);
        return new Promise<Uint8Array>((resolve, reject) => {
            const readers = this.waiting.get(ordinal) ?? [];
            readers.push({resolve, reject}); this.waiting.set(ordinal, readers);
            this.schedule();
        });
    }

    read(ordinal: number, resolution: PlaybackResolution, renderers: readonly ScheduledRenderer[]): Promise<GroupFrames> {
        const result = this.decodeTail.then(async () => {
            const payload = await this.loadPayload(ordinal, resolution);
            const decoded = await this.processor.processFramePayload(payload.slice().buffer);
            if (this.closed) throw new Error('Playback source closed');
            if (!decoded || decoded.frames.length !== this.videos.length) throw new Error('Incomplete playback multiframe');
            if (decoded.frames.reduce((bytes, frame) => bytes + frame.width * frame.height * 4, 0) > this.multiframeBytes) {
                throw new Error('Decoded multiframe dimensions differ from the presentation memory estimate');
            }
            decoded.frames.sort((a, b) => a.cameraIndex - b.cameraIndex);
            if (renderers.length !== decoded.frames.length) throw new Error('Missing playback camera renderers');
            const prepared = await Promise.allSettled(decoded.frames.map(async (frame, index): Promise<PlaybackFrame> => {
                if (frame.frameNumber !== ordinal || frame.cameraIndex !== index) throw new Error('Playback multiframe is not synchronized');
                const renderer = renderers[index];
                const image = await renderer.prepare(frame.pixelBuffer, frame.width, frame.height);
                return {ordinal, image, renderer};
            }));
            const frames = prepared.flatMap(result => result.status === 'fulfilled' ? [result.value] : []);
            const failure = prepared.find(result => result.status === 'rejected');
            if (failure || this.closed) {
                releaseGroupFrames(frames);
                throw failure?.reason ?? new Error('Playback source closed');
            }
            return frames;
        });
        this.decodeTail = result.then(() => undefined, () => undefined);
        return result;
    }

    async prefetch(ordinal: number, resolution: PlaybackResolution): Promise<void> {await this.loadPayload(ordinal, resolution);}

    hasCached(ordinal: number, resolution: PlaybackResolution): boolean {return this.caches.get(resolution)!.has(ordinal);}

    get cachedOrdinals(): number[] {return [...new Set([...this.caches.values()].flatMap(cache => [...cache.keys()]))].sort((a, b) => a - b);}
    get cachedBytes(): number {return this.allocatedBytes;}
    get frameCapacity(): number {return this.frameCount || 1;}
    get outstandingFrames(): number {return this.active ? this.active.end - this.active.next : 0;}

    private fail(cause: unknown): void {
        if (this.closed) return;
        this.failure = cause instanceof Error ? cause : new Error(String(cause));
        this.close();
    }

    close(): void {
        if (this.closed) return;
        this.closed = true;
        const error = this.failure ?? new Error('Playback source closed');
        this.rejectReady(error);
        for (const readers of this.waiting.values()) readers.forEach(reader => reader.reject(error));
        this.waiting.clear();
        this.socket.close(); this.processor.close();
        this.caches.forEach(cache => cache.clear()); this.allocatedBytes = 0;
    }
}
