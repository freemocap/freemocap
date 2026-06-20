// frame-processor.ts
//
// Manages the decode module worker. The worker parses the binary payload and
// decodes JPEG→ImageBitmap off the main thread, returning RAW bitmaps. Overlay
// compositing happens downstream in the per-camera canvas workers.

export interface FrameData {
    cameraId: string;
    cameraIndex: number;
    frameNumber: number;
    width: number;
    height: number;
    colorChannels: number;
    pixelBuffer: ArrayBuffer;
}

export interface ProcessedFrameResult {
    frames: FrameData[];
    cameraIds: Set<string>;
    frameNumbers: Set<number>;
}

/** Successful response from worker → main thread. */
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
    pixelBuffers: ArrayBuffer[];
}

/** Error response from worker → main thread. */
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
        this.worker = this.createWorker();
    }

    private createWorker(): Worker {
        const worker = new Worker(
            new URL("./frame-decode.worker.ts", import.meta.url),
            { type: "module" },
        );

        worker.onmessage = (e: MessageEvent<DecodeWorkerMessage>) => {
            this.handleWorkerMessage(e.data);
        };
        worker.onerror = (e: ErrorEvent) => {
            const error = new Error(`Frame decode worker error: ${e.message}`);
            for (const [, pending] of this.pendingRequests) {
                pending.reject(error);
            }
            this.pendingRequests.clear();
            throw error;
        };

        return worker;
    }

    private handleWorkerMessage(msg: DecodeWorkerMessage): void {
        const pending = this.pendingRequests.get(msg.requestId);
        if (!pending) {
            throw new Error(`Received response for unknown request ${msg.requestId}`);
        }
        this.pendingRequests.delete(msg.requestId);

        if (msg.type === 'error') {
            pending.reject(new Error(msg.message));
            return;
        }

        // Reassemble FrameData by zipping metadata + pixel buffers
        const frames: FrameData[] = msg.frameData.map((meta, i) => ({
            cameraId: meta.cameraId,
            cameraIndex: meta.cameraIndex,
            frameNumber: meta.frameNumber,
            width: meta.width,
            height: meta.height,
            colorChannels: meta.colorChannels,
            pixelBuffer: msg.pixelBuffers[i],
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

            // Transfer the ArrayBuffer to the worker (zero-copy).
            // After this, `data` is detached on the main thread.
            this.worker.postMessage({ type: 'decode', payload: data, requestId }, [data]);
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

        // Terminate and recreate the worker (re-applies visibility/schema).
        this.worker.terminate();
        this.worker = this.createWorker();
    }
}
