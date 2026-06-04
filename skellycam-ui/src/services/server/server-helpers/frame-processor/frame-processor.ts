// frame-processor.ts
//
// Delegates binary payload parsing and JPEG→ImageBitmap decoding to a
// dedicated Web Worker so that all Blob allocations and createImageBitmap
// async work happen off the main thread.

import { frameDecodeWorkerCode } from "@/services/server/server-helpers/frame-processor/frame-decode.worker";

export interface FrameData {
    cameraId: string;
    cameraIndex: number;
    frameNumber: number;
    width: number;
    height: number;
    colorChannels: number;
    bitmap: ImageBitmap;
}

export interface ProcessedFrameResult {
    frames: FrameData[];
    cameraIds: Set<string>;
    frameNumbers: Set<number>;
}

/** Message sent from main thread → decode worker. */
interface DecodeRequest {
    type: 'decode';
    payload: ArrayBuffer;
    requestId: number;
}

/** Successful response from decode worker → main thread. */
interface DecodeResultMessage {
    type: 'result';
    requestId: number;
    frameData: Array<{
        cameraId: string;
        cameraIndex: number;
        frameNumber: number;
        width: number;
        height: number;
        colorChannels: number;
    }>;
    bitmaps: ImageBitmap[];
}

/** Error response from decode worker → main thread. */
interface DecodeErrorMessage {
    type: 'error';
    requestId: number;
    message: string;
}

type DecodeWorkerMessage = DecodeResultMessage | DecodeErrorMessage;

export class FrameProcessor {
    private lastFrameTime: Map<string, number> = new Map();
    private currentFps: Map<string, number> = new Map();

    private worker: Worker;
    private nextRequestId: number = 0;
    private pendingRequests: Map<number, {
        resolve: (result: ProcessedFrameResult | null) => void;
        reject: (error: Error) => void;
    }> = new Map();

    constructor() {
        const blob = new Blob([frameDecodeWorkerCode], { type: 'application/javascript' });
        const url = URL.createObjectURL(blob);
        this.worker = new Worker(url);
        URL.revokeObjectURL(url);

        this.worker.onmessage = (e: MessageEvent<DecodeWorkerMessage>) => {
            this.handleWorkerMessage(e.data);
        };

        this.worker.onerror = (e: ErrorEvent) => {
            const error = new Error(`Frame decode worker error: ${e.message}`);
            // Reject all pending requests so callers don't hang
            for (const [, pending] of this.pendingRequests) {
                pending.reject(error);
            }
            this.pendingRequests.clear();
            throw error;
        };
    }

    private handleWorkerMessage(msg: DecodeWorkerMessage): void {
        const pending = this.pendingRequests.get(msg.requestId);
        if (!pending) {
            // Clean up any bitmaps in orphaned result messages
            if (msg.type === 'result') {
                for (const bitmap of msg.bitmaps) {
                    bitmap.close();
                }
            }
            throw new Error(`Received response for unknown request ${msg.requestId}`);
        }
        this.pendingRequests.delete(msg.requestId);

        if (msg.type === 'error') {
            pending.reject(new Error(msg.message));
            return;
        }

        // Reassemble FrameData by zipping metadata + bitmaps
        const frames: FrameData[] = msg.frameData.map((meta, i) => ({
            cameraId: meta.cameraId,
            cameraIndex: meta.cameraIndex,
            frameNumber: meta.frameNumber,
            width: meta.width,
            height: meta.height,
            colorChannels: meta.colorChannels,
            bitmap: msg.bitmaps[i],
        }));

        const cameraIds = new Set<string>();
        const frameNumbers = new Set<number>();

        for (const frame of frames) {
            cameraIds.add(frame.cameraId);
            frameNumbers.add(frame.frameNumber);

            // Track frame timing and calculate FPS on the main thread
            const now = performance.now();
            const lastTime = this.lastFrameTime.get(frame.cameraId);
            if (lastTime) {
                const fps = 1000 / (now - lastTime);
                this.currentFps.set(frame.cameraId, fps);
            }
            this.lastFrameTime.set(frame.cameraId, now);
        }

        pending.resolve({ frames, cameraIds, frameNumbers });
    }

    public processFramePayload(data: ArrayBuffer): Promise<ProcessedFrameResult | null> {
        return new Promise((resolve, reject) => {
            const requestId = this.nextRequestId++;
            this.pendingRequests.set(requestId, { resolve, reject });

            const msg: DecodeRequest = { type: 'decode', payload: data, requestId };
            // Transfer the ArrayBuffer to the worker (zero-copy).
            // After this, `data` is detached on the main thread.
            this.worker.postMessage(msg, [data]);
        });
    }

    public getFps(cameraId: string): number | null {
        return this.currentFps.get(cameraId) ?? null;
    }

    public reset(): void {
        this.lastFrameTime.clear();
        this.currentFps.clear();

        // Reject any pending requests
        for (const [, pending] of this.pendingRequests) {
            pending.reject(new Error('FrameProcessor reset'));
        }
        this.pendingRequests.clear();

        // Terminate and recreate the worker
        this.worker.terminate();

        const blob = new Blob([frameDecodeWorkerCode], { type: 'application/javascript' });
        const url = URL.createObjectURL(blob);
        this.worker = new Worker(url);
        URL.revokeObjectURL(url);

        this.worker.onmessage = (e: MessageEvent<DecodeWorkerMessage>) => {
            this.handleWorkerMessage(e.data);
        };

        this.worker.onerror = (e: ErrorEvent) => {
            const error = new Error(`Frame decode worker error: ${e.message}`);
            for (const [, pending] of this.pendingRequests) {
                pending.reject(error);
            }
            this.pendingRequests.clear();
            throw error;
        };
    }
}
