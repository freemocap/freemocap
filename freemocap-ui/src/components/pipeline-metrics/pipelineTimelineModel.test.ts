import {describe, expect, it} from 'vitest';
import {
    barWidthPercent,
    buildTimelineViewModel,
    clipBarToWindow,
    DEFAULT_CATEGORY_FILTERS,
    estimateFrameDurationFromFrameAnchors,
    formatBarDuration,
    resolveFrameDurationMs,
    resolveTimelineWindowBounds,
    resolveTimelineFrameDurationMs,
    shouldShowWithoutFrameContext,
    shouldShowBarDurationLabel,
} from '@/components/pipeline-metrics/pipelineTimelineModel';
import {PIPELINE_TIMELINE_FRAME_WINDOW, FALLBACK_FRAME_DURATION_MS} from '@/services/server/server-helpers/pipeline-timing-types';
import type {StoredPipelineTaskEvent} from '@/services/server/server-helpers/pipeline-timing-types';

function makeEvent(overrides: Partial<StoredPipelineTaskEvent> & Pick<StoredPipelineTaskEvent, 'taskId'>): StoredPipelineTaskEvent {
    return {
        parentTaskIds: [],
        stage: 'test',
        nodeKind: 'camera',
        cameraId: 'cam0',
        frameNumber: 10,
        startMs: 100,
        endMs: 120,
        durationMs: 20,
        clockDomain: 'backend_perf',
        sourceKey: 'camera:cam0:test',
        lastSeenMs: 1000,
        ...overrides,
    };
}

describe('clipBarToWindow', () => {
    it('clips bars that extend past the window', () => {
        const clip = clipBarToWindow(50, 150, 100, 200);
        expect(clip.clippedStartMs).toBe(100);
        expect(clip.clippedEndMs).toBe(150);
        expect(clip.visible).toBe(true);
    });

    it('marks fully outside bars as not visible', () => {
        const clip = clipBarToWindow(10, 20, 100, 200);
        expect(clip.visible).toBe(false);
    });
});

describe('resolveFrameDurationMs', () => {
    it('uses backend frame duration when provided', () => {
        expect(resolveFrameDurationMs([], 33.3)).toBe(33.3);
    });

    it('falls back to 30fps when no timing data exists', () => {
        expect(resolveFrameDurationMs([], null)).toBe(FALLBACK_FRAME_DURATION_MS);
    });
});

describe('buildTimelineViewModel', () => {
    it('keeps only the rolling frame window', () => {
        const events: StoredPipelineTaskEvent[] = [];
        for (let frame = 1; frame <= 10; frame++) {
            events.push(makeEvent({
                taskId: `f${frame}`,
                frameNumber: frame,
                startMs: frame * 10,
                endMs: frame * 10 + 5,
            }));
        }
        const model = buildTimelineViewModel({
            events,
            backendFrameDurationMs: 33,
            droppedTimingEvents: 0,
            logPipelineTimesEnabled: true,
            categoryFilters: DEFAULT_CATEGORY_FILTERS,
            paused: false,
            nowMs: 5000,
        });
        expect(model.latestFrame).toBe(10);
        expect(model.frameStart).toBe(10 - (PIPELINE_TIMELINE_FRAME_WINDOW - 1));
        expect(model.rows).toHaveLength(PIPELINE_TIMELINE_FRAME_WINDOW);
    });

    it('builds multi-parent edges from explicit metadata', () => {
        const parentA = makeEvent({taskId: 'parent-a', frameNumber: 5, startMs: 0, endMs: 10});
        const parentB = makeEvent({taskId: 'parent-b', frameNumber: 5, startMs: 0, endMs: 10, nodeKind: 'aggregator', sourceKey: 'aggregator:loop'});
        const child = makeEvent({
            taskId: 'child',
            frameNumber: 5,
            parentTaskIds: ['parent-a', 'parent-b'],
            startMs: 10,
            endMs: 20,
        });
        const model = buildTimelineViewModel({
            events: [parentA, parentB, child],
            backendFrameDurationMs: 33,
            droppedTimingEvents: 0,
            logPipelineTimesEnabled: true,
            categoryFilters: DEFAULT_CATEGORY_FILTERS,
            paused: false,
            nowMs: 5000,
        });
        expect(model.edges).toHaveLength(2);
    });

    it('orders rows with parents above children', () => {
        const parent = makeEvent({taskId: 'parent', frameNumber: 5, startMs: 0, endMs: 10});
        const child = makeEvent({
            taskId: 'child',
            frameNumber: 5,
            parentTaskIds: ['parent'],
            startMs: 10,
            endMs: 20,
        });
        const model = buildTimelineViewModel({
            events: [child, parent],
            backendFrameDurationMs: 33,
            droppedTimingEvents: 0,
            logPipelineTimesEnabled: true,
            categoryFilters: DEFAULT_CATEGORY_FILTERS,
            paused: false,
            nowMs: 5000,
        });
        expect(model.rows.map(row => row.taskId)).toEqual(['parent', 'child']);
    });

    it('keeps a fixed timeline scale after startup', () => {
        const lockedFrameDurationMs = 33;
        const fixedDuration = lockedFrameDurationMs * PIPELINE_TIMELINE_FRAME_WINDOW;
        const model1 = buildTimelineViewModel({
            events: [makeEvent({taskId: 'a', frameNumber: 1, startMs: 0, endMs: 5})],
            backendFrameDurationMs: lockedFrameDurationMs,
            lockedFrameDurationMs,
            droppedTimingEvents: 0,
            logPipelineTimesEnabled: true,
            categoryFilters: DEFAULT_CATEGORY_FILTERS,
            paused: false,
            nowMs: 5000,
        });
        expect(model1.windowDurationMs).toBe(fixedDuration);

        const model2 = buildTimelineViewModel({
            events: [
                makeEvent({taskId: 'a', frameNumber: 1, startMs: 0, endMs: 5}),
                makeEvent({taskId: 'b', frameNumber: 2, startMs: 100, endMs: 200}),
            ],
            backendFrameDurationMs: 50,
            lockedFrameDurationMs,
            droppedTimingEvents: 0,
            logPipelineTimesEnabled: true,
            categoryFilters: DEFAULT_CATEGORY_FILTERS,
            paused: false,
            nowMs: 5000,
        });
        expect(model2.windowDurationMs).toBe(fixedDuration);
    });

    it('shows preview rows without frame context', () => {
        const preview = makeEvent({
            taskId: 'preview',
            frameNumber: null,
            nodeKind: 'camera',
            stage: 'jpeg_resize',
            sourceKey: 'camera:cam0:jpeg_resize',
            startMs: 195,
            endMs: 200,
            durationMs: 5,
        });
        const model = buildTimelineViewModel({
            events: [
                makeEvent({taskId: 'f1', frameNumber: 1, startMs: 100, endMs: 105}),
                makeEvent({taskId: 'f2', frameNumber: 2, startMs: 133, endMs: 138}),
                makeEvent({taskId: 'f3', frameNumber: 3, startMs: 166, endMs: 171}),
                preview,
            ],
            backendFrameDurationMs: 33,
            lockedFrameDurationMs: 33,
            droppedTimingEvents: 0,
            logPipelineTimesEnabled: true,
            categoryFilters: DEFAULT_CATEGORY_FILTERS,
            paused: false,
            nowMs: 5000,
        });
        expect(model.orphanUiRows.map(row => row.taskId)).toContain('preview');
        expect(model.orphanUiRows.find(row => row.taskId === 'preview')?.category).toBe('ui_backend');
    });
});

describe('resolveTimelineFrameDurationMs', () => {
    it('uses locked frame duration when set', () => {
        expect(resolveTimelineFrameDurationMs([], 50, 33)).toBe(33);
    });

    it('does not use backend framerate telemetry before scale is locked', () => {
        expect(resolveTimelineFrameDurationMs([], 10, null)).toBe(FALLBACK_FRAME_DURATION_MS);
    });
});

describe('estimateFrameDurationFromFrameAnchors', () => {
    it('uses median frame-to-frame delta from earliest event per frame', () => {
        expect(estimateFrameDurationFromFrameAnchors([
            makeEvent({taskId: 'f1-late', frameNumber: 1, startMs: 105}),
            makeEvent({taskId: 'f1-early', frameNumber: 1, startMs: 100}),
            makeEvent({taskId: 'f2', frameNumber: 2, startMs: 133}),
            makeEvent({taskId: 'f3', frameNumber: 3, startMs: 166}),
        ])).toBe(33);
    });

    it('waits for enough distinct frame anchors', () => {
        expect(estimateFrameDurationFromFrameAnchors([
            makeEvent({taskId: 'f1', frameNumber: 1, startMs: 100}),
            makeEvent({taskId: 'f2', frameNumber: 2, startMs: 133}),
        ])).toBeNull();
    });
});

describe('shouldShowWithoutFrameContext', () => {
    it('includes UI and preview rows without frame numbers', () => {
        expect(shouldShowWithoutFrameContext(makeEvent({
            taskId: 'ui',
            frameNumber: null,
            nodeKind: 'ui',
            stage: 'raf_to_rendered_ms',
            sourceKey: 'ui:cam0:raf_to_rendered_ms',
        }))).toBe(true);
        expect(shouldShowWithoutFrameContext(makeEvent({
            taskId: 'preview',
            frameNumber: null,
            nodeKind: 'camera',
            stage: 'jpeg_encode',
            sourceKey: 'camera:cam0:jpeg_encode',
        }))).toBe(true);
    });

    it('excludes duplicate non-frame tracking rows', () => {
        expect(shouldShowWithoutFrameContext(makeEvent({
            taskId: 'tracking',
            frameNumber: null,
            nodeKind: 'skeleton_inference',
            stage: 'predict_batch',
            sourceKey: 'skeleton_inference:predict_batch',
        }))).toBe(false);
    });
});

describe('resolveTimelineWindowBounds', () => {
    it('uses a fixed window width from locked frame duration', () => {
        const bounds = resolveTimelineWindowBounds(
            [makeEvent({taskId: 'a', frameNumber: 2, startMs: 100, endMs: 200})],
            2,
            33,
        );
        expect(bounds.windowEndMs - bounds.windowStartMs).toBe(33 * PIPELINE_TIMELINE_FRAME_WINDOW);
        expect(bounds.windowStartMs).toBe(100);
    });
});

describe('barWidthPercent', () => {
    it('maps clipped intervals to percentage widths', () => {
        const pct = barWidthPercent(
            {clippedStartMs: 25, clippedEndMs: 75},
            0,
            100,
        );
        expect(pct.leftPct).toBe(25);
        expect(pct.widthPct).toBe(50);
    });
});

describe('formatBarDuration', () => {
    it('formats durations for bar labels', () => {
        expect(formatBarDuration(123.4)).toBe('123 ms');
        expect(formatBarDuration(12.34)).toBe('12.3 ms');
        expect(formatBarDuration(1.234)).toBe('1.23 ms');
    });
});

describe('shouldShowBarDurationLabel', () => {
    it('shows label when bar is wide enough for the text', () => {
        expect(shouldShowBarDurationLabel(10, '12.3 ms')).toBe(true);
        expect(shouldShowBarDurationLabel(2, '12.3 ms')).toBe(false);
    });
});
