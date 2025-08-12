import {z} from 'zod';

// Define string literals as const for better type safety
export const PixelFormats = ['RGB', 'BGR', 'GRAY'];
export const ExposureModes = ['MANUAL', 'AUTO', 'RECOMMEND'];
export const CameraStatus = ['CONNECTED', 'AVAILABLE', 'UNAVAILABLE', 'IN_USE', 'ERROR'];
export const RotationOptions = [-1, 0, 1, 2]; // NO_ROTATION, cv2.CLOCKWISE_90, cv2.ROTATE_180, cv2.COUNTERCLOCKWISE_90
export const RotationLabels = ['None', '90°', '180°', '270°']; // Human-readable labels
export const FourccOptions = ['MJPG', 'X264', 'YUYV', 'H264'];
export const ResolutionPresets = [
    {width: 640, height: 480, label: "VGA (4:3)"},
    {width: 1280, height: 720, label: "HD 720p (16:9)"},
    {width: 1920, height: 1080, label: "Full HD 1080p(16:9)"}
];
export const CAMERA_DEFAULT_CONSTRAINTS = {
    resolution: {
        min: {width: 640, height: 480},
        max: {width: 1920, height: 1080},
        default: {width: 1280, height: 720},
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
};

export interface CameraDevice {
    index: number;
    deviceId: string;
    cameraId: string;
    status: string;
    groupId: string;
    kind: string;
    label: string;
    selected: boolean;
    constraints: typeof CAMERA_DEFAULT_CONSTRAINTS;
    config: CameraConfig;
}


// Helper function
export const createDefaultCameraConfig = (index: number, label: string, id: string): CameraConfig => ({
    camera_index: index,
    camera_name: label || `Camera ${index}`,
    camera_id: id,
    use_this_camera: true,
    resolution: CAMERA_DEFAULT_CONSTRAINTS.resolution.default,
    color_channels: 3,
    pixel_format: PixelFormats[0],
    exposure_mode: ExposureModes[0], // 'MANUAL'
    exposure: CAMERA_DEFAULT_CONSTRAINTS.exposure.default,
    framerate: CAMERA_DEFAULT_CONSTRAINTS.framerate.default,
    rotation: RotationOptions[0], // '-1' for NO_ROTATION
    capture_fourcc: FourccOptions[0], // 'MJPG'
    writer_fourcc: FourccOptions[1], // 'X264'
});

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
    exposure_mode: z.string(),
    exposure: z.number(),
    framerate: z.number(),
    rotation: z.number(),
    capture_fourcc: z.string(),
    writer_fourcc: z.string(),
});

export const CameraConfigsSchema = z.record(z.string(), CameraConfigSchema);

export type CameraConfig = z.infer<typeof CameraConfigSchema>;
export type CameraConfigs = z.infer<typeof CameraConfigsSchema>;
export type ExposureMode = typeof ExposureModes[number];

