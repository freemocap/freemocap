import {load as parseYaml} from 'js-yaml';
import {z} from 'zod';

import layoutPresetsYaml from './layout-presets.yaml?raw';

export const PATH_TEMPLATE_FIELDS = [
    'videosSynchronizedDir',
    'videosAnnotatedDir',
    'outputDir',
    'logsDir',
    'calibrationTomlPath',
    'recordingInfoPath',
    'dataParquetPath',
    'blendPath',
] as const;

export type PathTemplateField = (typeof PATH_TEMPLATE_FIELDS)[number];

const PathTemplatesSchema = z.object({
    videosSynchronizedDir: z.string(),
    videosAnnotatedDir:    z.string(),
    outputDir:             z.string(),
    logsDir:               z.string(),
    calibrationTomlPath:   z.string(),
    recordingInfoPath:     z.string(),
    dataParquetPath:       z.string(),
    blendPath:             z.string(),
});

export type PathTemplates = z.infer<typeof PathTemplatesSchema>;

export const LayoutPresetsFileSchema = z.object({
    canonical: PathTemplatesSchema,
    legacy_v1: PathTemplatesSchema,
});

export type RecordingLayoutPresetName = keyof z.infer<typeof LayoutPresetsFileSchema>;

const parsed = parseYaml(layoutPresetsYaml);
export const LAYOUT_PRESETS = LayoutPresetsFileSchema.parse(parsed);

export const RECORDING_LAYOUT_PRESET_NAMES: readonly RecordingLayoutPresetName[] =
    Object.keys(LAYOUT_PRESETS) as RecordingLayoutPresetName[];

const TOKEN_RE = /\{([a-zA-Z_][a-zA-Z0-9_]*)\}/g;

export const renderPathTemplate = (
    template: string,
    context: {fullPath: string; recordingName: string},
): string => {
    return template.replace(TOKEN_RE, (_, token: string) => {
        if (token === 'fullPath') return context.fullPath;
        if (token === 'recordingName') return context.recordingName;
        throw new Error(
            `Unknown token "{${token}}" in layout-preset path template: ${template}`,
        );
    });
};
