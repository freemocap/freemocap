import {z} from 'zod';

import {
    LAYOUT_PRESETS,
    PATH_TEMPLATE_FIELDS,
    type PathTemplates,
    type RecordingLayoutPresetName,
    renderPathTemplate,
} from './layout-presets/layout-presets';

/**
 * Canonical folder layout for a freemocap recording.
 *
 * A recording is a single self-contained folder. Calibration / mocap are
 * *recording types* (tagged in `recording_info.json`), not separate folders.
 *
 *   {base_dir}/{recording_name}/
 *   ├── videos/
 *   │   ├── synchronized/                     (camera-sync raw videos)
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
 *
 * Path resolution is preset-driven: see ./layout-presets/layout-presets.yaml for
 * the canonical + legacy preset definitions.
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
    layoutPreset: RecordingLayoutPresetName;
    videosSynchronizedDir: string;
    videosAnnotatedDir: string;
    outputDir: string;
    logsDir: string;
    calibrationTomlPath: string;
    recordingInfoPath: string;
    dataParquetPath: string;
    blendPath: string;
}

export const joinPath = (...parts: string[]): string => {
    return parts
        .map((part, idx) => idx === 0 ? part.replace(/[\\/]+$/, '') : part.replace(/^[\\/]+|[\\/]+$/g, ''))
        .filter(part => part.length > 0)
        .join('/');
};

export type RecordingLayoutOverrides = Partial<PathTemplates>;

export interface BuildRecordingStructureOptions {
    preset?: RecordingLayoutPresetName;
    overrides?: RecordingLayoutOverrides;
}

export const buildRecordingStructure = (
    identity: RecordingIdentity,
    options: BuildRecordingStructureOptions = {},
): RecordingStructure => {
    const {baseDirectory, recordingName} = identity;
    const preset = options.preset ?? 'canonical';
    const overrides = options.overrides ?? {};
    const presetTemplates = LAYOUT_PRESETS[preset];
    const fullPath = joinPath(baseDirectory, recordingName);
    const ctx = {fullPath, recordingName};

    const resolved = PATH_TEMPLATE_FIELDS.reduce((acc, field) => {
        const template = overrides[field] ?? presetTemplates[field];
        acc[field] = joinPath(renderPathTemplate(template, ctx));
        return acc;
    }, {} as Record<(typeof PATH_TEMPLATE_FIELDS)[number], string>);

    return {
        baseDirectory,
        recordingName,
        fullPath,
        layoutPreset: preset,
        ...resolved,
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

export const synthesizeRecordingInfoStub = (recordingName: string): RecordingInfoJson => ({
    recording_name: recordingName,
    recording_types: [],
});

/**
 * Mirrors the backend `RecordingLayoutValidation` Pydantic model. Field names
 * are snake_case to match the JSON wire format emitted by FastAPI.
 */
export const FilePresenceSchema = z.object({
    path: z.string(),
    exists: z.boolean(),
    size_bytes: z.number().nullable().optional(),
});

export type FilePresence = z.infer<typeof FilePresenceSchema>;

export const RecordingLayoutValidationSchema = z.object({
    full_path: z.string(),
    is_legacy_layout: z.boolean().default(false),
    videos_synchronized: FilePresenceSchema,
    videos_annotated: FilePresenceSchema,
    output_dir: FilePresenceSchema,
    calibration_toml: FilePresenceSchema,
    recording_info: FilePresenceSchema,
    data_parquet: FilePresenceSchema,
    blend: FilePresenceSchema,
    synchronized_videos_dir: FilePresenceSchema,
    annotated_videos_dir: FilePresenceSchema,
    output_data_dir: FilePresenceSchema,
    camera_calibration_toml: FilePresenceSchema,
    legacy_parquet_in_output_data: FilePresenceSchema,
});

export type RecordingLayoutValidation = z.infer<typeof RecordingLayoutValidationSchema>;

export const LEGACY_MARKER_FIELDS = [
    'synchronized_videos_dir',
    'annotated_videos_dir',
    'output_data_dir',
    'camera_calibration_toml',
    'legacy_parquet_in_output_data',
] as const satisfies readonly (keyof RecordingLayoutValidation)[];

export const detectLayoutPreset = (
    validation: RecordingLayoutValidation,
): RecordingLayoutPresetName => {
    const legacy = LEGACY_MARKER_FIELDS.some(
        (field) => (validation[field] as FilePresence).exists,
    );
    const canonical =
        validation.videos_synchronized.exists ||
        validation.data_parquet.exists ||
        validation.calibration_toml.exists;
    // half-migrated folders prefer canonical
    return legacy && !canonical ? 'legacy_v1' : 'canonical';
};

export const listDetectedLegacyMarkers = (
    validation: RecordingLayoutValidation,
): readonly (typeof LEGACY_MARKER_FIELDS)[number][] =>
    LEGACY_MARKER_FIELDS.filter((field) => (validation[field] as FilePresence).exists);
