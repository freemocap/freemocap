/** Rolling UI policy: show this many frame numbers in the network timeline. */
export const PIPELINE_TIMELINE_FRAME_WINDOW = 3;

export const FALLBACK_FRAME_DURATION_MS = 1000 / 30;

export type PipelineClockDomain = 'backend_perf' | 'renderer_perf' | 'ingest_wall';

export type PipelineTaskCategory =
    | 'capture'
    | 'tracking'
    | 'aggregation'
    | 'ui_backend'
    | 'ui_frontend'
    | 'other';

/** Backend WebSocket task-event shape (forward-compatible). */
export interface PipelineTimingEventPayload {
    task_id: string;
    parent_task_ids?: string[];
    stage: string;
    node_kind: string;
    camera_id?: string | null;
    frame_number?: number | null;
    start_time_ns?: number | null;
    end_time_ns?: number | null;
    duration_ms: number;
    batch_index?: number | null;
    batch_size?: number | null;
}

export interface StoredPipelineTaskEvent {
    taskId: string;
    parentTaskIds: string[];
    stage: string;
    nodeKind: string;
    cameraId: string | null;
    frameNumber: number | null;
    startMs: number;
    endMs: number;
    durationMs: number;
    clockDomain: PipelineClockDomain;
    sourceKey: string;
    lastSeenMs: number;
}

export interface UiTimingRecordContext {
    frameNumber?: number | null;
    parentTaskIds?: string[];
    stage?: string;
}
