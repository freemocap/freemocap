import {
    CharucoObservation,
    CharucoOverlayDataMessage,
    CharucoOverlayDataMessageSchema,
} from "@/services/server/server-helpers/image-overlay/charuco-types";
import {
    MediapipeObservation,
    MediapipeOverlayDataMessage,
    MediapipeOverlayDataMessageSchema,
} from "@/services/server/server-helpers/image-overlay/mediapipe-types";
import {ModelInfo} from "@/services/server/server-helpers/image-overlay/image-overlay-system";
import {OverlayRendererFactory} from "@/services/server/server-helpers/image-overlay/overlay-renderer-factory";
import {DetailedFramerate} from "@/services/server/server-helpers/framerate-store";
import {LogRecord} from "@/services/server/server-helpers/log-store";
import {Point3d, RigidBodyPose} from "@/components/viewport3d";

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

export interface FrontendPayloadMessage {
    message_type: 'frontend_payload';
    frame_number: number;
    charuco_overlays: Record<string, CharucoObservation>
    skeleton_overlays: Record<string, MediapipeObservation>
    keypoints_raw: Record<string, Point3d>
    keypoints_filtered: Record<string, Point3d>
    rigid_body_poses: Record<string, RigidBodyPose>;
}

export function isFrontendPayload(data: any): data is FrontendPayloadMessage {
    return (
        data &&
        typeof data === 'object' &&
        data.message_type === 'frontend_payload' &&
        data.frame_number && typeof data.frame_number === 'number'
    );
}

export interface PosthocProgressMessage {
    message_type: 'posthoc_progress';
    pipeline_id: string;
    phase: string;
    progress_fraction: number;
    detail: string;
}

export function isPosthocProgress(data: unknown): data is PosthocProgressMessage {
    return (
        typeof data === 'object' &&
        data !== null &&
        (data as PosthocProgressMessage).message_type === 'posthoc_progress'
    );
}
