import { z } from "zod";

// Schema for CurrentFrameRate
const CurrentFrameRateSchema = z.object({
    mean_frame_duration_ms: z.number(),
    mean_frames_per_second: z.number(),
    recent_frames_per_second: z.number(),
    recent_mean_frame_duration_ms: z.number(),
});

// Schema for CameraConfig, assuming you have a similar structure in TypeScript
const CameraConfigSchema = z.object({
    // Assuming CameraId and CameraName are strings for simplicity
    camera_id: z.number(),
    camera_name: z.string(),
    use_this_camera: z.boolean(),
    resolution: z.object({
        width: z.number(),
        height: z.number(),
    }),
    color_channels: z.number(),
    pixel_format: z.string(),
    exposure_mode: z.string(),
    exposure: z.union([z.number(), z.string()]),
    framerate: z.number(),
    rotation: z.string(),
    capture_fourcc: z.string(),
    writer_fourcc: z.string(),
});

// Schema for CameraConfigs, a dictionary of CameraConfig
const CameraConfigsSchema = z.record(z.string(), CameraConfigSchema);

// Schema for CameraDeviceInfo
const CameraDeviceInfoSchema = z.object({
    description: z.string(),
    device_address: z.string(),
    cv2_port: z.number(),
    available_video_formats: z.array(
        z.object({
            width: z.number(),
            height: z.number(),
            pixel_format: z.string(),
            framerate: z.number(),
        })
    ),
});

// Schema for AvailableCameras, a dictionary of CameraDeviceInfo
const AvailableCamerasSchema = z.record(z.string(), CameraDeviceInfoSchema);

// Zod schema for SkellycamAppStateDTO
export const SkellyCamAppStateSchema = z.object({
    type: z.literal("SkellycamAppStateDTO"),
    state_timestamp: z.string().optional(), // Assuming a string timestamp
    camera_configs: CameraConfigsSchema.optional(), // Optional CameraConfigs
    available_devices: AvailableCamerasSchema.optional(), // Optional AvailableCameras
    current_framerate: CurrentFrameRateSchema.nullable().optional(), // Allow null or undefined
    record_frames_flag_status: z.boolean(),
});
