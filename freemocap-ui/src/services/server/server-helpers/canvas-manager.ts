import {workerCode} from "@/services/server/server-helpers/offscreen-renderer.worker";

export type FrameTimingMeta = {
    frameNumber: number;
    /** Main-thread performance.now() at start of the rAF body that kicked off decode for this frame. */
    rafCycleStartMs?: number;
};

/** renderAck is handled on the window thread; completedAt is window performance.now() (not worker time). */
export type RenderAckPayload = {
    cameraId: string;
    frameNumber: number;
    renderMs: number;
    completedAt: number;
    rafCycleStartMs?: number;
    canvasWorkerRafWaitMs?: number;
    canvasWorkerReceiveLagMs?: number;
    /** Main thread only: performance.now() − MessageEvent.timeStamp when the ack is handled (do not subtract worker clocks). */
    renderAckDeliveryMs?: number;
};

export interface CanvasWorker {
    worker: Worker;
    canvas: HTMLCanvasElement;
    initialized: boolean;
}

export class CanvasManager {
    private workers: Map<string, CanvasWorker> = new Map();
    private workerErrors: Map<string, number> = new Map();
    private pendingCanvases: Map<string, HTMLCanvasElement> = new Map();
    private readonly maxWorkerErrors: number = 3;
    private onRenderAck: ((payload: RenderAckPayload) => void) | null = null;

    setRenderAckHandler(handler: ((payload: RenderAckPayload) => void) | null): void {
        this.onRenderAck = handler;
    }

    /**
     * Set or update the canvas for a camera.
     * Only creates a new worker if one doesn't exist or if the canvas has changed.
     */
    public setCanvasForCamera(cameraId: string, canvas: HTMLCanvasElement): boolean {
        // Check if this exact canvas is already set up
        const existing = this.workers.get(cameraId);
        if (existing?.canvas === canvas && existing.initialized) {
            return true;
        }

        // Check if this is a different canvas for the same camera
        if (existing && existing.canvas !== canvas) {
            console.log(`Canvas changed for camera ${cameraId}, recreating worker`);
            this.terminateWorker(cameraId);
        }

        // Store pending canvas in case we need to retry
        this.pendingCanvases.set(cameraId, canvas);

        try {
            const worker = this.createWorker(cameraId);
            const offscreen = canvas.transferControlToOffscreen();

            worker.postMessage(
                { type: 'init', canvas: offscreen, cameraId },
                [offscreen]
            );

            this.workers.set(cameraId, {
                worker,
                canvas,
                initialized: true
            });

            // Reset error count on successful creation
            this.workerErrors.delete(cameraId);
            this.pendingCanvases.delete(cameraId);

            console.log(`Worker created for camera ${cameraId}`);
            return true;

        } catch (error) {
            console.error(`Failed to create worker for camera ${cameraId}:`, error);
            this.recordWorkerError(cameraId);
            return false;
        }
    }

    /**
     * Send a frame to a worker. Creates the worker if it doesn't exist yet.
     */
    public sendFrameToWorker(cameraId: string, bitmap: ImageBitmap, meta?: FrameTimingMeta): boolean {
        const workerInfo = this.workers.get(cameraId);

        if (!workerInfo?.initialized) {
            // Check if we have a pending canvas we can use
            const pendingCanvas = this.pendingCanvases.get(cameraId);
            if (pendingCanvas) {
                console.log(`Worker not ready for ${cameraId}, attempting to create from pending canvas`);
                if (this.setCanvasForCamera(cameraId, pendingCanvas)) {
                    // Try sending again after creation
                    return this.sendFrameToWorker(cameraId, bitmap, meta);
                }
            }

            console.warn(`No initialized worker for camera ${cameraId}, dropping frame`);
            bitmap.close();
            return false;
        }

        try {
            const mainSentAtMs = performance.now();
            workerInfo.worker.postMessage(
                {
                    type: 'frame',
                    bitmap,
                    frameNumber: meta?.frameNumber ?? -1,
                    rafCycleStartMs: meta?.rafCycleStartMs ?? 0,
                    mainSentAtMs,
                },
                [bitmap]
            );
            return true;
        } catch (error) {
            console.error(`Failed to send frame to worker ${cameraId}:`, error);
            bitmap.close();
            this.recordWorkerError(cameraId);
            return false;
        }
    }

    /**
     * Terminate a worker for a specific camera
     */
    public terminateWorker(cameraId: string): void {
        const workerInfo = this.workers.get(cameraId);
        if (workerInfo) {
            try {
                workerInfo.worker.terminate();
                console.log(`Worker terminated for camera ${cameraId}`);
            } catch (error) {
                console.error(`Error terminating worker for ${cameraId}:`, error);
            }
            this.workers.delete(cameraId);
        }

        // Also clean up any pending canvas
        this.pendingCanvases.delete(cameraId);
    }

    /**
     * Terminate all workers
     */
    public terminateAllWorkers(): void {
        console.log(`Terminating all workers (${this.workers.size} active)`);
        for (const [cameraId] of this.workers) {
            this.terminateWorker(cameraId);
        }
        this.workerErrors.clear();
        this.pendingCanvases.clear();
    }

    /**
     * Get list of active camera IDs
     */
    public getActiveCameraIds(): string[] {
        return Array.from(this.workers.keys());
    }

    /**
     * Check if a worker exists and is initialized for a camera
     */
    public hasWorker(cameraId: string): boolean {
        const worker = this.workers.get(cameraId);
        return worker?.initialized ?? false;
    }

    private createWorker(cameraId: string): Worker {
        const blob = new Blob([workerCode], { type: 'application/javascript' });
        const workerUrl = URL.createObjectURL(blob);

        try {
            const worker = new Worker(workerUrl);

            worker.onmessage = (ev: MessageEvent<{ type?: string } & Partial<RenderAckPayload & {
                workerRafWaitMs?: number;
                receiveLagMs?: number;
            }>>): void => {
                const d = ev.data;
                if (d?.type === 'renderAck' && this.onRenderAck && typeof d.cameraId === 'string') {
                    const completedAtMain = performance.now();
                    const evTs = ev.timeStamp;
                    const renderAckDeliveryMs =
                        typeof evTs === 'number' && evTs > 0 && Number.isFinite(evTs)
                            ? Math.max(0, completedAtMain - evTs)
                            : undefined;
                    this.onRenderAck({
                        cameraId: d.cameraId,
                        frameNumber: typeof d.frameNumber === 'number' ? d.frameNumber : -1,
                        renderMs: typeof d.renderMs === 'number' ? d.renderMs : 0,
                        completedAt: completedAtMain,
                        rafCycleStartMs: typeof d.rafCycleStartMs === 'number' ? d.rafCycleStartMs : undefined,
                        canvasWorkerRafWaitMs: typeof d.workerRafWaitMs === 'number' ? d.workerRafWaitMs : undefined,
                        canvasWorkerReceiveLagMs: typeof d.receiveLagMs === 'number' ? d.receiveLagMs : undefined,
                        renderAckDeliveryMs,
                    });
                }
            };

            // Set up error handling
            worker.onerror = (error) => {
                console.error(`Worker error for camera ${cameraId}:`, error);
                this.recordWorkerError(cameraId);
            };

            worker.onmessageerror = (error) => {
                console.error(`Worker message error for camera ${cameraId}:`, error);
            };

            return worker;
        } finally {
            URL.revokeObjectURL(workerUrl);
        }
    }

    private recordWorkerError(cameraId: string): void {
        const errorCount = (this.workerErrors.get(cameraId) ?? 0) + 1;
        this.workerErrors.set(cameraId, errorCount);

        if (errorCount >= this.maxWorkerErrors) {
            console.error(
                `Worker for camera ${cameraId} has failed ${errorCount} times, disabling. ` +
                `Worker will be recreated if canvas is set again.`
            );
            this.terminateWorker(cameraId);
        }
    }

}
