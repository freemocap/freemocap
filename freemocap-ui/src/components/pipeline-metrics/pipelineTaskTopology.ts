import type {PipelineTaskCategory, StoredPipelineTaskEvent} from '@/services/server/server-helpers/pipeline-timing-types';

const UI_BACKEND_PREVIEW_STAGES = new Set([
    'jpeg_rotate',
    'jpeg_resize',
    'jpeg_encode',
    'ws_payload_prepare',
    'jpeg_rotate_ms',
    'jpeg_resize_ms',
    'jpeg_encode_ms',
    'ws_payload_prepare_ms',
]);

export function buildDeterministicTaskId(params: {
    frameNumber: number;
    cameraId?: string | null;
    nodeKind: string;
    stage: string;
    scope?: 'batch' | 'aggregator' | 'ui';
}): string {
    const {frameNumber, cameraId, nodeKind, stage, scope} = params;
    if (scope === 'batch') {
        return `${frameNumber}:batch:${nodeKind}:${stage}`;
    }
    if (scope === 'aggregator') {
        return `${frameNumber}:aggregator:${stage}`;
    }
    if (scope === 'ui' || nodeKind === 'ui') {
        const cam = cameraId ?? 'unknown';
        return `${frameNumber}:${cam}:ui:${stage}`;
    }
    const cam = cameraId ?? 'unknown';
    return `${frameNumber}:${cam}:${nodeKind}:${stage}`;
}

export function classifyTaskCategory(event: Pick<StoredPipelineTaskEvent, 'nodeKind' | 'stage' | 'sourceKey'>): PipelineTaskCategory {
    const {nodeKind, stage, sourceKey} = event;
    if (nodeKind === 'ui' || sourceKey.startsWith('ui:')) {
        return 'ui_frontend';
    }
    if (stage === 'capture_to_aggregator_ms') {
        return 'capture';
    }
    if (nodeKind === 'aggregator' || sourceKey.startsWith('aggregator:')) {
        return 'aggregation';
    }
    if (nodeKind === 'skeleton_inference' || sourceKey.startsWith('skeleton_inference:')) {
        return 'tracking';
    }
    if (nodeKind === 'multiframe' || sourceKey.startsWith('multiframe:')) {
        if (UI_BACKEND_PREVIEW_STAGES.has(stage)) {
            return 'ui_backend';
        }
        return 'capture';
    }
    if (nodeKind === 'camera' || sourceKey.startsWith('camera:')) {
        if (stage === 'skeleton_detection' || stage === 'charuco_detection') {
            return 'tracking';
        }
        if (UI_BACKEND_PREVIEW_STAGES.has(stage)) {
            return 'ui_backend';
        }
        return 'capture';
    }
    return 'other';
}

const PRETTY_STAGE_LABELS: Record<string, string> = {
    'multiframe:inter_camera_grab_spread_ms': 'Inter-camera grab spread',
    'multiframe:ws_payload_prepare_ms': 'WS payload prepare',
    'skeleton_inference:frame_read': 'Skeleton GPU: frame read',
    'skeleton_inference:human_detection_letterbox': 'Skeleton GPU: human detection letterbox',
    'skeleton_inference:human_detection_batch_pack': 'Skeleton GPU: human detection batch pack',
    'skeleton_inference:human_detection_preprocess': 'Skeleton GPU: human detection preprocess',
    'skeleton_inference:human_detection': 'Skeleton GPU: human detection',
    'skeleton_inference:human_detection_postprocess': 'Skeleton GPU: human detection postprocess',
    'skeleton_inference:pose_estimation_preprocess': 'Skeleton GPU: pose estimation preprocess',
    'skeleton_inference:pose_estimation': 'Skeleton GPU: pose estimation',
    'skeleton_inference:pose_estimation_postprocess': 'Skeleton GPU: pose estimation postprocess',
    'skeleton_inference:predict_batch': 'Skeleton GPU: predict batch',
    'aggregator:capture_to_aggregator_ms': 'Capture → aggregator',
    'aggregator:frame_collection_wait': 'Frame collection wait',
    'aggregator:skeleton_triangulation': 'Skeleton triangulation',
    'aggregator:charuco_triangulation': 'Charuco triangulation',
    'aggregator:keypoint_filter': 'Keypoint filter',
    'aggregator:velocity_gate': 'Velocity gate',
    'aggregator:skeleton_filter': 'Skeleton filter',
    'aggregator:full_frame_processing': 'Full frame processing',
    'aggregator:loop_time': 'Aggregator loop time',
    'camera:jpeg_encode': 'JPEG encode (server)',
    'camera:jpeg_resize': 'JPEG resize (server)',
    'camera:jpeg_rotate': 'JPEG rotate (server)',
    'camera:ws_payload_prepare': 'WS payload prepare (server)',
    'camera:jpeg_encode_ms': 'JPEG encode (server)',
    'camera:jpeg_resize_ms': 'JPEG resize (server)',
    'camera:jpeg_rotate_ms': 'JPEG rotate (server)',
    'camera:ws_payload_prepare_ms': 'WS payload prepare (server)',
    'camera:grab_request_to_success_ms': 'Grab request → success',
    'camera:retrieve_request_to_success_ms': 'Retrieve request → success',
    'ui:jpeg_ack_to_receive_ms': 'UI: ACK → JPEG received',
    'ui:jpeg_ws_binary_interval_ms': 'UI: WS binary spacing',
    'ui:jpeg_ws_dispatch_lag_ms': 'UI: WS binary handler lag',
    'ui:raf_body_before_decode_ms': 'UI: rAF body before decode',
    'ui:jpeg_decode_worker_ms': 'UI: JPEG decode (worker)',
    'ui:jpeg_decode_main_wait_ms': 'UI: JPEG decode total wait',
    'ui:jpeg_decode_bridge_ms': 'UI: JPEG decode bridge',
    'ui:main_dispatch_to_canvas_ms': 'UI: dispatch → canvas worker',
    'ui:canvas_worker_receive_lag_ms': 'UI: canvas worker receive lag',
    'ui:canvas_worker_raf_wait_ms': 'UI: canvas worker rAF wait',
    'ui:canvas_bitmap_transfer_ms': 'UI: bitmap transfer (worker)',
    'ui:render_ack_delivery_ms': 'UI: render ack delivery',
    'ui:raf_to_rendered_ms': 'UI: rAF tick → rendered',
};

function humanizeSourceKey(sourceKey: string): string {
    if (PRETTY_STAGE_LABELS[sourceKey]) {
        return PRETTY_STAGE_LABELS[sourceKey];
    }
    if (sourceKey.startsWith('aggregator:')) {
        const stage = sourceKey.slice('aggregator:'.length);
        return PRETTY_STAGE_LABELS[`aggregator:${stage}`] ?? stage;
    }
    if (sourceKey.startsWith('skeleton_inference:')) {
        const parts = sourceKey.split(':');
        if (parts.length >= 3) {
            const cam = parts[1];
            const stage = parts.slice(2).join(':');
            const label = PRETTY_STAGE_LABELS[`skeleton_inference:${stage}`] ?? stage;
            return `${cam} · ${label}`;
        }
        const stage = sourceKey.slice('skeleton_inference:'.length);
        return PRETTY_STAGE_LABELS[`skeleton_inference:${stage}`] ?? stage;
    }
    if (sourceKey.startsWith('camera:')) {
        const parts = sourceKey.split(':');
        const cam = parts[1];
        const stage = parts.slice(2).join(':');
        return `${cam} · ${PRETTY_STAGE_LABELS[`camera:${stage}`] ?? stage}`;
    }
    if (sourceKey.startsWith('ui:')) {
        const parts = sourceKey.split(':');
        const cam = parts[1];
        const stage = parts.slice(2).join(':');
        return `${cam} · ${PRETTY_STAGE_LABELS[`ui:${stage}`] ?? stage}`;
    }
    if (sourceKey.startsWith('multiframe:')) {
        const stage = sourceKey.slice('multiframe:'.length);
        return PRETTY_STAGE_LABELS[`multiframe:${stage}`] ?? stage;
    }
    return sourceKey.replace(/:/g, ' · ');
}

export function taskLabel(event: StoredPipelineTaskEvent, options?: {nested?: boolean}): string {
    const base = humanizeSourceKey(event.sourceKey);
    let text = event.frameNumber != null ? `F${event.frameNumber} · ${base}` : base;
    if (options?.nested) {
        text = text
            .replace(/^F\d+ · /, '')
            .replace(/Skeleton GPU: /g, '');
    }
    return text;
}

const UI_TIMING_STAGE_ORDER: string[] = [
    'raf_body_before_decode_ms',
    'jpeg_decode_worker_ms',
    'jpeg_decode_main_wait_ms',
    'jpeg_decode_bridge_ms',
    'main_dispatch_to_canvas_ms',
    'canvas_worker_receive_lag_ms',
    'canvas_worker_raf_wait_ms',
    'canvas_bitmap_transfer_ms',
    'render_ack_delivery_ms',
    'raf_to_rendered_ms',
    'jpeg_ack_to_receive_ms',
    'jpeg_ws_binary_interval_ms',
    'jpeg_ws_dispatch_lag_ms',
];

/** Pipeline order for skeleton-inference batch stages (matches backend RTMPose flow). */
const SKELETON_INFERENCE_STAGE_ORDER: string[] = [
    'frame_read',
    'predict_batch',
    'human_detection_preprocess',
    'human_detection_letterbox',
    'human_detection_batch_pack',
    'human_detection',
    'human_detection_postprocess',
    'pose_estimation_preprocess',
    'pose_estimation',
    'pose_estimation_postprocess',
];

const HUMAN_DETECTION_PREPROCESS_CHILD_STAGES = new Set([
    'human_detection_letterbox',
    'human_detection_batch_pack',
]);

/** Stages that run inside ``predict_batch`` (excluding the batch wrapper itself). */
const PREDICT_BATCH_CHILD_STAGES = new Set([
    'human_detection_preprocess',
    'human_detection_letterbox',
    'human_detection_batch_pack',
    'human_detection',
    'human_detection_postprocess',
    'pose_estimation_preprocess',
    'pose_estimation',
    'pose_estimation_postprocess',
]);

const CATEGORY_PRIORITY: Record<PipelineTaskCategory, number> = {
    capture: 0,
    ui_backend: 1,
    tracking: 2,
    aggregation: 3,
    ui_frontend: 4,
    other: 5,
};

function skeletonStageOrdinal(sourceKey: string, stage: string): number {
    if (!sourceKey.startsWith('skeleton_inference:') && stage !== 'frame_read') {
        return 10_000;
    }
    const i = SKELETON_INFERENCE_STAGE_ORDER.indexOf(stage);
    return i === -1 ? 5000 : i;
}

export function skeletonPreprocessChildIndent(
    event: Pick<StoredPipelineTaskEvent, 'nodeKind' | 'stage'>,
): number {
    return skeletonTimelineIndent(event);
}

export function skeletonTimelineIndent(
    event: Pick<StoredPipelineTaskEvent, 'nodeKind' | 'stage'>,
): number {
    if (event.nodeKind !== 'skeleton_inference') {
        return 0;
    }
    if (HUMAN_DETECTION_PREPROCESS_CHILD_STAGES.has(event.stage)) {
        return 2;
    }
    if (PREDICT_BATCH_CHILD_STAGES.has(event.stage)) {
        return 1;
    }
    return 0;
}

function alignPreprocessChildrenForFrame(
    events: StoredPipelineTaskEvent[],
    byTaskId: Map<string, StoredPipelineTaskEvent>,
    frameNumber: number,
): void {
    const preprocessId = batchSkeletonTaskId(frameNumber, 'human_detection_preprocess');
    const children = events.filter(
        event =>
            event.frameNumber === frameNumber
            && event.nodeKind === 'skeleton_inference'
            && HUMAN_DETECTION_PREPROCESS_CHILD_STAGES.has(event.stage),
    );
    if (children.length === 0) {
        return;
    }

    const minStart = Math.min(...children.map(child => child.startMs));
    const maxEnd = Math.max(...children.map(child => child.endMs));
    const preprocess = byTaskId.get(preprocessId);
    if (preprocess) {
        byTaskId.set(preprocessId, {
            ...preprocess,
            startMs: minStart,
            endMs: maxEnd,
            durationMs: maxEnd - minStart,
        });
    }

    for (const child of children) {
        const existing = byTaskId.get(child.taskId);
        if (!existing) {
            continue;
        }
        byTaskId.set(child.taskId, {
            ...existing,
            parentTaskIds: [preprocessId],
        });
    }
}

function alignPredictBatchChildrenForFrame(
    events: StoredPipelineTaskEvent[],
    byTaskId: Map<string, StoredPipelineTaskEvent>,
    frameNumber: number,
): void {
    const predictBatchId = batchSkeletonTaskId(frameNumber, 'predict_batch');
    const innerStages = events.filter(
        event =>
            event.frameNumber === frameNumber
            && event.nodeKind === 'skeleton_inference'
            && PREDICT_BATCH_CHILD_STAGES.has(event.stage),
    );
    if (innerStages.length === 0) {
        return;
    }

    const minStart = Math.min(...innerStages.map(stage => stage.startMs));
    const maxEnd = Math.max(...innerStages.map(stage => stage.endMs));
    const predictBatch = byTaskId.get(predictBatchId);
    if (predictBatch) {
        const startMs = Math.min(predictBatch.startMs, minStart);
        const endMs = Math.max(predictBatch.endMs, maxEnd);
        byTaskId.set(predictBatchId, {
            ...predictBatch,
            startMs,
            endMs,
            durationMs: endMs - startMs,
        });
    }

    for (const stage of innerStages) {
        const existing = byTaskId.get(stage.taskId);
        if (!existing) {
            continue;
        }
        if (HUMAN_DETECTION_PREPROCESS_CHILD_STAGES.has(stage.stage)) {
            continue;
        }
        byTaskId.set(stage.taskId, {
            ...existing,
            parentTaskIds: [predictBatchId],
        });
    }
}

/** Align skeleton GPU parent spans and parent-child links for the metrics timeline. */
export function normalizeSkeletonInferenceTiming(
    events: StoredPipelineTaskEvent[],
): StoredPipelineTaskEvent[] {
    if (events.length === 0) {
        return events;
    }

    const byTaskId = new Map(events.map(event => [event.taskId, {...event}]));
    const frameNumbers = new Set(
        events
            .filter(event => event.frameNumber != null && event.nodeKind === 'skeleton_inference')
            .map(event => event.frameNumber as number),
    );

    for (const frameNumber of frameNumbers) {
        alignPreprocessChildrenForFrame(events, byTaskId, frameNumber);
        alignPredictBatchChildrenForFrame(events, byTaskId, frameNumber);
    }

    return events.map(event => byTaskId.get(event.taskId) ?? event);
}

/** @deprecated Use {@link normalizeSkeletonInferenceTiming}. */
export function normalizeSkeletonPreprocessTiming(
    events: StoredPipelineTaskEvent[],
): StoredPipelineTaskEvent[] {
    return normalizeSkeletonInferenceTiming(events);
}

function batchSkeletonTaskId(frameNumber: number, stage: string): string {
    return buildDeterministicTaskId({
        frameNumber,
        nodeKind: 'skeleton_inference',
        stage,
        scope: 'batch',
    });
}

function uiStageOrdinal(sourceKey: string): number {
    if (!sourceKey.startsWith('ui:')) return 10_000;
    const stage = sourceKey.split(':').slice(2).join(':');
    const i = UI_TIMING_STAGE_ORDER.indexOf(stage);
    return i === -1 ? 5000 : i;
}

/** Place parents above children while preserving compareTimelineRows within each level. */
export function orderTasksParentsBeforeChildren(events: StoredPipelineTaskEvent[]): StoredPipelineTaskEvent[] {
    if (events.length <= 1) {
        return [...events];
    }

    const byId = new Map(events.map(event => [event.taskId, event]));
    const inDegree = new Map<string, number>();
    const childrenByParent = new Map<string, string[]>();

    for (const event of events) {
        inDegree.set(event.taskId, 0);
    }

    for (const event of events) {
        const parents = inferParentTaskIds(event).filter(parentId => byId.has(parentId));
        inDegree.set(event.taskId, parents.length);
        for (const parentId of parents) {
            const children = childrenByParent.get(parentId) ?? [];
            children.push(event.taskId);
            childrenByParent.set(parentId, children);
        }
    }

    const ready = events
        .filter(event => (inDegree.get(event.taskId) ?? 0) === 0)
        .sort(compareTimelineRows);
    const ordered: StoredPipelineTaskEvent[] = [];

    while (ready.length > 0) {
        const next = ready.shift()!;
        ordered.push(next);

        for (const childId of childrenByParent.get(next.taskId) ?? []) {
            const remaining = (inDegree.get(childId) ?? 0) - 1;
            inDegree.set(childId, remaining);
            if (remaining === 0) {
                const child = byId.get(childId);
                if (child) {
                    ready.push(child);
                    ready.sort(compareTimelineRows);
                }
            }
        }
    }

    if (ordered.length < events.length) {
        const seen = new Set(ordered.map(event => event.taskId));
        const remainder = events
            .filter(event => !seen.has(event.taskId))
            .sort(compareTimelineRows);
        ordered.push(...remainder);
    }

    return ordered;
}

export function compareTimelineRows(a: StoredPipelineTaskEvent, b: StoredPipelineTaskEvent): number {
    const frameA = a.frameNumber ?? -1;
    const frameB = b.frameNumber ?? -1;
    if (frameA !== frameB) return frameA - frameB;

    const catCmp = CATEGORY_PRIORITY[classifyTaskCategory(a)] - CATEGORY_PRIORITY[classifyTaskCategory(b)];
    if (catCmp !== 0) return catCmp;

    const skelCmp = skeletonStageOrdinal(a.sourceKey, a.stage) - skeletonStageOrdinal(b.sourceKey, b.stage);
    if (skelCmp !== 0) return skelCmp;

    const uiCmp = uiStageOrdinal(a.sourceKey) - uiStageOrdinal(b.sourceKey);
    if (uiCmp !== 0) return uiCmp;

    if (a.startMs !== b.startMs) return a.startMs - b.startMs;
    return a.taskId.localeCompare(b.taskId);
}

export const CATEGORY_COLORS: Record<PipelineTaskCategory, string> = {
    capture: '#4caf50',
    tracking: '#ff9800',
    aggregation: '#9c27b0',
    ui_backend: '#00bcd4',
    ui_frontend: '#1976d2',
    other: '#9e9e9e',
};

export function inferParentTaskIds(event: StoredPipelineTaskEvent): string[] {
    if (event.frameNumber == null) {
        return event.parentTaskIds.length > 0 ? event.parentTaskIds : [];
    }
    const frame = event.frameNumber;
    const predictBatchId = batchSkeletonTaskId(frame, 'predict_batch');
    const preprocessId = batchSkeletonTaskId(frame, 'human_detection_preprocess');
    const frameReadId = batchSkeletonTaskId(frame, 'frame_read');

    if (
        event.nodeKind === 'skeleton_inference'
        && HUMAN_DETECTION_PREPROCESS_CHILD_STAGES.has(event.stage)
    ) {
        return [preprocessId];
    }

    if (event.nodeKind === 'skeleton_inference') {
        if (event.stage === 'predict_batch') {
            return [frameReadId];
        }
        if (event.stage === 'human_detection_preprocess') {
            return [predictBatchId];
        }
        if (PREDICT_BATCH_CHILD_STAGES.has(event.stage)) {
            return [predictBatchId];
        }
        if (event.stage === 'frame_read') {
            return [];
        }
    }

    if (event.parentTaskIds.length > 0) {
        return event.parentTaskIds;
    }

    if (event.nodeKind === 'camera' && event.cameraId) {
        return [buildDeterministicTaskId({
            frameNumber: frame,
            nodeKind: 'skeleton_inference',
            stage: 'predict_batch',
            scope: 'batch',
        })];
    }
    if (event.nodeKind === 'ui' && event.cameraId) {
        return [buildDeterministicTaskId({
            frameNumber: frame,
            cameraId: event.cameraId,
            nodeKind: 'camera',
            stage: 'ws_payload_prepare_ms',
        })];
    }
    return [];
}
