import { z } from 'zod';

// Constants
export const PixelFormats = ['RGB', 'BGR', 'GRAY'] as const;
export const ExposureModes = ['MANUAL', 'AUTO', 'RECOMMEND'] as const;
export const CameraStatus = ['CONNECTED', 'AVAILABLE', 'UNAVAILABLE', 'IN_USE', 'ERROR'] as const;
export const RotationOptions = [-1, 0, 1, 2] as const;
export const RotationLabels = ['None', '90°', '180°', '270°'] as const;
export const FourccOptions = ['MJPG', 'X264', 'YUYV', 'H264'] as const;

// Type definitions derived from constants
export type PixelFormat = typeof PixelFormats[number];
export type ExposureMode = typeof ExposureModes[number];
export type CameraStatusType = typeof CameraStatus[number];
export type RotationOption = typeof RotationOptions[number];
export type FourccOption = typeof FourccOptions[number];

export const ResolutionPresets = [
    { width: 640, height: 480, label: "VGA (4:3)" },
    { width: 1280, height: 720, label: "HD 720p (16:9)" },
    { width: 1920, height: 1080, label: "Full HD 1080p(16:9)" }
] as const;

export const CAMERA_DEFAULT_CONSTRAINTS = {
    resolution: {
        min: { width: 640, height: 480 },
        max: { width: 1920, height: 1080 },
        default: { width: 1280, height: 720 },
        presets: ResolutionPresets
    },
    exposure: {
        min: -12,
        max: -4,
        default: -7,
        step: 1
    },
    framerate: {
        min: 1,
        max: 60,
        default: 30,
        available: [15, 30, 60]
    },
    pixel_formats: PixelFormats,
    exposure_modes: ExposureModes,
    status_options: CameraStatus,
    rotation_options: RotationOptions,
    fourcc_options: FourccOptions
} as const;

export const CameraConfigSchema = z.object({
    camera_index: z.number(),
    camera_id: z.string(),
    camera_name: z.string(),
    use_this_camera: z.boolean(),
    resolution: z.object({
        width: z.number().int(),
        height: z.number().int()
    }),
    color_channels: z.number(),
    pixel_format: z.string(),
    exposure_mode: z.enum(ExposureModes),
    exposure: z.number(),
    framerate: z.number(),
    rotation: z.number(),
    capture_fourcc: z.string(),
    writer_fourcc: z.string(),
});

export type CameraConfig = z.infer<typeof CameraConfigSchema>;

export interface CameraDevice {
    index: number;
    deviceId: string;
    cameraId: string;
    status: CameraStatusType;
    groupId: string;
    kind: string;
    label: string;
    selected: boolean;
    constraints: typeof CAMERA_DEFAULT_CONSTRAINTS;
    config: CameraConfig;
}

export const createDefaultCameraConfig = (
    index: number,
    label: string,
    id: string
): CameraConfig => ({
    camera_index: index,
    camera_name: label || `Camera ${index}`,
    camera_id: id,
    use_this_camera: true,
    resolution: CAMERA_DEFAULT_CONSTRAINTS.resolution.default,
    color_channels: 3,
    pixel_format: PixelFormats[0],
    exposure_mode: ExposureModes[0],
    exposure: CAMERA_DEFAULT_CONSTRAINTS.exposure.default,
    framerate: CAMERA_DEFAULT_CONSTRAINTS.framerate.default,
    rotation: RotationOptions[0],
    capture_fourcc: FourccOptions[0],
    writer_fourcc: FourccOptions[1],
});
