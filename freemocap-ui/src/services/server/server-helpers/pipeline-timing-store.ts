import {
    DetailedFramerate,
    MAX_DURATION_HISTORY,
    TimestampedRingBuffer,
    WindowedStats,
} from "@/services/server/server-helpers/sample-window-stats";
import {
    PIPELINE_TIMELINE_FRAME_WINDOW,
    type PipelineTimingEventPayload,
    type StoredPipelineTaskEvent,
    type UiTimingRecordContext,
} from "@/services/server/server-helpers/pipeline-timing-types";
import {estimateFrameDurationFromFrameAnchors} from "@/components/pipeline-metrics/pipelineTimelineModel";
import {buildDeterministicTaskId} from "@/components/pipeline-metrics/pipelineTaskTopology";
import type {PipelineTimingWsMessage} from "@/services/server/server-helpers/websocket-message-types";

export type PipelineTimingSnapshot = {
    aggregates: Map<string, DetailedFramerate | null>;
    recentValues: Map<string, number | null>;
    lastSampleTimestamps: Map<string, number>;
    logPipelineTimesEnabled: boolean;
};

export type PipelineTimelineSnapshot = {
    events: StoredPipelineTaskEvent[];
    backendFrameDurationMs: number | null;
    configuredFrameDurationMs: number | null;
    /** Frame duration locked at pipeline startup; timeline scale stays fixed until clear(). */
    lockedFrameDurationMs: number | null;
    droppedTimingEvents: number;
    logPipelineTimesEnabled: boolean;
};

/** Align backend perf_counter_ns samples to renderer performance.now() at ingest. */
export function normalizeBackendPerfNsToRendererMs(
    eventNs: number,
    ingestPerfMs: number,
    relayPerfCounterNs: number | null,
): number {
    if (relayPerfCounterNs == null) {
        return ingestPerfMs;
    }
    const relayPerfMs = relayPerfCounterNs / 1e6;
    const eventPerfMs = eventNs / 1e6;
    return ingestPerfMs - (relayPerfMs - eventPerfMs);
}

/**
 * Ingests backend pipeline_timing batches and UI-measured samples.
 * Mutable ref store — poll via getSnapshot() or getTimelineSnapshot().
 */
export class PipelineTimingStore {
    private readonly buffers = new Map<string, TimestampedRingBuffer>();
    private readonly statsComputers = new Map<string, WindowedStats>();
    private readonly recentValues = new Map<string, number | null>();
    private readonly lastSampleTimestamps = new Map<string, number>();
    private readonly taskEvents = new Map<string, StoredPipelineTaskEvent>();
    private logPipelineTimesEnabled = false;
    private droppedTimingEvents = 0;
    private backendFrameDurationMs: number | null = null;
    private configuredFrameDurationMs: number | null = null;
    private lockedFrameDurationMs: number | null = null;

    private _writeVersion = 0;
    private _snapshotVersion = -1;
    private _cachedSnapshot: PipelineTimingSnapshot | null = null;
    private _timelineVersion = -1;
    private _cachedTimeline: PipelineTimelineSnapshot | null = null;

    private touch(rowKey: string): void {
        this.lastSampleTimestamps.set(rowKey, Date.now());
    }

    private bump(): void {
        this._writeVersion++;
        this._cachedSnapshot = null;
        this._cachedTimeline = null;
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

    private pruneTaskEventsOutsideFrameWindow(): void {
        const framed = [...this.taskEvents.values()].filter(e => e.frameNumber != null);
        if (framed.length === 0) return;
        const latestFrame = Math.max(...framed.map(e => e.frameNumber as number));
        const minFrame = Math.max(0, latestFrame - PIPELINE_TIMELINE_FRAME_WINDOW);
        for (const [id, event] of this.taskEvents) {
            if (event.frameNumber != null && event.frameNumber < minFrame) {
                this.taskEvents.delete(id);
            }
        }
    }

    private backendNsToRendererMs(eventNs: number, ingestPerfMs: number, relayPerfCounterNs: number | null): number {
        return normalizeBackendPerfNsToRendererMs(eventNs, ingestPerfMs, relayPerfCounterNs);
    }

    private upsertTaskEvent(event: StoredPipelineTaskEvent): void {
        const existing = this.taskEvents.get(event.taskId);
        if (existing) {
            this.taskEvents.set(event.taskId, {
                ...existing,
                ...event,
                parentTaskIds: event.parentTaskIds.length > 0 ? event.parentTaskIds : existing.parentTaskIds,
                lastSeenMs: event.lastSeenMs,
            });
        } else {
            this.taskEvents.set(event.taskId, event);
        }
        this.pruneTaskEventsOutsideFrameWindow();
    }

    private ingestExplicitEvent(
        payload: PipelineTimingEventPayload,
        ingestPerfMs: number,
        relayPerfCounterNs: number | null,
    ): void {
        const startNs = payload.start_time_ns ?? null;
        const endNs = payload.end_time_ns ?? null;
        let startMs: number;
        let endMs: number;
        if (startNs != null && endNs != null) {
            startMs = this.backendNsToRendererMs(startNs, ingestPerfMs, relayPerfCounterNs);
            endMs = this.backendNsToRendererMs(endNs, ingestPerfMs, relayPerfCounterNs);
        } else {
            endMs = ingestPerfMs;
            startMs = endMs - payload.duration_ms;
        }
        const sourceKey = payload.camera_id
            ? `${payload.node_kind === 'camera' ? 'camera' : payload.node_kind}:${payload.camera_id}:${payload.stage}`
            : `${payload.node_kind}:${payload.stage}`;

        this.upsertTaskEvent({
            taskId: payload.task_id,
            parentTaskIds: payload.parent_task_ids ?? [],
            stage: payload.stage,
            nodeKind: payload.node_kind,
            cameraId: payload.camera_id ?? null,
            frameNumber: payload.frame_number ?? null,
            startMs,
            endMs,
            durationMs: payload.duration_ms,
            clockDomain: 'backend_perf',
            sourceKey,
            lastSeenMs: performance.now(),
        });
    }

    private ingestLegacySample(
        rowKey: string,
        durationMs: number,
        ingestPerfMs: number,
        nodeKind: string,
        stage: string,
        cameraId: string | null,
    ): void {
        const endMs = ingestPerfMs;
        const startMs = endMs - durationMs;
        const taskId = `legacy:${rowKey}:${Math.round(endMs)}`;
        this.upsertTaskEvent({
            taskId,
            parentTaskIds: [],
            stage,
            nodeKind,
            cameraId,
            frameNumber: null,
            startMs,
            endMs,
            durationMs,
            clockDomain: 'ingest_wall',
            sourceKey: rowKey,
            lastSeenMs: performance.now(),
        });
    }

    private lockTimelineScaleIfNeeded(events: StoredPipelineTaskEvent[]): void {
        if (this.lockedFrameDurationMs != null) {
            return;
        }
        if (this.configuredFrameDurationMs != null && this.configuredFrameDurationMs > 0) {
            this.lockedFrameDurationMs = this.configuredFrameDurationMs;
            return;
        }
        const measuredFrameDurationMs = estimateFrameDurationFromFrameAnchors(events);
        if (measuredFrameDurationMs != null && measuredFrameDurationMs > 0) {
            this.lockedFrameDurationMs = measuredFrameDurationMs;
        }
    }

    setBackendFrameDurationMs(durationMs: number | null): void {
        if (durationMs != null && durationMs > 0) {
            this.backendFrameDurationMs = durationMs;
            this.bump();
        }
    }

    setConfiguredCameraFpsHz(fpsHz: number | null | undefined): void {
        if (fpsHz != null && fpsHz > 0) {
            this.configuredFrameDurationMs = 1000 / fpsHz;
            this.lockTimelineScaleIfNeeded([...this.taskEvents.values()]);
            this.bump();
        }
    }

    ingestBackendMessage(msg: PipelineTimingWsMessage): void {
        this.logPipelineTimesEnabled = msg.log_pipeline_times_enabled ?? false;
        this.pruneHiddenBackendRows();
        this.prunePubsubRowsWhenDisabled();
        const ingestWallMs = Date.now();
        const ingestPerfMs = performance.now();
        const relayPerfCounterNs = msg.relay_perf_counter_ns ?? null;

        this.setConfiguredCameraFpsHz(msg.configured_camera_fps_hz);

        if (typeof msg.dropped_timing_events === 'number' && msg.dropped_timing_events > 0) {
            this.droppedTimingEvents += msg.dropped_timing_events;
        }

        if (msg.events) {
            for (const event of msg.events) {
                this.ingestExplicitEvent(event, ingestPerfMs, relayPerfCounterNs);
            }
        }

        if (msg.per_node) {
            for (const [nodeKind, stages] of Object.entries(msg.per_node)) {
                for (const [stage, samples] of Object.entries(stages)) {
                    if (nodeKind === "skeleton_inference" && stage === "predict_per_camera") {
                        continue;
                    }
                    const rowKey = `${nodeKind}:${stage}`;
                    const buf = this.ensureBuffer(rowKey);
                    for (const v of samples) {
                        buf.push(ingestWallMs, v);
                        this.recentValues.set(rowKey, v);
                        this.ingestLegacySample(rowKey, v, ingestPerfMs, nodeKind, stage, null);
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
                        buf.push(ingestWallMs, v);
                        this.recentValues.set(rowKey, v);
                        this.ingestLegacySample(rowKey, v, ingestPerfMs, 'camera', stage, camId);
                    }
                    this.touch(rowKey);
                }
            }
        }

        this.bump();
    }

    private recordUiDuration(
        cameraId: string,
        stage: string,
        latencyMs: number,
        ctx?: UiTimingRecordContext,
    ): void {
        const rowKey = `ui:${cameraId}:${stage}`;
        const buf = this.ensureBuffer(rowKey);
        const nowWall = Date.now();
        buf.push(nowWall, latencyMs);
        this.recentValues.set(rowKey, latencyMs);
        this.touch(rowKey);

        const nowPerf = performance.now();
        const frameNumber = ctx?.frameNumber ?? null;
        const taskId = frameNumber != null
            ? buildDeterministicTaskId({
                frameNumber,
                cameraId,
                nodeKind: 'ui',
                stage,
                scope: 'ui',
            })
            : `ui-orphan:${cameraId}:${stage}:${Math.round(nowPerf)}`;

        this.upsertTaskEvent({
            taskId,
            parentTaskIds: ctx?.parentTaskIds ?? [],
            stage,
            nodeKind: 'ui',
            cameraId,
            frameNumber,
            startMs: nowPerf - latencyMs,
            endMs: nowPerf,
            durationMs: latencyMs,
            clockDomain: 'renderer_perf',
            sourceKey: rowKey,
            lastSeenMs: nowPerf,
        });
        this.bump();
    }

    recordRafBodyBeforeDecode(cameraId: string, latencyMs: number, ctx?: UiTimingRecordContext): void {
        this.recordUiDuration(cameraId, 'raf_body_before_decode_ms', latencyMs, ctx);
    }

    recordJpegDecodeWorker(cameraId: string, latencyMs: number, ctx?: UiTimingRecordContext): void {
        this.recordUiDuration(cameraId, 'jpeg_decode_worker_ms', latencyMs, ctx);
    }

    recordJpegDecodeMainWait(cameraId: string, latencyMs: number, ctx?: UiTimingRecordContext): void {
        this.recordUiDuration(cameraId, 'jpeg_decode_main_wait_ms', latencyMs, ctx);
    }

    recordJpegDecodeBridge(cameraId: string, latencyMs: number, ctx?: UiTimingRecordContext): void {
        this.recordUiDuration(cameraId, 'jpeg_decode_bridge_ms', latencyMs, ctx);
    }

    recordMainDispatchToCanvas(cameraId: string, latencyMs: number, ctx?: UiTimingRecordContext): void {
        this.recordUiDuration(cameraId, 'main_dispatch_to_canvas_ms', latencyMs, ctx);
    }

    recordCanvasWorkerReceiveLag(cameraId: string, latencyMs: number, ctx?: UiTimingRecordContext): void {
        this.recordUiDuration(cameraId, 'canvas_worker_receive_lag_ms', latencyMs, ctx);
    }

    recordCanvasWorkerRafWait(cameraId: string, latencyMs: number, ctx?: UiTimingRecordContext): void {
        this.recordUiDuration(cameraId, 'canvas_worker_raf_wait_ms', latencyMs, ctx);
    }

    recordCanvasBitmapTransfer(cameraId: string, latencyMs: number, ctx?: UiTimingRecordContext): void {
        this.recordUiDuration(cameraId, 'canvas_bitmap_transfer_ms', latencyMs, ctx);
    }

    recordRenderAckDelivery(cameraId: string, latencyMs: number, ctx?: UiTimingRecordContext): void {
        this.recordUiDuration(cameraId, 'render_ack_delivery_ms', latencyMs, ctx);
    }

    recordJpegAckToReceive(cameraId: string, latencyMs: number, ctx?: UiTimingRecordContext): void {
        this.recordUiDuration(cameraId, 'jpeg_ack_to_receive_ms', latencyMs, ctx);
    }

    recordJpegWsBinaryInterval(cameraId: string, intervalMs: number, ctx?: UiTimingRecordContext): void {
        this.recordUiDuration(cameraId, 'jpeg_ws_binary_interval_ms', intervalMs, ctx);
    }

    recordJpegWsBinaryDispatchLag(cameraId: string, lagMs: number, ctx?: UiTimingRecordContext): void {
        this.recordUiDuration(cameraId, 'jpeg_ws_dispatch_lag_ms', lagMs, ctx);
    }

    recordRafToRendered(cameraId: string, latencyMs: number, ctx?: UiTimingRecordContext): void {
        this.recordUiDuration(cameraId, 'raf_to_rendered_ms', latencyMs, ctx);
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

    getTimelineSnapshot(): PipelineTimelineSnapshot {
        if (this._cachedTimeline && this._timelineVersion === this._writeVersion) {
            return this._cachedTimeline;
        }
        const events = [...this.taskEvents.values()];
        this.lockTimelineScaleIfNeeded(events);
        this._cachedTimeline = {
            events,
            backendFrameDurationMs: this.backendFrameDurationMs,
            configuredFrameDurationMs: this.configuredFrameDurationMs,
            lockedFrameDurationMs: this.lockedFrameDurationMs,
            droppedTimingEvents: this.droppedTimingEvents,
            logPipelineTimesEnabled: this.logPipelineTimesEnabled,
        };
        this._timelineVersion = this._writeVersion;
        return this._cachedTimeline;
    }

    clear(): void {
        this.buffers.clear();
        this.statsComputers.clear();
        this.recentValues.clear();
        this.lastSampleTimestamps.clear();
        this.taskEvents.clear();
        this.logPipelineTimesEnabled = false;
        this.droppedTimingEvents = 0;
        this.backendFrameDurationMs = null;
        this.configuredFrameDurationMs = null;
        this.lockedFrameDurationMs = null;
        this._writeVersion++;
        this._cachedSnapshot = null;
        this._cachedTimeline = null;
        this._snapshotVersion = -1;
        this._timelineVersion = -1;
    }
}
