import {describe, expect, it} from 'vitest';
import {
    barWidthPercent,
    barWidthPercentInViewport,
    buildTimelineViewModel,
    clipBarToWindow,
    DEFAULT_CATEGORY_FILTERS,
    estimateFrameDurationFromFrameAnchors,
    formatBarDuration,
    resolveFrameDurationMs,
    resolveTimelineWindowBounds,
    resolveTimelineFrameDurationMs,
    resolveVisibleTimelineWindow,
    shouldShowWithoutFrameContext,
    shouldShowBarDurationLabel,
    zoomTimelineAtPointer,
} from '@/components/pipeline-metrics/pipelineTimelineModel';
import {PIPELINE_TIMELINE_FRAME_WINDOW, FALLBACK_FRAME_DURATION_MS} from '@/services/server/server-helpers/pipeline-timing-types';
import type {StoredPipelineTaskEvent} from '@/services/server/server-helpers/pipeline-timing-types';
import {buildDeterministicTaskId} from '@/components/pipeline-metrics/pipelineTaskTopology';

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

describe('timeline chart zoom', () => {
    it('resolves visible window from zoom and pan', () => {
        const visible = resolveVisibleTimelineWindow(100, 200, 2, 50);
        expect(visible.visibleStartMs).toBe(150);
        expect(visible.visibleDurationMs).toBe(100);
        expect(visible.zoomLevel).toBe(2);
    });

    it('zooms in toward the pointer', () => {
        const next = zoomTimelineAtPointer(0, 100, 1, 0, 0.5, true);
        const visible = resolveVisibleTimelineWindow(0, 100, next.zoomLevel, next.panMs);
        expect(visible.visibleDurationMs).toBeLessThan(100);
        expect(visible.visibleStartMs).toBeGreaterThan(0);
        expect(visible.visibleEndMs).toBeLessThan(100);
    });

    it('clips bars to the visible viewport', () => {
        const pct = barWidthPercentInViewport(
            {barStartMs: 40, barEndMs: 80},
            50,
            100,
        );
        expect(pct.visible).toBe(true);
        expect(pct.leftPct).toBeCloseTo(0);
        expect(pct.widthPct).toBeCloseTo(30);
    });
});

describe('skeleton preprocess alignment', () => {
    it('attaches parent span metadata to preprocess child rows', () => {
        const frame = 5;
        const preprocessId = buildDeterministicTaskId({
            frameNumber: frame,
            nodeKind: 'skeleton_inference',
            stage: 'human_detection_preprocess',
            scope: 'batch',
        });
        const model = buildTimelineViewModel({
            events: [
                makeEvent({
                    taskId: buildDeterministicTaskId({
                        frameNumber: frame,
                        nodeKind: 'skeleton_inference',
                        stage: 'predict_batch',
                        scope: 'batch',
                    }),
                    frameNumber: frame,
                    nodeKind: 'skeleton_inference',
                    stage: 'predict_batch',
                    sourceKey: 'skeleton_inference:predict_batch',
                    startMs: 95,
                    endMs: 115,
                    durationMs: 20,
                }),
                makeEvent({
                    taskId: preprocessId,
                    frameNumber: frame,
                    nodeKind: 'skeleton_inference',
                    stage: 'human_detection_preprocess',
                    sourceKey: 'skeleton_inference:human_detection_preprocess',
                    startMs: 100,
                    endMs: 110,
                    durationMs: 10,
                }),
                makeEvent({
                    taskId: `${frame}:cam_a:skeleton_inference:human_detection_letterbox`,
                    frameNumber: frame,
                    nodeKind: 'skeleton_inference',
                    stage: 'human_detection_letterbox',
                    sourceKey: 'skeleton_inference:cam_a:human_detection_letterbox',
                    startMs: 100,
                    endMs: 105,
                    durationMs: 5,
                }),
                makeEvent({
                    taskId: buildDeterministicTaskId({
                        frameNumber: frame,
                        nodeKind: 'skeleton_inference',
                        stage: 'human_detection_batch_pack',
                        scope: 'batch',
                    }),
                    frameNumber: frame,
                    nodeKind: 'skeleton_inference',
                    stage: 'human_detection_batch_pack',
                    sourceKey: 'skeleton_inference:human_detection_batch_pack',
                    startMs: 105,
                    endMs: 110,
                    durationMs: 5,
                }),
            ],
            backendFrameDurationMs: 33,
            droppedTimingEvents: 0,
            logPipelineTimesEnabled: true,
            categoryFilters: DEFAULT_CATEGORY_FILTERS,
            paused: false,
            nowMs: 5000,
        });

        const letterbox = model.rows.find(row => row.sourceKey.includes('letterbox'));
        const batchPack = model.rows.find(row => row.sourceKey.includes('batch_pack'));
        const preprocess = model.rows.find(row => row.sourceKey.includes('human_detection_preprocess'));
        expect(letterbox?.indentLevel).toBe(2);
        expect(preprocess?.indentLevel).toBe(1);
        expect(letterbox?.parentSpanStartMs).toBe(100);
        expect(letterbox?.parentSpanEndMs).toBe(110);
        expect(batchPack?.parentSpanStartMs).toBe(100);
        expect(batchPack?.parentSpanEndMs).toBe(110);
        expect(preprocess?.parentSpanStartMs).toBe(95);
        expect(preprocess?.parentSpanEndMs).toBe(115);
    });

    it('places predict_batch above inner stages in row order', () => {
        const frame = 5;
        const model = buildTimelineViewModel({
            events: [
                makeEvent({
                    taskId: buildDeterministicTaskId({
                        frameNumber: frame,
                        nodeKind: 'skeleton_inference',
                        stage: 'frame_read',
                        scope: 'batch',
                    }),
                    frameNumber: frame,
                    nodeKind: 'skeleton_inference',
                    stage: 'frame_read',
                    sourceKey: 'skeleton_inference:frame_read',
                    startMs: 90,
                    endMs: 95,
                    durationMs: 5,
                }),
                makeEvent({
                    taskId: buildDeterministicTaskId({
                        frameNumber: frame,
                        nodeKind: 'skeleton_inference',
                        stage: 'predict_batch',
                        scope: 'batch',
                    }),
                    frameNumber: frame,
                    nodeKind: 'skeleton_inference',
                    stage: 'predict_batch',
                    sourceKey: 'skeleton_inference:predict_batch',
                    startMs: 95,
                    endMs: 130,
                    durationMs: 35,
                }),
                makeEvent({
                    taskId: buildDeterministicTaskId({
                        frameNumber: frame,
                        nodeKind: 'skeleton_inference',
                        stage: 'human_detection',
                        scope: 'batch',
                    }),
                    frameNumber: frame,
                    nodeKind: 'skeleton_inference',
                    stage: 'human_detection',
                    sourceKey: 'skeleton_inference:human_detection',
                    startMs: 110,
                    endMs: 125,
                    durationMs: 15,
                }),
            ],
            backendFrameDurationMs: 33,
            droppedTimingEvents: 0,
            logPipelineTimesEnabled: true,
            categoryFilters: DEFAULT_CATEGORY_FILTERS,
            paused: false,
            nowMs: 5000,
        });

        expect(model.rows.map(row => row.sourceKey)).toEqual([
            'skeleton_inference:frame_read',
            'skeleton_inference:predict_batch',
            'skeleton_inference:human_detection',
        ]);
        expect(model.rows[2]?.indentLevel).toBe(1);
    });
});
