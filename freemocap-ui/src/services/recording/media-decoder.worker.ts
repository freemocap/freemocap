import {ALL_FORMATS, BlobSource, UrlSource, Input, VideoSampleSink, type VideoSample} from 'mediabunny';
import {DecodedFrameCache} from './decoded-frame-cache';
import {DecoderCommand, DecoderReply, type DecoderRequest, type DecoderResponse} from './media-decoder-protocol';

let input: Input | null = null;
let sink: VideoSampleSink | null = null;
let iterator: AsyncGenerator<VideoSample, void, unknown> | null = null;
let cache: DecodedFrameCache | null = null;
let ordinal = -1;
let decoded = 0;
let restarts = 0;
let budget = 0;
const surface = new OffscreenCanvas(1, 1);
const context = surface.getContext('2d');
if (!context) throw new Error('Worker canvas is unavailable');

function reply(message: DecoderResponse, transfer: Transferable[] = []): void {
    self.postMessage(message, {transfer});
}

async function dispose(): Promise<void> {
    try { await iterator?.return(); } finally {
        iterator = null;
        cache?.clear(); cache = null;
        input?.dispose(); input = null; sink = null;
    }
}

async function handle(request: DecoderRequest): Promise<void> {
    if (request.kind !== DecoderCommand.Read) {
        await dispose();
        budget = request.budgetBytes;
        cache = new DecodedFrameCache(budget);
        input = new Input({source: request.kind === DecoderCommand.Open
            ? new BlobSource(request.file)
            : new UrlSource(request.url, {maxCacheSize: request.encodedBudgetBytes, getRetryDelay: () => null}), formats: ALL_FORMATS});
        const track = await input.getPrimaryVideoTrack();
        if (!track) throw new Error('This file contains no video track');
        if (!await track.canDecode()) throw new Error(`Video codec ${track.codec} is unsupported by this Electron runtime`);
        sink = new VideoSampleSink(track);
        // Prototype preflight counts decoded frames rather than compressed packets.
        let frameCount = 0;
        let firstTime = 0;
        let endTime = 0;
        for await (const sample of sink.samples()) {
            try {
                if (!frameCount) firstTime = sample.timestamp;
                endTime = sample.timestamp + sample.duration;
                frameCount++;
            } finally { sample.close(); }
        }
        const fps = frameCount / (endTime - firstTime);
        if (!frameCount || !Number.isFinite(fps) || fps <= 0) throw new Error('Invalid video frame grid');
        iterator = sink.samples();
        ordinal = -1; decoded = 0; restarts = 0;
        reply({kind: DecoderReply.Ready, codec: track.codec ?? 'unknown', frameCount, fps});
        return;
    }
    if (!Number.isSafeInteger(request.ordinal) || request.ordinal < 0) throw new Error('Invalid frame ordinal');
    if (!sink || !iterator || !cache) throw new Error('Open a video before reading frames');
    const cached = cache.get(request.ordinal);
    if (!cached && request.ordinal <= ordinal) {
        await iterator.return();
        iterator = sink.samples();
        ordinal = -1;
        restarts++;
    }
    while (!cached && ordinal < request.ordinal) {
        const next = await iterator.next();
        if (next.done) throw new Error(`Video ends before frame ${request.ordinal}`);
        const sample = next.value;
        try {
            if (sample.displayWidth * sample.displayHeight * 4 > budget) {
                throw new Error('A single decoded frame exceeds this prototype cache budget');
            }
            surface.width = sample.displayWidth; surface.height = sample.displayHeight;
            sample.draw(context!, 0, 0);
            cache.put(++ordinal, surface.transferToImageBitmap());
            decoded++;
        } finally { sample.close(); }
    }
    const image = cached ?? cache.get(request.ordinal);
    if (!image) throw new Error('Requested frame is missing from the cache');
    // Transfer a copy so the worker retains its cached frame for subsequent reads.
    const bitmap = await createImageBitmap(image);
    reply({kind: DecoderReply.Frame, ordinal: request.ordinal, bitmap, cacheHit: !!cached,
        decoded, restarts, cacheBytes: cache.sizeBytes}, [bitmap]);
}

// Serialize decoder access. A failed request closes the media; opening another file can recover.
let pending = Promise.resolve();
self.onmessage = (event: MessageEvent<DecoderRequest>): void => {
    pending = pending.then(() => handle(event.data)).catch(async (error: unknown) => {
        try { await dispose(); } finally {
            reply({kind: DecoderReply.Error, message: String(error)});
        }
    });
};
