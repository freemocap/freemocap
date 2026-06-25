import {describe, expect, it} from 'vitest';
import {
    buildDeterministicTaskId,
    classifyTaskCategory,
    inferParentTaskIds,
    orderTasksParentsBeforeChildren,
} from '@/components/pipeline-metrics/pipelineTaskTopology';
import {PipelineTimingStore, normalizeBackendPerfNsToRendererMs} from '@/services/server/server-helpers/pipeline-timing-store';

describe('buildDeterministicTaskId', () => {
    it('builds stable per-camera task ids', () => {
        expect(buildDeterministicTaskId({
            frameNumber: 42,
            cameraId: 'cam0',
            nodeKind: 'camera',
            stage: 'jpeg_encode_ms',
        })).toBe('42:cam0:camera:jpeg_encode_ms');
    });

    it('builds batch and aggregator ids', () => {
        expect(buildDeterministicTaskId({
            frameNumber: 7,
            nodeKind: 'skeleton_inference',
            stage: 'predict_batch',
            scope: 'batch',
        })).toBe('7:batch:skeleton_inference:predict_batch');
        expect(buildDeterministicTaskId({
            frameNumber: 7,
            nodeKind: 'aggregator',
            stage: 'loop_time',
            scope: 'aggregator',
        })).toBe('7:aggregator:loop_time');
    });
});

describe('normalizeBackendPerfNsToRendererMs', () => {
    it('aligns backend monotonic timestamps to renderer ingest time', () => {
        const relayNs = 1_000_000_000;
        const eventNs = 999_000_000;
        const ingestMs = 5000;
        const rendererMs = normalizeBackendPerfNsToRendererMs(eventNs, ingestMs, relayNs);
        expect(rendererMs).toBeCloseTo(4999, 5);
    });
});

describe('PipelineTimingStore UI frame correlation', () => {
    it('stores UI events with frame numbers for timeline joins', () => {
        const store = new PipelineTimingStore();
        store.recordJpegDecodeWorker('cam0', 12.5, {frameNumber: 99});
        const snap = store.getTimelineSnapshot();
        const uiEvent = snap.events.find(e => e.nodeKind === 'ui');
        expect(uiEvent?.frameNumber).toBe(99);
        expect(uiEvent?.taskId).toBe('99:cam0:ui:jpeg_decode_worker_ms');
    });
});

describe('inferParentTaskIds', () => {
    it('prefers explicit parent_task_ids', () => {
        const event = {
            taskId: 'child',
            parentTaskIds: ['a', 'b'],
            stage: 'x',
            nodeKind: 'camera',
            cameraId: 'cam0',
            frameNumber: 3,
            startMs: 0,
            endMs: 1,
            durationMs: 1,
            clockDomain: 'backend_perf' as const,
            sourceKey: 'camera:cam0:x',
            lastSeenMs: 0,
        };
        expect(inferParentTaskIds(event)).toEqual(['a', 'b']);
    });

    it('classifies ui_frontend rows', () => {
        expect(classifyTaskCategory({
            nodeKind: 'ui',
            stage: 'raf_to_rendered_ms',
            sourceKey: 'ui:cam0:raf_to_rendered_ms',
        })).toBe('ui_frontend');
    });

    it('classifies capture-to-aggregator as capture', () => {
        expect(classifyTaskCategory({
            nodeKind: 'aggregator',
            stage: 'capture_to_aggregator_ms',
            sourceKey: 'aggregator:capture_to_aggregator_ms',
        })).toBe('capture');
    });
});

describe('orderTasksParentsBeforeChildren', () => {
    const baseEvent = {
        parentTaskIds: [] as string[],
        stage: 'test',
        nodeKind: 'camera' as const,
        cameraId: 'cam0',
        frameNumber: 5,
        startMs: 0,
        endMs: 10,
        durationMs: 10,
        clockDomain: 'backend_perf' as const,
        sourceKey: 'camera:cam0:test',
        lastSeenMs: 1000,
    };

    it('places parents above children', () => {
        const parent = {...baseEvent, taskId: 'parent', startMs: 0, endMs: 10};
        const child = {
            ...baseEvent,
            taskId: 'child',
            parentTaskIds: ['parent'],
            startMs: 10,
            endMs: 20,
        };
        const ordered = orderTasksParentsBeforeChildren([child, parent]);
        expect(ordered.map(event => event.taskId)).toEqual(['parent', 'child']);
    });

    it('orders multi-level chains parent-first', () => {
        const grandparent = {...baseEvent, taskId: 'gp', startMs: 0, endMs: 5};
        const parent = {...baseEvent, taskId: 'p', parentTaskIds: ['gp'], startMs: 5, endMs: 10};
        const child = {...baseEvent, taskId: 'c', parentTaskIds: ['p'], startMs: 10, endMs: 15};
        const ordered = orderTasksParentsBeforeChildren([child, parent, grandparent]);
        expect(ordered.map(event => event.taskId)).toEqual(['gp', 'p', 'c']);
    });
});

describe('PipelineTimingStore dropped events', () => {
    it('accumulates dropped_timing_events from backend payloads', () => {
        const store = new PipelineTimingStore();
        store.ingestBackendMessage({
            message_type: 'pipeline_timing',
            camera_group_id: 'default',
            dropped_timing_events: 3,
        });
        expect(store.getTimelineSnapshot().droppedTimingEvents).toBe(3);
    });
});

describe('PipelineTimingStore locked timeline scale', () => {
    it('locks frame duration from configured camera fps', () => {
        const store = new PipelineTimingStore();
        store.ingestBackendMessage({
            message_type: 'pipeline_timing',
            camera_group_id: 'default',
            configured_camera_fps_hz: 20,
        });
        expect(store.getTimelineSnapshot().lockedFrameDurationMs).toBe(50);
    });

    it('does not lock frame duration from backend framerate telemetry', () => {
        const store = new PipelineTimingStore();
        store.setBackendFrameDurationMs(10);
        expect(store.getTimelineSnapshot().lockedFrameDurationMs).toBeNull();
    });

    it('locks frame duration from measured startup frame cadence', () => {
        const store = new PipelineTimingStore();
        store.ingestBackendMessage({
            message_type: 'pipeline_timing',
            camera_group_id: 'default',
            relay_perf_counter_ns: 1_000_000_000,
            events: [
                {
                    task_id: 'f1',
                    stage: 'test',
                    node_kind: 'camera',
                    camera_id: 'cam0',
                    frame_number: 1,
                    start_time_ns: 1_000_000_000,
                    end_time_ns: 1_001_000_000,
                    duration_ms: 1,
                },
                {
                    task_id: 'f2',
                    stage: 'test',
                    node_kind: 'camera',
                    camera_id: 'cam0',
                    frame_number: 2,
                    start_time_ns: 1_033_000_000,
                    end_time_ns: 1_034_000_000,
                    duration_ms: 1,
                },
                {
                    task_id: 'f3',
                    stage: 'test',
                    node_kind: 'camera',
                    camera_id: 'cam0',
                    frame_number: 3,
                    start_time_ns: 1_066_000_000,
                    end_time_ns: 1_067_000_000,
                    duration_ms: 1,
                },
            ],
        });
        expect(store.getTimelineSnapshot().lockedFrameDurationMs).toBe(33);
    });

    it('clears locked frame duration on reset', () => {
        const store = new PipelineTimingStore();
        store.ingestBackendMessage({
            message_type: 'pipeline_timing',
            camera_group_id: 'default',
            configured_camera_fps_hz: 30,
        });
        store.clear();
        expect(store.getTimelineSnapshot().lockedFrameDurationMs).toBeNull();
    });
});
