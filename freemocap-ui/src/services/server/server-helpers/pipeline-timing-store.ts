import {
    DetailedFramerate,
    MAX_DURATION_HISTORY,
    TimestampedRingBuffer,
    WindowedStats,
} from "@/services/server/server-helpers/sample-window-stats";

export type PipelineTimingSnapshot = {
    aggregates: Map<string, DetailedFramerate | null>;
    recentValues: Map<string, number | null>;
    lastSampleTimestamps: Map<string, number>;
    logPipelineTimesEnabled: boolean;
};

/**
 * Ingests backend pipeline_timing batches and UI-measured samples.
 * Mutable ref store — poll via getSnapshot().
 */
export class PipelineTimingStore {
    private readonly buffers = new Map<string, TimestampedRingBuffer>();
    private readonly statsComputers = new Map<string, WindowedStats>();
    private readonly recentValues = new Map<string, number | null>();
    private readonly lastSampleTimestamps = new Map<string, number>();
    private logPipelineTimesEnabled = false;

    private _writeVersion = 0;
    private _snapshotVersion = -1;
    private _cachedSnapshot: PipelineTimingSnapshot | null = null;

    private touch(rowKey: string): void {
        this.lastSampleTimestamps.set(rowKey, Date.now());
    }

    private ensureBuffer(rowKey: string): TimestampedRingBuffer {
        let buf = this.buffers.get(rowKey);
        if (!buf) {
            buf = new TimestampedRingBuffer(MAX_DURATION_HISTORY);
            this.buffers.set(rowKey, buf);
            this.statsComputers.set(rowKey, new WindowedStats(buf, MAX_DURATION_HISTORY));
        }
        return buf;
    }

    /** Drop rows hidden from the Pipeline Stages panel (stale keys after policy changes). */
    private pruneHiddenBackendRows(): void {
        for (const key of [...this.buffers.keys()]) {
            if (
                key === "skeleton_inference:predict_per_camera"
                || (key.startsWith("camera:") && key.endsWith(":total_camera_node"))
                || (key.startsWith("camera:") && key.endsWith(":total_detection_time"))
            ) {
                this.buffers.delete(key);
                this.statsComputers.delete(key);
                this.recentValues.delete(key);
                this.lastSampleTimestamps.delete(key);
            }
        }
    }

    /** Remove pubsub-only rows when pipeline timing is disabled on the server. */
    private prunePubsubRowsWhenDisabled(): void {
        if (this.logPipelineTimesEnabled) {
            return;
        }
        for (const key of [...this.buffers.keys()]) {
            if (key.startsWith("skeleton_inference:") || key.startsWith("aggregator:")) {
                this.buffers.delete(key);
                this.statsComputers.delete(key);
                this.recentValues.delete(key);
                this.lastSampleTimestamps.delete(key);
            }
        }
    }

    /** Backend ~4Hz batch */
    ingestBackendMessage(msg: {
        log_pipeline_times_enabled?: boolean;
        per_node?: Record<string, Record<string, number[]>>;
        per_camera?: Record<string, Record<string, number[]>>;
    }): void {
        this.logPipelineTimesEnabled = msg.log_pipeline_times_enabled ?? false;
        this.pruneHiddenBackendRows();
        this.prunePubsubRowsWhenDisabled();
        const ts = Date.now();

        if (msg.per_node) {
            for (const [nodeKind, stages] of Object.entries(msg.per_node)) {
                for (const [stage, samples] of Object.entries(stages)) {
                    if (nodeKind === "skeleton_inference" && stage === "predict_per_camera") {
                        continue;
                    }
                    const rowKey = `${nodeKind}:${stage}`;
                    const buf = this.ensureBuffer(rowKey);
                    for (const v of samples) {
                        buf.push(ts, v);
                        this.recentValues.set(rowKey, v);
                    }
                    this.touch(rowKey);
                }
            }
        }

        if (msg.per_camera) {
            for (const [camId, stages] of Object.entries(msg.per_camera)) {
                for (const [stage, samples] of Object.entries(stages)) {
                    const rowKey = `camera:${camId}:${stage}`;
                    const buf = this.ensureBuffer(rowKey);
                    for (const v of samples) {
                        buf.push(ts, v);
                        this.recentValues.set(rowKey, v);
                    }
                    this.touch(rowKey);
                }
            }
        }

        this._writeVersion++;
        this._cachedSnapshot = null;
    }

    /** Main-thread work in the same rAF tick before multiplex JPEG decode is queued (ack, JSON, keypoints, etc.). */
    recordRafBodyBeforeDecode(cameraId: string, latencyMs: number): void {
        const rowKey = `ui:${cameraId}:raf_body_before_decode_ms`;
        const buf = this.ensureBuffer(rowKey);
        buf.push(Date.now(), latencyMs);
        this.recentValues.set(rowKey, latencyMs);
        this.touch(rowKey);
        this._writeVersion++;
        this._cachedSnapshot = null;
    }

    /** Wall time inside the JPEG decode worker (parse + createImageBitmap), excluding postMessage bridging. */
    recordJpegDecodeWorker(cameraId: string, latencyMs: number): void {
        const rowKey = `ui:${cameraId}:jpeg_decode_worker_ms`;
        const buf = this.ensureBuffer(rowKey);
        buf.push(Date.now(), latencyMs);
        this.recentValues.set(rowKey, latencyMs);
        this.touch(rowKey);
        this._writeVersion++;
        this._cachedSnapshot = null;
    }

    /** Main-thread wait from posting decode to dispatchFrames: worker time + structured clone + microtask scheduling. */
    recordJpegDecodeMainWait(cameraId: string, latencyMs: number): void {
        const rowKey = `ui:${cameraId}:jpeg_decode_main_wait_ms`;
        const buf = this.ensureBuffer(rowKey);
        buf.push(Date.now(), latencyMs);
        this.recentValues.set(rowKey, latencyMs);
        this.touch(rowKey);
        this._writeVersion++;
        this._cachedSnapshot = null;
    }

    /** Approx. postMessage / main-thread slice: main wait minus worker-busy time (see tooltips). */
    recordJpegDecodeBridge(cameraId: string, latencyMs: number): void {
        const rowKey = `ui:${cameraId}:jpeg_decode_bridge_ms`;
        const buf = this.ensureBuffer(rowKey);
        buf.push(Date.now(), latencyMs);
        this.recentValues.set(rowKey, latencyMs);
        this.touch(rowKey);
        this._writeVersion++;
        this._cachedSnapshot = null;
    }

    /** Main thread from entering dispatchFrames until this frame is posted to the canvas worker (includes overlay if async path completes later). */
    recordMainDispatchToCanvas(cameraId: string, latencyMs: number): void {
        const rowKey = `ui:${cameraId}:main_dispatch_to_canvas_ms`;
        const buf = this.ensureBuffer(rowKey);
        buf.push(Date.now(), latencyMs);
        this.recentValues.set(rowKey, latencyMs);
        this.touch(rowKey);
        this._writeVersion++;
        this._cachedSnapshot = null;
    }

    /** Canvas worker: performance.now() delta from main postMessage to worker onmessage (cross-thread delivery). */
    recordCanvasWorkerReceiveLag(cameraId: string, latencyMs: number): void {
        const rowKey = `ui:${cameraId}:canvas_worker_receive_lag_ms`;
        const buf = this.ensureBuffer(rowKey);
        buf.push(Date.now(), latencyMs);
        this.recentValues.set(rowKey, latencyMs);
        this.touch(rowKey);
        this._writeVersion++;
        this._cachedSnapshot = null;
    }

    /** Canvas worker: from frame received until the rAF callback begins painting this frame. */
    recordCanvasWorkerRafWait(cameraId: string, latencyMs: number): void {
        const rowKey = `ui:${cameraId}:canvas_worker_raf_wait_ms`;
        const buf = this.ensureBuffer(rowKey);
        buf.push(Date.now(), latencyMs);
        this.recentValues.set(rowKey, latencyMs);
        this.touch(rowKey);
        this._writeVersion++;
        this._cachedSnapshot = null;
    }

    /** Worker ImageBitmapRenderingContext: transferFromImageBitmap wall time. */
    recordCanvasBitmapTransfer(cameraId: string, latencyMs: number): void {
        const rowKey = `ui:${cameraId}:canvas_bitmap_transfer_ms`;
        const buf = this.ensureBuffer(rowKey);
        buf.push(Date.now(), latencyMs);
        this.recentValues.set(rowKey, latencyMs);
        this.touch(rowKey);
        this._writeVersion++;
        this._cachedSnapshot = null;
    }

    /** Main thread: time from worker posting renderAck until the window receives the message. */
    recordRenderAckDelivery(cameraId: string, latencyMs: number): void {
        const rowKey = `ui:${cameraId}:render_ack_delivery_ms`;
        const buf = this.ensureBuffer(rowKey);
        buf.push(Date.now(), latencyMs);
        this.recentValues.set(rowKey, latencyMs);
        this.touch(rowKey);
        this._writeVersion++;
        this._cachedSnapshot = null;
    }

    /** Time from sending frameAcknowledgment until this JPEG multiplex payload was fully received (network + server). */
    recordJpegAckToReceive(cameraId: string, latencyMs: number): void {
        const rowKey = `ui:${cameraId}:jpeg_ack_to_receive_ms`;
        const buf = this.ensureBuffer(rowKey);
        buf.push(Date.now(), latencyMs);
        this.recentValues.set(rowKey, latencyMs);
        this.touch(rowKey);
        this._writeVersion++;
        this._cachedSnapshot = null;
    }

    /**
     * Milliseconds since the previous multiplex JPEG binary arrived on this WebSocket.
     * When the server sends one preview payload at a time, this tracks pacing of full-frame delivery.
     */
    recordJpegWsBinaryInterval(cameraId: string, intervalMs: number): void {
        const rowKey = `ui:${cameraId}:jpeg_ws_binary_interval_ms`;
        const buf = this.ensureBuffer(rowKey);
        buf.push(Date.now(), intervalMs);
        this.recentValues.set(rowKey, intervalMs);
        this.touch(rowKey);
        this._writeVersion++;
        this._cachedSnapshot = null;
    }

    /** Main-thread delay between the browser's MessageEvent timestamp and this handler running. */
    recordJpegWsBinaryDispatchLag(cameraId: string, lagMs: number): void {
        const rowKey = `ui:${cameraId}:jpeg_ws_dispatch_lag_ms`;
        const buf = this.ensureBuffer(rowKey);
        buf.push(Date.now(), lagMs);
        this.recentValues.set(rowKey, lagMs);
        this.touch(rowKey);
        this._writeVersion++;
        this._cachedSnapshot = null;
    }

    /** Main-thread window time from the rAF tick that started decode to render ack after bitmaprenderer paint. */
    recordRafToRendered(cameraId: string, latencyMs: number): void {
        const rowKey = `ui:${cameraId}:raf_to_rendered_ms`;
        const buf = this.ensureBuffer(rowKey);
        buf.push(Date.now(), latencyMs);
        this.recentValues.set(rowKey, latencyMs);
        this.touch(rowKey);
        this._writeVersion++;
        this._cachedSnapshot = null;
    }

    getSnapshot(): PipelineTimingSnapshot {
        if (this._cachedSnapshot && this._snapshotVersion === this._writeVersion) {
            return this._cachedSnapshot;
        }

        const aggregates = new Map<string, DetailedFramerate | null>();
        const recent = new Map<string, number | null>();

        for (const [rowKey, computer] of this.statsComputers.entries()) {
            aggregates.set(rowKey, computer.computeAggregate(rowKey));
            recent.set(rowKey, this.recentValues.get(rowKey) ?? null);
        }

        this._cachedSnapshot = {
            aggregates,
            recentValues: recent,
            lastSampleTimestamps: new Map(this.lastSampleTimestamps),
            logPipelineTimesEnabled: this.logPipelineTimesEnabled,
        };
        this._snapshotVersion = this._writeVersion;
        return this._cachedSnapshot;
    }

    clear(): void {
        this.buffers.clear();
        this.statsComputers.clear();
        this.recentValues.clear();
        this.lastSampleTimestamps.clear();
        this.logPipelineTimesEnabled = false;
        this._writeVersion++;
        this._cachedSnapshot = null;
        this._snapshotVersion = -1;
    }
}
