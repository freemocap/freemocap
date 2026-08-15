import {z} from 'zod';
import {DetailedFramerate} from "@/services/server/server-helpers/framerate-store";
import {LogRecord} from "@/services/server/server-helpers/log-store";
import {TrackedObjectDefinition} from "@/services/server/server-helpers/tracked-object-definition";

// Type guard to check if a message is a log record
export function isLogRecord(data: any): data is LogRecord {
    return (
        data &&
        typeof data === 'object' &&
        data.message_type === 'log_record' &&
        typeof data.levelname === 'string' &&
        typeof data.message === 'string'
    );
}

// Type for framerate update message from backend
export interface FramerateUpdateMessage {
    message_type: 'framerate_update';
    camera_group_id: string;
    backend_framerate: DetailedFramerate;
    frontend_framerate: DetailedFramerate;
}

// Type guard to check if a message is a framerate update
export function isFramerateUpdate(data: any): data is FramerateUpdateMessage {
    return (
        data &&
        typeof data === 'object' &&
        data.message_type === 'framerate_update' &&
        typeof data.camera_group_id === 'string' &&
        data.backend_framerate &&
        typeof data.backend_framerate === 'object' &&
        data.frontend_framerate &&
        typeof data.frontend_framerate === 'object'
    );
}

/**
 * Tracker-schema handshake message — sent once on WS connect and again whenever
 * the pipeline's tracker configuration changes. `schemas` is keyed by tracker
 * id (e.g. `"rtmpose_wholebody"`); overlays reference a schema via the
 * `tracker_id` field in `SkeletonObservation`.
 */
export interface TrackerSchemasMessage {
    message_type: 'tracker_schemas';
    schemas: Record<string, TrackedObjectDefinition>;
}

export function isTrackerSchemas(data: any): data is TrackerSchemasMessage {
    return (
        data &&
        typeof data === 'object' &&
        data.message_type === 'tracker_schemas' &&
        data.schemas &&
        typeof data.schemas === 'object'
    );
}

export const PosthocProgressSchema = z.object({
    message_type: z.literal('posthoc_progress'),
    pipeline_id: z.string(),
    pipeline_type: z.string(),
    phase: z.string(),
    progress_fraction: z.number().min(0).max(1),
    detail: z.string().default(''),
    recording_name: z.string().default(''),
    recording_path: z.string().default(''),
});

export type PosthocProgressMessage = z.infer<typeof PosthocProgressSchema>;

export function isPosthocProgress(data: unknown): data is PosthocProgressMessage {
    const result = PosthocProgressSchema.safeParse(data);
    if (!result.success && typeof data === 'object' && data !== null && (data as Record<string, unknown>).message_type === 'posthoc_progress') {
        console.error('[WS] posthoc_progress message failed schema validation:', result.error.format(), data);
    }
    return result.success;
}
