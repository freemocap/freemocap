import {
    CharucoOverlayDataMessage,
    CharucoOverlayDataMessageSchema,
} from "@/services/server/server-helpers/image-overlay/charuco-types";
import {
    MediapipeOverlayDataMessage,
    MediapipeOverlayDataMessageSchema,
} from "@/services/server/server-helpers/image-overlay/mediapipe-types";
import {ModelInfo} from "@/services/server/server-helpers/image-overlay/image-overlay-system";
import {OverlayRendererFactory} from "@/services/server/server-helpers/image-overlay/overlay-renderer-factory";

export interface FramerateUpdateMessage {
    message_type: 'framerate_update';
    camera_group_id: string;
    backend_framerate: {
        mean: number;
        std: number;
        min: number;
        max: number;
        median: number;
        recent: number[];
    };
    frontend_framerate: {
        mean: number;
        std: number;
        min: number;
        max: number;
        median: number;
        recent: number[];
    };
}

export interface LogRecord {
    message_type: 'log_record';
    levelname: string;
    message: string;
    timestamp: string;
}

export interface SettingsStateMessage {
    message_type: 'settings/state';
    settings: Record<string, unknown>;
    version: number;
}

export function arraysEqual(a: string[], b: string[]): boolean {
    if (a.length !== b.length) return false;
    const sortedA = [...a].sort();
    const sortedB = [...b].sort();
    return sortedA.every((val, idx) => val === sortedB[idx]);
}

export function isLogRecord(data: unknown): data is LogRecord {
    return (
        typeof data === 'object' &&
        data !== null &&
        (data as Record<string, unknown>).message_type === 'log_record' &&
        typeof (data as Record<string, unknown>).levelname === 'string' &&
        typeof (data as Record<string, unknown>).message === 'string'
    );
}

export function isSettingsStateMessage(data: unknown): data is SettingsStateMessage {
    return (
        typeof data === 'object' &&
        data !== null &&
        (data as Record<string, unknown>).message_type === 'settings/state' &&
        typeof (data as Record<string, unknown>).settings === 'object' &&
        (data as Record<string, unknown>).settings !== null &&
        typeof (data as Record<string, unknown>).version === 'number'
    );
}

export function isFramerateUpdate(data: unknown): data is FramerateUpdateMessage {
    const d = data as Record<string, unknown>;
    return (
        typeof data === 'object' &&
        data !== null &&
        d.message_type === 'framerate_update' &&
        typeof d.camera_group_id === 'string' &&
        typeof d.backend_framerate === 'object' &&
        d.backend_framerate !== null &&
        typeof d.frontend_framerate === 'object' &&
        d.frontend_framerate !== null
    );
}

export function isCharucoOverlayDataMessage(data: unknown): data is CharucoOverlayDataMessage {
    const result = CharucoOverlayDataMessageSchema.safeParse(data);
    return result.success;
}

export function isMediapipeOverlayDataMessage(data: unknown): data is MediapipeOverlayDataMessage {
    const result = MediapipeOverlayDataMessageSchema.safeParse(data);
    return result.success;
}

export function handleModelInfoUpdate(modelInfo: ModelInfo): void {
    console.log(`Received model info for tracker: ${modelInfo.tracker_name}`);
    OverlayRendererFactory.setModelInfo(modelInfo.tracker_name, modelInfo);
}