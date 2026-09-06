/** Bounded browser experiment; not a production media loader. */
import {DecodedFrameCache} from './decoded-frame-cache';

export interface DecoderPrototypeResult {
    codec: string;
    decodedFrames: number;
    cacheHits: number;
    cacheBytes: number;
    restartVerified: boolean;
}

export async function runDecoderPrototype(): Promise<DecoderPrototypeResult> {
    const width = 64;
    const height = 48;
    const count = 24;
    const config: VideoEncoderConfig = {codec: 'vp8', width, height, bitrate: 2_000_000, framerate: 30};
    if (!(await VideoEncoder.isConfigSupported(config)).supported) {
        throw new Error('Prototype VP8 encoder is unsupported in this runtime');
    }
    const packets: EncodedVideoChunk[] = [];
    let failure: Error | null = null;
    const encoder = new VideoEncoder({output: chunk => packets.push(chunk), error: error => {failure = error;}});
    const canvas = new OffscreenCanvas(width, height);
    const context = canvas.getContext('2d');
    if (!context) throw new Error('Prototype requires a 2D canvas');
    try {
        encoder.configure(config);
        for (let ordinal = 0; ordinal < count; ordinal++) {
            // Large grayscale steps let us verify decoded image identity despite lossy compression.
            const level = ordinal * 10;
            context.fillStyle = `rgb(${level}, ${level}, ${level})`;
            context.fillRect(0, 0, width, height);
            const frame = new VideoFrame(canvas, {timestamp: Math.round(ordinal * 1_000_000 / 30)});
            try { encoder.encode(frame, {keyFrame: ordinal === 0}); } finally { frame.close(); }
        }
        await encoder.flush();
        if (failure) throw failure;
    } finally { if (encoder.state !== 'closed') encoder.close(); }

    const cache = new DecodedFrameCache(width * height * 4 * 8);
    const decode = async (): Promise<number> => {
        let ordinal = 0;
        let decodeFailure: Error | null = null;
        const copies: Promise<void>[] = [];
        const decoder = new VideoDecoder({
            error: error => {decodeFailure = error;},
            output: frame => {
                const frameNumber = ordinal++;
                const timestamp = frame.timestamp;
                // Release decoder-owned surfaces promptly; retained cache images own their storage.
                copies.push(createImageBitmap(frame).then(bitmap => {
                    if (timestamp !== Math.round(frameNumber * 1_000_000 / 30)) {
                        bitmap.close();
                        throw new Error(`Presentation order mismatch at frame ${frameNumber}`);
                    }
                    context.drawImage(bitmap, 0, 0);
                    const level = context.getImageData(0, 0, 1, 1).data[0];
                    if (Math.abs(level - frameNumber * 10) > 4) {
                        bitmap.close();
                        throw new Error(`Decoded image identity mismatch at frame ${frameNumber}`);
                    }
                    cache.put(frameNumber, bitmap);
                }));
                frame.close();
            },
        });
        try {
            const decoderConfig: VideoDecoderConfig = {codec: config.codec};
            if (!(await VideoDecoder.isConfigSupported(decoderConfig)).supported) {
                throw new Error('Prototype VP8 decoder is unsupported in this runtime');
            }
            decoder.configure(decoderConfig);
            for (const packet of packets) decoder.decode(packet);
            await decoder.flush();
            await Promise.all(copies);
            if (decodeFailure) throw decodeFailure;
            if (ordinal !== count) throw new Error(`Expected ${count} frames, decoded ${ordinal}`);
            return ordinal;
        } finally {
            await Promise.allSettled(copies);
            if (decoder.state !== 'closed') decoder.close();
        }
    };
    try {
        const decodedFrames = await decode();
        let cacheHits = 0;
        for (const ordinal of [23, 20, 22, 20]) {
            const bitmap = cache.get(ordinal);
            if (!bitmap) throw new Error(`Recent frame ${ordinal} was not cached`);
            context.drawImage(bitmap, 0, 0);
            if (Math.abs(context.getImageData(0, 0, 1, 1).data[0] - ordinal * 10) > 4) {
                throw new Error(`Cached image mismatch at ${ordinal}`);
            }
            cacheHits++;
        }
        if (cache.get(0)) throw new Error('Old frame was not evicted');
        cache.clear();
        await decode();
        return {codec: config.codec, decodedFrames, cacheHits, cacheBytes: cache.sizeBytes, restartVerified: true};
    } finally { cache.clear(); }
}
