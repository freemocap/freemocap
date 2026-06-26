import {describe, expect, it, vi} from 'vitest';
import {
    buildDeterministicTaskId,
    classifyTaskCategory,
    inferParentTaskIds,
    normalizeSkeletonInferenceTiming,
    normalizeSkeletonPreprocessTiming,
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

    it('nests human-detection preprocess child stages under preprocess', () => {
        const preprocessId = buildDeterministicTaskId({
            frameNumber: 8,
            nodeKind: 'skeleton_inference',
            stage: 'human_detection_preprocess',
            scope: 'batch',
        });
        const letterbox = {
            taskId: '8:cam_a:skeleton_inference:human_detection_letterbox',
            parentTaskIds: ['8:batch:skeleton_inference:frame_read'],
            stage: 'human_detection_letterbox',
            nodeKind: 'skeleton_inference' as const,
            cameraId: 'cam_a',
            frameNumber: 8,
            startMs: 10,
            endMs: 12,
            durationMs: 2,
            clockDomain: 'backend_perf' as const,
            sourceKey: 'skeleton_inference:cam_a:human_detection_letterbox',
            lastSeenMs: 0,
        };
        expect(inferParentTaskIds(letterbox)).toEqual([preprocessId]);
    });

    it('nests predict_batch inner stages under predict_batch', () => {
        const frame = 9;
        const predictBatchId = buildDeterministicTaskId({
            frameNumber: frame,
            nodeKind: 'skeleton_inference',
            stage: 'predict_batch',
            scope: 'batch',
        });
        const detection = {
            taskId: buildDeterministicTaskId({
                frameNumber: frame,
                nodeKind: 'skeleton_inference',
                stage: 'human_detection',
                scope: 'batch',
            }),
            parentTaskIds: [`${frame}:batch:skeleton_inference:frame_read`],
            stage: 'human_detection',
            nodeKind: 'skeleton_inference' as const,
            cameraId: null,
            frameNumber: frame,
            startMs: 20,
            endMs: 30,
            durationMs: 10,
            clockDomain: 'backend_perf' as const,
            sourceKey: 'skeleton_inference:human_detection',
            lastSeenMs: 0,
        };
        expect(inferParentTaskIds(detection)).toEqual([predictBatchId]);
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

    it('places predict_batch above inner GPU stages', () => {
        const frame = 15;
        const frameReadId = buildDeterministicTaskId({
            frameNumber: frame,
            nodeKind: 'skeleton_inference',
            stage: 'frame_read',
            scope: 'batch',
        });
        const predictBatchId = buildDeterministicTaskId({
            frameNumber: frame,
            nodeKind: 'skeleton_inference',
            stage: 'predict_batch',
            scope: 'batch',
        });
        const preprocessId = buildDeterministicTaskId({
            frameNumber: frame,
            nodeKind: 'skeleton_inference',
            stage: 'human_detection_preprocess',
            scope: 'batch',
        });
        const frameRead = {
            ...baseEvent,
            taskId: frameReadId,
            nodeKind: 'skeleton_inference' as const,
            stage: 'frame_read',
            sourceKey: 'skeleton_inference:frame_read',
            startMs: 0,
            endMs: 5,
        };
        const predictBatch = {
            ...baseEvent,
            taskId: predictBatchId,
            nodeKind: 'skeleton_inference' as const,
            stage: 'predict_batch',
            sourceKey: 'skeleton_inference:predict_batch',
            startMs: 5,
            endMs: 40,
        };
        const preprocess = {
            ...baseEvent,
            taskId: preprocessId,
            nodeKind: 'skeleton_inference' as const,
            stage: 'human_detection_preprocess',
            sourceKey: 'skeleton_inference:human_detection_preprocess',
            startMs: 6,
            endMs: 12,
        };
        const detection = {
            ...baseEvent,
            taskId: buildDeterministicTaskId({
                frameNumber: frame,
                nodeKind: 'skeleton_inference',
                stage: 'human_detection',
                scope: 'batch',
            }),
            nodeKind: 'skeleton_inference' as const,
            stage: 'human_detection',
            sourceKey: 'skeleton_inference:human_detection',
            startMs: 12,
            endMs: 25,
        };
        const ordered = orderTasksParentsBeforeChildren([
            detection,
            preprocess,
            predictBatch,
            frameRead,
        ]);
        expect(ordered.map(event => event.stage)).toEqual([
            'frame_read',
            'predict_batch',
            'human_detection_preprocess',
            'human_detection',
        ]);
    });

    it('places preprocess child stages directly under preprocess', () => {
        const frame = 12;
        const preprocess = {
            ...baseEvent,
            taskId: buildDeterministicTaskId({
                frameNumber: frame,
                nodeKind: 'skeleton_inference',
                stage: 'human_detection_preprocess',
                scope: 'batch',
            }),
            nodeKind: 'skeleton_inference' as const,
            stage: 'human_detection_preprocess',
            sourceKey: 'skeleton_inference:human_detection_preprocess',
            startMs: 10,
            endMs: 20,
        };
        const letterbox = {
            ...baseEvent,
            taskId: `${frame}:cam_a:skeleton_inference:human_detection_letterbox`,
            nodeKind: 'skeleton_inference' as const,
            stage: 'human_detection_letterbox',
            sourceKey: 'skeleton_inference:cam_a:human_detection_letterbox',
            startMs: 11,
            endMs: 15,
        };
        const batchPack = {
            ...baseEvent,
            taskId: buildDeterministicTaskId({
                frameNumber: frame,
                nodeKind: 'skeleton_inference',
                stage: 'human_detection_batch_pack',
                scope: 'batch',
            }),
            nodeKind: 'skeleton_inference' as const,
            stage: 'human_detection_batch_pack',
            sourceKey: 'skeleton_inference:human_detection_batch_pack',
            startMs: 15,
            endMs: 18,
        };
        const detection = {
            ...baseEvent,
            taskId: buildDeterministicTaskId({
                frameNumber: frame,
                nodeKind: 'skeleton_inference',
                stage: 'human_detection',
                scope: 'batch',
            }),
            nodeKind: 'skeleton_inference' as const,
            stage: 'human_detection',
            sourceKey: 'skeleton_inference:human_detection',
            startMs: 20,
            endMs: 30,
        };
        const ordered = orderTasksParentsBeforeChildren([detection, batchPack, letterbox, preprocess]);
        expect(ordered.map(event => event.stage)).toEqual([
            'human_detection_preprocess',
            'human_detection_letterbox',
            'human_detection_batch_pack',
            'human_detection',
        ]);
    });

    it('aligns preprocess parent span to child start/end times', () => {
        const frame = 20;
        const preprocessId = buildDeterministicTaskId({
            frameNumber: frame,
            nodeKind: 'skeleton_inference',
            stage: 'human_detection_preprocess',
            scope: 'batch',
        });
        const events = normalizeSkeletonInferenceTiming([
            {
                ...baseEvent,
                taskId: preprocessId,
                frameNumber: frame,
                nodeKind: 'skeleton_inference',
                stage: 'human_detection_preprocess',
                sourceKey: 'skeleton_inference:human_detection_preprocess',
                startMs: 99,
                endMs: 105,
                durationMs: 6,
            },
            {
                ...baseEvent,
                taskId: `${frame}:cam_a:skeleton_inference:human_detection_letterbox`,
                frameNumber: frame,
                nodeKind: 'skeleton_inference',
                stage: 'human_detection_letterbox',
                sourceKey: 'skeleton_inference:cam_a:human_detection_letterbox',
                startMs: 100,
                endMs: 103,
                durationMs: 3,
            },
            {
                ...baseEvent,
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
                startMs: 103,
                endMs: 108,
                durationMs: 5,
            },
        ]);

        const preprocess = events.find(event => event.taskId === preprocessId);
        const letterbox = events.find(event => event.stage === 'human_detection_letterbox');
        const batchPack = events.find(event => event.stage === 'human_detection_batch_pack');
        expect(preprocess?.startMs).toBe(100);
        expect(preprocess?.endMs).toBe(108);
        expect(letterbox?.parentTaskIds).toEqual([preprocessId]);
        expect(batchPack?.parentTaskIds).toEqual([preprocessId]);
    });
});

describe('PipelineTimingStore contextless event pruning', () => {
    it('keeps only the last 10 frameless events per sourceKey', () => {
        const store = new PipelineTimingStore();
        const rowKey = 'camera:cam0:jpeg_resize';
        for (let i = 0; i < 15; i++) {
            store.ingestBackendMessage({
                message_type: 'pipeline_timing',
                camera_group_id: 'default',
                events: [{
                    task_id: `orphan-${i}`,
                    stage: 'jpeg_resize',
                    node_kind: 'camera',
                    camera_id: 'cam0',
                    duration_ms: i + 1,
                }],
            });
        }
        const frameless = store.getTimelineSnapshot().events
            .filter(e => e.frameNumber == null && e.sourceKey === rowKey);
        expect(frameless.length).toBe(10);
        expect(frameless.map(e => e.taskId).sort())
            .toEqual(['orphan-10', 'orphan-11', 'orphan-12', 'orphan-13', 'orphan-14', 'orphan-5', 'orphan-6', 'orphan-7', 'orphan-8', 'orphan-9']);
    });

    it('prunes frameless UI orphan events independently per stage', () => {
        let now = 1000;
        vi.spyOn(performance, 'now').mockImplementation(() => now++);
        const store = new PipelineTimingStore();
        for (let i = 0; i < 12; i++) {
            store.recordJpegDecodeWorker('cam0', i + 1);
            store.recordJpegDecodeMainWait('cam0', i + 100);
        }
        const decode = store.getTimelineSnapshot().events
            .filter(e => e.frameNumber == null && e.stage === 'jpeg_decode_worker_ms');
        const wait = store.getTimelineSnapshot().events
            .filter(e => e.frameNumber == null && e.stage === 'jpeg_decode_main_wait_ms');
        expect(decode.length).toBe(10);
        expect(wait.length).toBe(10);
        vi.restoreAllMocks();
    });

    it('does not prune framed events via contextless cap', () => {
        const store = new PipelineTimingStore();
        for (let frame = 1; frame <= 20; frame++) {
            store.ingestBackendMessage({
                message_type: 'pipeline_timing',
                camera_group_id: 'default',
                relay_perf_counter_ns: frame * 1_000_000_000,
                events: [{
                    task_id: `f${frame}`,
                    stage: 'test',
                    node_kind: 'camera',
                    camera_id: 'cam0',
                    frame_number: frame,
                    start_time_ns: frame * 1_000_000_000,
                    end_time_ns: frame * 1_000_000_000 + 1_000_000,
                    duration_ms: 1,
                }],
            });
        }
        const framed = store.getTimelineSnapshot().events.filter(e => e.frameNumber != null);
        expect(framed.length).toBe(6);
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
