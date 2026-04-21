import {z} from 'zod';

/**
 * Canonical folder layout for a freemocap recording.
 *
 * A recording is a single self-contained folder. Calibration / mocap are
 * *recording types* (tagged in `recording_info.json`), not separate folders.
 *
 *   {base_dir}/{recording_name}/
 *   ├── videos/
 *   │   ├── raw/                              (camera-sync raw videos)
 *   │   └── annotated/                        (videos with keypoint overlays)
 *   ├── output/                               (split mocap artifacts)
 *   ├── logs/
 *   ├── {recording_name}_calibration.toml     (may be copied from another recording)
 *   ├── {recording_name}_recording_info.json  (camera configs, type tags, metadata)
 *   ├── {recording_name}_data.parquet         (primary mocap data store)
 *   └── {recording_name}.blend                (optional Blender export)
 *
 * Matches the backend `RecordingStructure` Pydantic model (source of truth spec
 * lives alongside that file). Any change here should be mirrored server-side.
 */

export const RecordingIdentitySchema = z.object({
    baseDirectory: z.string(),
    recordingName: z.string(),
});

export type RecordingIdentity = z.infer<typeof RecordingIdentitySchema>;

export interface RecordingStructure {
    baseDirectory: string;
    recordingName: string;
    fullPath: string;
    videosRawDir: string;
    videosAnnotatedDir: string;
    outputDir: string;
    logsDir: string;
    calibrationTomlPath: string;
    recordingInfoPath: string;
    dataParquetPath: string;
    blendPath: string;
}

const joinPath = (...parts: string[]): string => {
    return parts
        .map((part, idx) => idx === 0 ? part.replace(/[\\/]+$/, '') : part.replace(/^[\\/]+|[\\/]+$/g, ''))
        .filter(part => part.length > 0)
        .join('/');
};

export const buildRecordingStructure = (identity: RecordingIdentity): RecordingStructure => {
    const {baseDirectory, recordingName} = identity;
    const fullPath = joinPath(baseDirectory, recordingName);
    return {
        baseDirectory,
        recordingName,
        fullPath,
        videosRawDir: joinPath(fullPath, 'videos', 'raw'),
        videosAnnotatedDir: joinPath(fullPath, 'videos', 'annotated'),
        outputDir: joinPath(fullPath, 'output'),
        logsDir: joinPath(fullPath, 'logs'),
        calibrationTomlPath: joinPath(fullPath, `${recordingName}_calibration.toml`),
        recordingInfoPath: joinPath(fullPath, `${recordingName}_recording_info.json`),
        dataParquetPath: joinPath(fullPath, `${recordingName}_data.parquet`),
        blendPath: joinPath(fullPath, `${recordingName}.blend`),
    };
};

export const RecordingTypeTagSchema = z.enum(['calibration', 'mocap']);
export type RecordingTypeTag = z.infer<typeof RecordingTypeTagSchema>;

export const RecordingInfoJsonSchema = z.object({
    recording_name: z.string(),
    recording_types: z.array(RecordingTypeTagSchema).default([]),
    created_at: z.string().nullable().optional(),
    camera_configs: z.record(z.string(), z.unknown()).optional(),
    notes: z.string().nullable().optional(),
}).passthrough();

export type RecordingInfoJson = z.infer<typeof RecordingInfoJsonSchema>;

export const RecordingLayoutValidationSchema = z.object({
    hasVideosRaw: z.boolean(),
    hasVideosAnnotated: z.boolean(),
    hasOutput: z.boolean(),
    hasCalibrationToml: z.boolean(),
    hasRecordingInfo: z.boolean(),
    hasDataParquet: z.boolean(),
    hasBlend: z.boolean(),
    isLegacyLayout: z.boolean().default(false),
    videoCount: z.number().default(0),
    frameCount: z.number().nullable().default(null),
});

export type RecordingLayoutValidation = z.infer<typeof RecordingLayoutValidationSchema>;
