import {z} from 'zod';
import {PlaybackSource} from './playback-source';
import {CalibrationUpdateRequestSchema} from '@/store/slices/calibration/calibration-types';
import {ModelDefinitionSchema, type ModelDefinition} from '@/services/server/transport/message-contract';
import type {ResolvedModelFrame, PointsFrame} from '@/services/server/transport/frame-types';

export enum RecordingChannelKind {
    RawPoints = 'RAW_KEYPOINTS_3D', Landmarks = 'LANDMARKS_3D', Origins = 'SEGMENT_ORIGINS',
    WorldRotations = 'ROTATIONS_WORLD', LocalRotations = 'ROTATIONS_LOCAL',
    Derived = 'DERIVED_POINTS', Lengths = 'SEGMENT_LENGTHS', Scale = 'MODEL_SCALE',
}

export enum RecordingComponent {W = 'w', X = 'x', Y = 'y', Z = 'z'}
const POSITION_COMPONENTS = [RecordingComponent.X, RecordingComponent.Y, RecordingComponent.Z];
const ROTATION_COMPONENTS = [RecordingComponent.W, ...POSITION_COMPONENTS];

export interface ChannelLayout {names: readonly string[]; components: readonly RecordingComponent[]}

export const RecordingChannelSchema = z.object({
    sensor_group: z.string(), source: z.string(), reference_frame: z.string().nullable(),
    kind: z.string(), names: z.array(z.string()), components: z.record(z.string(), z.string()),
});
export type RecordingChannel = z.infer<typeof RecordingChannelSchema>;
export const RecordingTimelineSchema = z.object({
    sensor_group: z.string(), source: z.string(),
    frame_numbers: z.array(z.number().int().nonnegative()), timestamps_s: z.array(z.number()),
});
export type RecordingTimeline = z.infer<typeof RecordingTimelineSchema>;
export const PlaybackMediaSchema = z.object({
    video_source: z.enum(PlaybackSource), video_filename: z.string(),
    nominal_fps: z.number().positive(), timeline: RecordingTimelineSchema,
});
export type PlaybackMedia = z.infer<typeof PlaybackMediaSchema>;
export const RecordingStaticChannelSchema = z.object({
    channel: RecordingChannelSchema, values: z.record(z.string(), z.record(z.string(), z.number())),
});
export type RecordingStaticChannel = z.infer<typeof RecordingStaticChannelSchema>;
export const PlaybackRunSchema = z.object({
    model_sources: z.record(z.string(), z.string()),
    calibration_updates: z.record(z.string(), CalibrationUpdateRequestSchema).optional(),
    run_id: z.number().int().nonnegative(), models: z.array(ModelDefinitionSchema),
    channels: z.array(RecordingChannelSchema), static_channels: z.array(RecordingStaticChannelSchema),
    timelines: z.array(RecordingTimelineSchema), media: z.array(PlaybackMediaSchema),
});
export type PlaybackRun = z.infer<typeof PlaybackRunSchema>;
export const PlaybackManifestSchema = z.object({
    recording_id: z.string(), revision: z.string().min(1), selected_run_id: z.number().int().nonnegative(),
    runs: z.array(PlaybackRunSchema),
});
export type PlaybackManifest = z.infer<typeof PlaybackManifestSchema>;
export const PlaybackChannelDataSchema = z.object({
    channel: RecordingChannelSchema, frame_numbers: z.array(z.number().int().nonnegative()),
    timestamps_s: z.array(z.number()),
    values: z.instanceof(Float64Array),
});
export type PlaybackChannelData = z.infer<typeof PlaybackChannelDataSchema>;
export interface PlaybackSamples {channels: PlaybackChannelData[]}

export function sampleAtTime(timestamps: readonly number[], time: number): number {
    let left = 0, right = timestamps.length;
    while (left < right) {
        const mid = (left + right) >>> 1;
        if (timestamps[mid] <= time) left = mid + 1; else right = mid;
    }
    return left - 1;
}

export function channelFrame(data: PlaybackChannelData, time: number): Float32Array | null {
    if (data.timestamps_s.length !== data.frame_numbers.length) throw new Error('Invalid recording timestamp array length');
    const index = sampleAtTime(data.timestamps_s, time);
    if (index < 0) return null;
    const stride = data.channel.names.length * Object.keys(data.channel.components).length;
    if (data.values.length !== data.frame_numbers.length * stride) throw new Error('Invalid recording channel array length');
    return Float32Array.from(data.values.slice(index * stride, (index + 1) * stride), value => value ?? NaN);
}

export function orderedChannelFrame(data: PlaybackChannelData, time: number, layout: ChannelLayout): Float32Array | null {
    const components = Object.keys(data.channel.components);
    const componentIndices = layout.components.map(component => components.indexOf(component));
    const nameIndices = layout.names.map(name => data.channel.names.indexOf(name));
    if (components.length !== layout.components.length || componentIndices.includes(-1) ||
        data.channel.names.length !== layout.names.length || nameIndices.includes(-1)) {
        throw new Error('Recording channel does not match the requested renderer layout');
    }
    const frame = channelFrame(data, time);
    if (!frame) return null;
    return Float32Array.from(nameIndices.flatMap(name => componentIndices.map(component =>
        frame[name * components.length + component])));
}

export function recordedModelFrame(run: PlaybackRun, samples: PlaybackSamples, model: ModelDefinition, group: string, time: number): ResolvedModelFrame {
    const find = (kind: RecordingChannelKind): PlaybackChannelData | undefined => {
        const matches = samples.channels.filter(item => run.model_sources[item.channel.source] === model.model_id &&
            item.channel.sensor_group === group && item.channel.kind === kind);
        if (matches.length > 1) throw new Error(`Ambiguous recording reference frame for ${kind}`);
        return matches[0];
    };
    const segmentNames = model.segments.map(segment => segment.name);
    const landmarkNames = model.landmarks.map(landmark => landmark.name);
    const points = (kind: RecordingChannelKind): PointsFrame | null => {
        const item = find(kind);
        if (!item) return null;
        const names = kind === RecordingChannelKind.Origins ? segmentNames
            : kind === RecordingChannelKind.Landmarks ? landmarkNames : item.channel.names;
        const data = orderedChannelFrame(item, time, {names, components: POSITION_COMPONENTS});
        return data ? {names, data} : null;
    };
    const staticChannel = (kind: RecordingChannelKind): RecordingStaticChannel | undefined => run.static_channels.find(item =>
        run.model_sources[item.channel.source] === model.model_id && item.channel.sensor_group === group && item.channel.kind === kind);
    const scalarValues = (item: RecordingStaticChannel): Float32Array => Float32Array.from(item.channel.names.map(name =>
        item.values[name][Object.keys(item.channel.components)[0]]));
    const scale = staticChannel(RecordingChannelKind.Scale);
    const lengths = staticChannel(RecordingChannelKind.Lengths);
    const world = find(RecordingChannelKind.WorldRotations), local = find(RecordingChannelKind.LocalRotations);
    const worldData = world ? orderedChannelFrame(world, time,
        {names: segmentNames, components: ROTATION_COMPONENTS}) : null;
    const localData = local && world ? orderedChannelFrame(local, time,
        {names: segmentNames, components: ROTATION_COMPONENTS}) : null;
    const derived = points(RecordingChannelKind.Derived);
    const comIndex = derived?.names.indexOf('center_of_mass') ?? -1;
    const com = derived && comIndex >= 0 ? Array.from(derived.data.slice(comIndex * 3, comIndex * 3 + 3)) : null;
    const fittedScaleMm = scale ? scalarValues(scale)[0] : null;
    return {
        modelId: model.model_id, instanceId: 0, fittedScaleMm,
        landmarks: points(RecordingChannelKind.Landmarks), segmentOrigins: points(RecordingChannelKind.Origins),
        rotations: world && worldData ? {boneNames: segmentNames, worldQuaternions: worldData,
            localQuaternions: localData ?? new Float32Array(worldData.length).fill(NaN)} : null,
        segmentLengths: lengths ? {names: segmentNames,
            data: Float32Array.from(segmentNames.map(name => {
                const value = lengths.values[name]?.[Object.keys(lengths.channel.components)[0]];
                if (value === undefined) throw new Error('Missing declared segment length');
                return value;
            })), fittedScaleMm} : null,
        derived: {centerOfMass: com?.every(Number.isFinite) ? [com[0], com[1], com[2]] : null, xcom: null},
    };
}
