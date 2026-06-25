import {
    FALLBACK_FRAME_DURATION_MS,
    PIPELINE_TIMELINE_FRAME_WINDOW,
    type PipelineTaskCategory,
    type StoredPipelineTaskEvent,
} from '@/services/server/server-helpers/pipeline-timing-types';
import {
    classifyTaskCategory,
    compareTimelineRows,
    inferParentTaskIds,
    orderTasksParentsBeforeChildren,
    taskLabel,
} from '@/components/pipeline-metrics/pipelineTaskTopology';

export interface TimelineRowView {
    taskId: string;
    label: string;
    category: PipelineTaskCategory;
    frameNumber: number | null;
    barStartMs: number;
    barEndMs: number;
    clippedStartMs: number;
    clippedEndMs: number;
    durationMs: number;
    sourceKey: string;
    stale: boolean;
    hasFrameContext: boolean;
}

export interface TimelineEdgeView {
    fromTaskId: string;
    toTaskId: string;
    fromRowIndex: number;
    toRowIndex: number;
}

export interface PipelineTimelineViewModel {
    windowStartMs: number;
    windowEndMs: number;
    windowDurationMs: number;
    frameStart: number | null;
    frameEnd: number | null;
    latestFrame: number | null;
    frameDurationMs: number;
    rows: TimelineRowView[];
    edges: TimelineEdgeView[];
    orphanUiRows: TimelineRowView[];
    droppedTimingEvents: number;
    logPipelineTimesEnabled: boolean;
    paused: boolean;
}

export type TimelineCategoryFilters = Record<PipelineTaskCategory, boolean>;

export const DEFAULT_CATEGORY_FILTERS: TimelineCategoryFilters = {
    capture: true,
    tracking: true,
    aggregation: true,
    ui_backend: true,
    ui_frontend: true,
    other: true,
};

const STALE_THRESHOLD_MS = 5000;
export const MIN_STARTUP_SCALE_FRAME_ANCHORS = 3;
/** Minimum bar width (percent of timeline) before showing inline duration text. */
export const BAR_DURATION_LABEL_MIN_WIDTH_PCT = 5;
const CONTEXTLESS_PREVIEW_STAGES = new Set([
    'jpeg_rotate',
    'jpeg_resize',
    'jpeg_encode',
    'ws_payload_prepare',
    'jpeg_rotate_ms',
    'jpeg_resize_ms',
    'jpeg_encode_ms',
    'ws_payload_prepare_ms',
    'preview',
    'inter_camera_grab_spread_ms',
]);

export function formatBarDuration(durationMs: number): string {
    if (durationMs >= 100) {
        return `${Math.round(durationMs)} ms`;
    }
    if (durationMs >= 10) {
        return `${durationMs.toFixed(1)} ms`;
    }
    return `${durationMs.toFixed(2)} ms`;
}

export function shouldShowBarDurationLabel(widthPct: number, durationLabel: string): boolean {
    const minPct = Math.max(BAR_DURATION_LABEL_MIN_WIDTH_PCT, durationLabel.length * 0.75);
    return widthPct >= minPct;
}

export function shouldShowWithoutFrameContext(event: StoredPipelineTaskEvent): boolean {
    if (event.frameNumber != null) {
        return false;
    }
    if (event.nodeKind === 'ui') {
        return true;
    }
    if (event.nodeKind === 'multiframe') {
        return CONTEXTLESS_PREVIEW_STAGES.has(event.stage);
    }
    if (event.nodeKind === 'camera') {
        return CONTEXTLESS_PREVIEW_STAGES.has(event.stage);
    }
    return false;
}

export function resolveFrameDurationMs(
    events: StoredPipelineTaskEvent[],
    backendFrameDurationMs: number | null,
): number {
    if (backendFrameDurationMs != null && backendFrameDurationMs > 0) {
        return backendFrameDurationMs;
    }
    const framed = events
        .filter(e => e.frameNumber != null && e.durationMs > 0)
        .sort((a, b) => a.startMs - b.startMs);
    if (framed.length >= 2) {
        const deltas: number[] = [];
        for (let i = 1; i < framed.length; i++) {
            const prev = framed[i - 1];
            const cur = framed[i];
            if (prev.frameNumber === cur.frameNumber) continue;
            const delta = cur.startMs - prev.startMs;
            if (delta > 0) deltas.push(delta);
        }
        if (deltas.length > 0) {
            deltas.sort((a, b) => a - b);
            return deltas[Math.floor(deltas.length / 2)];
        }
    }
    return FALLBACK_FRAME_DURATION_MS;
}

export function estimateFrameDurationFromFrameAnchors(
    events: StoredPipelineTaskEvent[],
    minFrameAnchors = MIN_STARTUP_SCALE_FRAME_ANCHORS,
): number | null {
    const startByFrame = new Map<number, number>();
    for (const event of events) {
        if (event.frameNumber == null || event.startMs == null) {
            continue;
        }
        const existing = startByFrame.get(event.frameNumber);
        if (existing == null || event.startMs < existing) {
            startByFrame.set(event.frameNumber, event.startMs);
        }
    }

    const anchors = [...startByFrame.entries()]
        .sort(([a], [b]) => a - b)
        .map(([frameNumber, startMs]) => ({frameNumber, startMs}));
    if (anchors.length < minFrameAnchors) {
        return null;
    }

    const deltas: number[] = [];
    for (let i = 1; i < anchors.length; i++) {
        const prev = anchors[i - 1];
        const cur = anchors[i];
        const frameDelta = cur.frameNumber - prev.frameNumber;
        const timeDelta = cur.startMs - prev.startMs;
        if (frameDelta <= 0 || timeDelta <= 0) {
            continue;
        }
        deltas.push(timeDelta / frameDelta);
    }
    if (deltas.length === 0) {
        return null;
    }
    deltas.sort((a, b) => a - b);
    return deltas[Math.floor(deltas.length / 2)];
}

export function clipBarToWindow(
    startMs: number,
    endMs: number,
    windowStartMs: number,
    windowEndMs: number,
): {clippedStartMs: number; clippedEndMs: number; visible: boolean} {
    const clippedStartMs = Math.max(startMs, windowStartMs);
    const clippedEndMs = Math.min(endMs, windowEndMs);
    return {
        clippedStartMs,
        clippedEndMs,
        visible: clippedEndMs > clippedStartMs,
    };
}

export function resolveTimelineFrameDurationMs(
    events: StoredPipelineTaskEvent[],
    _backendFrameDurationMs: number | null,
    lockedFrameDurationMs: number | null,
): number {
    if (lockedFrameDurationMs != null && lockedFrameDurationMs > 0) {
        return lockedFrameDurationMs;
    }
    return estimateFrameDurationFromFrameAnchors(events) ?? FALLBACK_FRAME_DURATION_MS;
}

export function resolveTimelineWindowBounds(
    windowEvents: StoredPipelineTaskEvent[],
    frameStart: number | null,
    frameDurationMs: number,
): {windowStartMs: number; windowEndMs: number} {
    const windowDurationMs = frameDurationMs * PIPELINE_TIMELINE_FRAME_WINDOW;
    let windowStartMs = 0;
    let windowEndMs = windowDurationMs;

    if (frameStart != null && windowEvents.length > 0) {
        const frameStartEvents = windowEvents.filter(e => e.frameNumber === frameStart);
        if (frameStartEvents.length > 0) {
            windowStartMs = Math.min(...frameStartEvents.map(e => e.startMs));
        } else {
            windowStartMs = Math.min(...windowEvents.map(e => e.startMs));
        }
        windowEndMs = windowStartMs + windowDurationMs;
    }

    return {windowStartMs, windowEndMs};
}

export function buildTimelineViewModel(params: {
    events: StoredPipelineTaskEvent[];
    backendFrameDurationMs: number | null;
    lockedFrameDurationMs?: number | null;
    droppedTimingEvents: number;
    logPipelineTimesEnabled: boolean;
    categoryFilters: TimelineCategoryFilters;
    paused: boolean;
    nowMs?: number;
}): PipelineTimelineViewModel {
    const nowMs = params.nowMs ?? performance.now();
    const framedEvents = params.events.filter(e => e.frameNumber != null);
    const latestFrame = framedEvents.length > 0
        ? Math.max(...framedEvents.map(e => e.frameNumber as number))
        : null;

    const frameDurationMs = resolveTimelineFrameDurationMs(
        params.events,
        params.backendFrameDurationMs,
        params.lockedFrameDurationMs ?? null,
    );

    let frameStart: number | null = null;
    let frameEnd: number | null = null;
    if (latestFrame != null) {
        frameEnd = latestFrame;
        frameStart = Math.max(0, latestFrame - (PIPELINE_TIMELINE_FRAME_WINDOW - 1));
    }

    const windowEvents = frameStart != null && frameEnd != null
        ? params.events.filter(e =>
            e.frameNumber != null
            && e.frameNumber >= frameStart!
            && e.frameNumber <= frameEnd!,
        )
        : [];

    const {windowStartMs, windowEndMs} = resolveTimelineWindowBounds(
        windowEvents,
        frameStart,
        frameDurationMs,
    );

    const orphanUiRows: TimelineRowView[] = orderTasksParentsBeforeChildren(
        params.events.filter(shouldShowWithoutFrameContext),
    )
        .map(e => eventToRow(e, windowStartMs, windowEndMs, nowMs))
        .filter(row => params.categoryFilters[row.category]);

    const sorted = orderTasksParentsBeforeChildren(windowEvents);
    const rows: TimelineRowView[] = [];
    const rowIndexById = new Map<string, number>();

    for (const event of sorted) {
        const category = classifyTaskCategory(event);
        if (!params.categoryFilters[category]) continue;
        const row = eventToRow(event, windowStartMs, windowEndMs, nowMs);
        if (!row.visible) continue;
        rowIndexById.set(event.taskId, rows.length);
        rows.push(row);
    }

    const edges: TimelineEdgeView[] = [];
    for (const event of sorted) {
        const toIndex = rowIndexById.get(event.taskId);
        if (toIndex === undefined) continue;
        for (const parentId of inferParentTaskIds(event)) {
            const fromIndex = rowIndexById.get(parentId);
            if (fromIndex === undefined || fromIndex === toIndex) continue;
            edges.push({
                fromTaskId: parentId,
                toTaskId: event.taskId,
                fromRowIndex: fromIndex,
                toRowIndex: toIndex,
            });
        }
    }

    return {
        windowStartMs,
        windowEndMs,
        windowDurationMs: Math.max(1, windowEndMs - windowStartMs),
        frameStart,
        frameEnd,
        latestFrame,
        frameDurationMs,
        rows,
        edges,
        orphanUiRows,
        droppedTimingEvents: params.droppedTimingEvents,
        logPipelineTimesEnabled: params.logPipelineTimesEnabled,
        paused: params.paused,
    };
}

function eventToRow(
    event: StoredPipelineTaskEvent,
    windowStartMs: number,
    windowEndMs: number,
    nowMs: number,
): TimelineRowView & {visible: boolean} {
    const clip = clipBarToWindow(event.startMs, event.endMs, windowStartMs, windowEndMs);
    const stale = nowMs - event.lastSeenMs > STALE_THRESHOLD_MS;
    return {
        taskId: event.taskId,
        label: taskLabel(event),
        category: classifyTaskCategory(event),
        frameNumber: event.frameNumber,
        barStartMs: event.startMs,
        barEndMs: event.endMs,
        clippedStartMs: clip.clippedStartMs,
        clippedEndMs: clip.clippedEndMs,
        durationMs: event.durationMs,
        sourceKey: event.sourceKey,
        stale,
        hasFrameContext: event.frameNumber != null,
        visible: clip.visible,
    };
}

export function barWidthPercent(
    row: Pick<TimelineRowView, 'clippedStartMs' | 'clippedEndMs'>,
    windowStartMs: number,
    windowDurationMs: number,
): {leftPct: number; widthPct: number} {
    const leftPct = ((row.clippedStartMs - windowStartMs) / windowDurationMs) * 100;
    const widthPct = ((row.clippedEndMs - row.clippedStartMs) / windowDurationMs) * 100;
    return {
        leftPct: Math.max(0, Math.min(100, leftPct)),
        widthPct: Math.max(0.15, Math.min(100, widthPct)),
    };
}

export function formatRulerTick(ms: number): string {
    if (ms >= 1000) return `${(ms / 1000).toFixed(1)}s`;
    return `${Math.round(ms)}ms`;
}
