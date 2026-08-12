import {
    DetailedFramerate,
    MAX_DURATION_HISTORY,
    TimestampedRingBuffer,
    WindowedStats,
} from "@/services/server/server-helpers/sample-window-stats";
import {
    MAX_CONTEXTLESS_EVENTS_PER_SOURCE,
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
    /** null until the first backend status heartbeat is received. */
    realtimePipelineActive: boolean | null;
    /** Mean frame processing time over the last ~10 seconds of samples, in ms. */
    trailingMeanFrameMs: number | null;
    /** Frame numbers missing one or more node kinds. */
    incompleteFrames: number[];
    /** Per-node-kind lag: frames each node kind is behind the leader. */
    nodeLag: Record<string, number>;
    /** Node kinds excluded due to staleness timeout. */
    staleNodes: string[];
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
    private realtimePipelineActive: boolean | null = null;
    private droppedTimingEvents = 0;
    private backendFrameDurationMs: number | null = null;
    private configuredFrameDurationMs: number | null = null;
    private lockedFrameDurationMs: number | null = null;
    private incompleteFrames: number[] = [];
    private nodeLag: Record<string, number> = {};
    private staleNodes: string[] = [];

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
            if (key.startsWith("skeleton_inference:")) {
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

    /** Frameless / synthetic-timing rows accumulate unique task ids — cap per sourceKey. */
    private pruneContextlessTaskEvents(): void {
        const bySource = new Map<string, StoredPipelineTaskEvent[]>();
        for (const event of this.taskEvents.values()) {
            if (event.frameNumber != null) {
                continue;
            }
            const group = bySource.get(event.sourceKey) ?? [];
            group.push(event);
            bySource.set(event.sourceKey, group);
        }
        for (const group of bySource.values()) {
            if (group.length <= MAX_CONTEXTLESS_EVENTS_PER_SOURCE) {
                continue;
            }
            group.sort((a, b) => a.lastSeenMs - b.lastSeenMs);
            for (const event of group.slice(0, group.length - MAX_CONTEXTLESS_EVENTS_PER_SOURCE)) {
                this.taskEvents.delete(event.taskId);
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
        this.pruneContextlessTaskEvents();
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
            ? `${payload.node_kind}:${payload.camera_id}:${payload.stage}`
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
        if (typeof msg.realtime_pipeline_active === 'boolean') {
            this.realtimePipelineActive = msg.realtime_pipeline_active;
        }
        this.pruneHiddenBackendRows();
        this.prunePubsubRowsWhenDisabled();
        const ingestWallMs = Date.now();
        const ingestPerfMs = performance.now();
        const relayPerfCounterNs = msg.relay_perf_counter_ns ?? null;

        this.setConfiguredCameraFpsHz(msg.configured_camera_fps_hz);

        if (typeof msg.dropped_timing_events === 'number' && msg.dropped_timing_events > 0) {
            this.droppedTimingEvents += msg.dropped_timing_events;
        }

        if (Array.isArray(msg.incomplete_frames)) {
            this.incompleteFrames = msg.incomplete_frames;
        }
        if (msg.node_lag && typeof msg.node_lag === 'object') {
            this.nodeLag = msg.node_lag as Record<string, number>;
        }
        if (Array.isArray(msg.stale_nodes)) {
            this.staleNodes = msg.stale_nodes;
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
            for (const [cameraId, stages] of Object.entries(msg.per_camera)) {
                for (const [stage, samples] of Object.entries(stages)) {
                    const rowKey = `camera:${cameraId}:${stage}`;
                    const buf = this.ensureBuffer(rowKey);
                    for (const v of samples) {
                        buf.push(ingestWallMs, v);
                        this.recentValues.set(rowKey, v);
                        this.ingestLegacySample(rowKey, v, ingestPerfMs, 'camera', stage, cameraId ?? null);
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
            realtimePipelineActive: this.realtimePipelineActive,
            trailingMeanFrameMs: this._computeTrailingMeanCombined(10_000),
            incompleteFrames: this.incompleteFrames,
            nodeLag: this.nodeLag,
            staleNodes: this.staleNodes,
        };
        this._timelineVersion = this._writeVersion;
        return this._cachedTimeline;
    }

    private _computeTrailingMean(rowKey: string, windowMs: number): number | null {
        const buf = this.buffers.get(rowKey);
        if (!buf) return null;
        const samples = buf.toArray();
        if (samples.length === 0) return null;
        const now = Date.now();
        const cutoff = now - windowMs;
        let sum = 0;
        let count = 0;
        for (let i = samples.length - 1; i >= 0; i--) {
            if (samples[i].timestamp < cutoff) break;
            sum += samples[i].value;
            count++;
        }
        return count > 0 ? sum / count : null;
    }

    private _computeTrailingMeanCameraTotal(windowMs: number): number | null {
        const now = Date.now();
        const cutoff = now - windowMs;
        let bestMean = null as number | null;
        for (const [key, buf] of this.buffers) {
            if (!key.startsWith('camera:') || !key.endsWith(':total_camera_node')) continue;
            const samples = buf.toArray();
            let sum = 0;
            let count = 0;
            for (let i = samples.length - 1; i >= 0; i--) {
                if (samples[i].timestamp < cutoff) break;
                sum += samples[i].value;
                count++;
            }
            if (count > 0) {
                const mean = sum / count;
                if (bestMean === null || mean > bestMean) bestMean = mean;
            }
        }
        return bestMean;
    }

    private _computeTrailingMeanCombined(windowMs: number): number | null {
        const predictBatchMean = this._computeTrailingMean("skeleton_inference:predict_batch", windowMs);
        const cameraTotalMax = this._computeTrailingMeanCameraTotal(windowMs);
        if (predictBatchMean === null && cameraTotalMax === null) return null;
        return (predictBatchMean ?? 0) + (cameraTotalMax ?? 0);
    }

    clear(): void {
        this.buffers.clear();
        this.statsComputers.clear();
        this.recentValues.clear();
        this.lastSampleTimestamps.clear();
        this.taskEvents.clear();
        this.logPipelineTimesEnabled = false;
        this.realtimePipelineActive = null;
        this.droppedTimingEvents = 0;
        this.backendFrameDurationMs = null;
        this.configuredFrameDurationMs = null;
        this.lockedFrameDurationMs = null;
        this.incompleteFrames = [];
        this.nodeLag = {};
        this.staleNodes = [];
        this._writeVersion++;
        this._cachedSnapshot = null;
        this._cachedTimeline = null;
        this._snapshotVersion = -1;
        this._timelineVersion = -1;
    }
}
