import { workerCode } from "@/services/server/server-helpers/offscreen-renderer.worker";

export interface FrameData {
    cameraId: string;
    frameNumber: number;
    bitmap: ImageBitmap;
}

export interface CanvasWorker {
    worker: Worker;
    canvas: HTMLCanvasElement;
    initialized: boolean;
}

export class CanvasManager {
    private workers: Map<string, CanvasWorker> = new Map();
    private workerErrors: Map<string, number> = new Map();
    private pendingCanvases: Map<string, HTMLCanvasElement> = new Map();
    private renderCallbacks: Map<string, () => void> = new Map(); // cameraId -> callback
    private readonly maxWorkerErrors: number = 3;

    public setCanvasForCamera(cameraId: string, canvas: HTMLCanvasElement): boolean {
        const existing = this.workers.get(cameraId);
        if (existing?.canvas === canvas && existing.initialized) {
            return true;
        }

        if (existing && existing.canvas !== canvas) {
            console.log(`Canvas changed for camera ${cameraId}, recreating worker`);
            this.terminateWorker(cameraId);
        }

        this.pendingCanvases.set(cameraId, canvas);

        try {
            const worker = this.createWorker(cameraId);
            const offscreen = canvas.transferControlToOffscreen();

            worker.postMessage(
                { type: 'init', canvas: offscreen },
                [offscreen]
            );

            this.workers.set(cameraId, {
                worker,
                canvas,
                initialized: true
            });

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

    public sendFrameToWorker(
        cameraId: string,
        bitmap: ImageBitmap,
        onRendered?: () => void
    ): boolean {
        const workerInfo = this.workers.get(cameraId);

        if (!workerInfo?.initialized) {
            const pendingCanvas = this.pendingCanvases.get(cameraId);
            if (pendingCanvas) {
                console.log(`Worker not ready for ${cameraId}, attempting to create from pending canvas`);
                if (this.setCanvasForCamera(cameraId, pendingCanvas)) {
                    return this.sendFrameToWorker(cameraId, bitmap, onRendered);
                }
            }

            console.warn(`No initialized worker for camera ${cameraId}, dropping frame`);
            bitmap.close();
            onRendered?.();
            return false;
        }

        try {
            // Store callback for this camera
            if (onRendered) {
                this.renderCallbacks.set(cameraId, onRendered);
            }

            workerInfo.worker.postMessage(
                { type: 'frame', bitmap },
                [bitmap]
            );
            return true;
        } catch (error) {
            console.error(`Failed to send frame to worker ${cameraId}:`, error);
            bitmap.close();
            onRendered?.();
            this.recordWorkerError(cameraId);
            return false;
        }
    }

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

        // Clean up callback
        this.renderCallbacks.delete(cameraId);
        this.pendingCanvases.delete(cameraId);
    }

    public terminateAllWorkers(): void {
        console.log(`Terminating all workers (${this.workers.size} active)`);
        for (const [cameraId] of this.workers) {
            this.terminateWorker(cameraId);
        }
        this.workerErrors.clear();
        this.pendingCanvases.clear();
        this.renderCallbacks.clear();
    }

    public getActiveCameraIds(): string[] {
        return Array.from(this.workers.keys());
    }

    public hasWorker(cameraId: string): boolean {
        const worker = this.workers.get(cameraId);
        return worker?.initialized ?? false;
    }

    private createWorker(cameraId: string): Worker {
        const blob = new Blob([workerCode], { type: 'application/javascript' });
        const workerUrl = URL.createObjectURL(blob);

        try {
            const worker = new Worker(workerUrl);

            worker.onerror = (error) => {
                console.error(`Worker error for camera ${cameraId}:`, error);
                this.recordWorkerError(cameraId);
            };

            worker.onmessageerror = (error) => {
                console.error(`Worker message error for camera ${cameraId}:`, error);
            };

            worker.onmessage = (e) => {
                if (e.data.type === 'frameRendered') {
                    const callback = this.renderCallbacks.get(cameraId);
                    if (callback) {
                        callback();
                        this.renderCallbacks.delete(cameraId);
                    }
                }
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

    public getWorkerStatus(cameraId: string): {
        hasWorker: boolean;
        errorCount: number;
        hasPendingCanvas: boolean;
    } {
        return {
            hasWorker: this.workers.has(cameraId),
            errorCount: this.workerErrors.get(cameraId) ?? 0,
            hasPendingCanvas: this.pendingCanvases.has(cameraId)
        };
    }
}
