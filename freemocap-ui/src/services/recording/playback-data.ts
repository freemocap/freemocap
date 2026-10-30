import {z} from 'zod';
import {PlaybackSource} from './playback-source';
import {CalibrationUpdateRequestSchema, CalibrationCameraDataSchema} from '@/store/slices/calibration/calibration-types';
import {ModelDefinitionSchema, type ModelDefinition} from '@/services/server/transport/message-contract';
import type {ResolvedModelFrame, PointsFrame} from '@/services/server/transport/frame-types';

export enum RecordingChannelKind {
    MappedKeypoints = 'MAPPED_KEYPOINTS_3D',
    RawPoints = 'RAW_KEYPOINTS_3D', Landmarks = 'LANDMARKS_3D', Origins = 'SEGMENT_ORIGINS',
    WorldRotations = 'ROTATIONS_WORLD', LocalRotations = 'ROTATIONS_LOCAL',
    Derived = 'DERIVED_POINTS', Lengths = 'SEGMENT_LENGTHS', Scale = 'MODEL_SCALE',
}

export enum RecordingComponent {W = 'w', X = 'x', Y = 'y', Z = 'z'}
const POSITION_COMPONENTS = [RecordingComponent.X, RecordingComponent.Y, RecordingComponent.Z];
const ROTATION_COMPONENTS = [RecordingComponent.W, ...POSITION_COMPONENTS];

export interface ChannelLayout {names: readonly string[]; components: readonly string[]}

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
    camera_geometry: z.record(z.string(), z.array(CalibrationCameraDataSchema)).optional(),
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

/** Display projections borrow stable views; the Float64 recording remains untouched. */
export interface PreparedChannelFrame {
    names: readonly string[];
    components: readonly string[];
    read: (time: number) => Float32Array | null;
}
const preparedChannels = new WeakMap<PlaybackChannelData, PreparedChannelFrame[]>();
const sameNames = (left: readonly string[], right: readonly string[]): boolean =>
    left === right || left.length === right.length && left.every((name, index) => name === right[index]);

export function prepareChannelFrame(data: PlaybackChannelData, layout?: ChannelLayout): PreparedChannelFrame {
    const sourceComponents = Object.keys(data.channel.components);
    const names = layout?.names ?? data.channel.names;
    const components = layout?.components ?? sourceComponents;
    const cached = preparedChannels.get(data)?.find(item => sameNames(item.names, names) && sameNames(item.components, components));
    if (cached) return cached;
    if (data.timestamps_s.length !== data.frame_numbers.length) throw new Error('Invalid recording timestamp array length');
    const stride = data.channel.names.length * sourceComponents.length;
    if (data.values.length !== data.frame_numbers.length * stride) throw new Error('Invalid recording channel array length');
    const componentIndices = components.map(component => sourceComponents.indexOf(component));
    const nameIndices = names.map(name => data.channel.names.indexOf(name));
    if (sourceComponents.length !== components.length || componentIndices.includes(-1) ||
        data.channel.names.length !== names.length || nameIndices.includes(-1) ||
        new Set(names).size !== names.length || new Set(components).size !== components.length) {
        throw new Error('Recording channel does not match the requested renderer layout');
    }
    const offsets = Uint32Array.from(nameIndices.flatMap(name => componentIndices.map(component => name * sourceComponents.length + component)));
    const ordered = offsets.every((offset, index) => offset === index);
    const values = ordered ? new Float32Array(data.values) : new Float32Array(data.values.length);
    if (!ordered) {
        for (let base = 0; base < values.length; base += stride) {
            for (let column = 0; column < stride; column++) values[base + column] = data.values[base + offsets[column]];
        }
    }
    let previousIndex = -1;
    let previousView: Float32Array | null = null;
    const prepared: PreparedChannelFrame = {names, components, read: time => {
        const index = sampleAtTime(data.timestamps_s, time);
        if (index < 0) return null;
        if (index !== previousIndex) {previousIndex = index; previousView = values.subarray(index * stride, (index + 1) * stride);}
        return previousView;
    }};
    const variants = preparedChannels.get(data);
    if (variants) variants.push(prepared); else preparedChannels.set(data, [prepared]);
    return prepared;
}

export function channelFrame(data: PlaybackChannelData, time: number): Float32Array | null {
    return prepareChannelFrame(data).read(time);
}

export function orderedChannelFrame(data: PlaybackChannelData, time: number, layout: ChannelLayout): Float32Array | null {
    return prepareChannelFrame(data, layout).read(time);
}

function preparePoints(item: PlaybackChannelData | undefined, names?: readonly string[]): (time: number) => PointsFrame | null {
    if (!item) return () => null;
    const prepared = prepareChannelFrame(item, {names: names ?? item.channel.names, components: POSITION_COMPONENTS});
    let previous: PointsFrame | null = null;
    return time => {
        const data = prepared.read(time);
        if (!data) return null;
        if (previous?.data !== data) previous = {names: prepared.names, data};
        return previous;
    };
}

const preparedKeypoints = new WeakMap<PlaybackChannelData[], Map<string, (time: number) => PointsFrame | null>>();
/** A merged multi-source result is borrowed until the next read; individual channel views are stable. */
export function prepareRecordedKeypoints(channels: PlaybackChannelData[], group: string): (time: number) => PointsFrame | null {
    let groups = preparedKeypoints.get(channels);
    if (!groups) {groups = new Map(); preparedKeypoints.set(channels, groups);}
    const cached = groups.get(group);
    if (cached) return cached;
    const readers = channels.filter(item => item.channel.sensor_group === group && item.channel.kind === RecordingChannelKind.RawPoints)
        .map(item => preparePoints(item));
    let active: Array<PointsFrame | null> = [];
    let merged: PointsFrame | null = null;
    const read = readers.length === 1 ? readers[0] : (time: number): PointsFrame | null => {
        const frames = readers.map(reader => reader(time));
        const layoutChanged = frames.length !== active.length || frames.some((frame, index) => frame?.names !== active[index]?.names);
        if (layoutChanged) {
            const names = frames.flatMap(frame => frame?.names ?? []);
            merged = names.length ? {names, data: new Float32Array(names.length * POSITION_COMPONENTS.length)} : null;
        }
        if (merged) {
            let offset = 0;
            for (let index = 0; index < frames.length; index++) {
                const frame = frames[index];
                if (!frame) continue;
                if (layoutChanged || frame !== active[index]) merged.data.set(frame.data, offset);
                offset += frame.data.length;
            }
        }
        active = frames;
        return merged;
    };
    groups.set(group, read);
    return read;
}

/** Every original tracker stream in the selected sensor group, in declared XYZ order. */
export function recordedKeypoints(channels: PlaybackChannelData[], group: string, time: number): PointsFrame | null {
    return prepareRecordedKeypoints(channels, group)(time);
}

const preparedModels = new WeakMap<PlaybackChannelData[], WeakMap<PlaybackRun, WeakMap<ModelDefinition, Map<string, (time: number) => ResolvedModelFrame>>>>();
export function prepareRecordedModelFrame(run: PlaybackRun, samples: PlaybackSamples, model: ModelDefinition, group: string): (time: number) => ResolvedModelFrame {
    let runs = preparedModels.get(samples.channels);
    if (!runs) {runs = new WeakMap(); preparedModels.set(samples.channels, runs);}
    let models = runs.get(run);
    if (!models) {models = new WeakMap(); runs.set(run, models);}
    let groups = models.get(model);
    if (!groups) {groups = new Map(); models.set(model, groups);}
    const cached = groups.get(group);
    if (cached) return cached;
    const byKind = new Map<RecordingChannelKind, PlaybackChannelData>();
    for (const item of samples.channels) {
        if (run.model_sources[item.channel.source] !== model.model_id || item.channel.sensor_group !== group) continue;
        const kind = item.channel.kind as RecordingChannelKind;
        if (byKind.has(kind)) throw new Error(`Ambiguous recording reference frame for ${kind}`);
        byKind.set(kind, item);
    }
    const segmentNames = model.segments.map(segment => segment.name);
    const landmarkNames = model.landmarks.map(landmark => landmark.name);
    const mapped = preparePoints(byKind.get(RecordingChannelKind.MappedKeypoints), landmarkNames);
    const landmarks = preparePoints(byKind.get(RecordingChannelKind.Landmarks), landmarkNames);
    const origins = preparePoints(byKind.get(RecordingChannelKind.Origins), segmentNames);
    const derived = preparePoints(byKind.get(RecordingChannelKind.Derived));
    const centerIndex = byKind.get(RecordingChannelKind.Derived)?.channel.names.indexOf('center_of_mass') ?? -1;
    let previousDerived: Float32Array | null = null;
    let previousCenter: [number, number, number] | null = null;
    const staticChannel = (kind: RecordingChannelKind): RecordingStaticChannel | undefined => run.static_channels.find(item =>
        run.model_sources[item.channel.source] === model.model_id && item.channel.sensor_group === group && item.channel.kind === kind);
    const scale = staticChannel(RecordingChannelKind.Scale);
    const lengths = staticChannel(RecordingChannelKind.Lengths);
    const fittedScaleMm = scale ? Math.fround(scale.values[scale.channel.names[0]][Object.keys(scale.channel.components)[0]]) : null;
    const segmentLengths = lengths ? {names: segmentNames, data: Float32Array.from(segmentNames.map(name => {
        const value = lengths.values[name]?.[Object.keys(lengths.channel.components)[0]];
        if (value === undefined) throw new Error('Missing declared segment length');
        return value;
    })), fittedScaleMm} : null;
    const world = byKind.get(RecordingChannelKind.WorldRotations), local = byKind.get(RecordingChannelKind.LocalRotations);
    const worldReader = world ? prepareChannelFrame(world, {names: segmentNames, components: ROTATION_COMPONENTS}) : null;
    const localReader = local && world ? prepareChannelFrame(local, {names: segmentNames, components: ROTATION_COMPONENTS}) : null;
    const unavailableLocal = new Float32Array(segmentNames.length * ROTATION_COMPONENTS.length).fill(NaN);
    let previous: ResolvedModelFrame | null = null;
    const read = (time: number): ResolvedModelFrame => {
        const mappedKeypoints = mapped(time), landmarkPoints = landmarks(time), segmentOrigins = origins(time);
        const worldData = worldReader?.read(time) ?? null;
        const localData = worldData ? localReader?.read(time) ?? unavailableLocal : null;
        const derivedPoints = derived(time);
        let centerOfMass: [number, number, number] | null = null;
        if (derivedPoints && centerIndex >= 0) {
            const values = derivedPoints.data;
            if (values !== previousDerived) {
                const offset = centerIndex * POSITION_COMPONENTS.length;
                const x = values[offset], y = values[offset + 1], z = values[offset + 2];
                previousCenter = Number.isFinite(x) && Number.isFinite(y) && Number.isFinite(z) ? [x, y, z] : null;
                previousDerived = values;
            }
            centerOfMass = previousCenter;
        }
        if (previous && previous.mappedKeypoints === mappedKeypoints && previous.landmarks === landmarkPoints &&
            previous.segmentOrigins === segmentOrigins && (previous.rotations?.worldQuaternions ?? null) === worldData &&
            (previous.rotations?.localQuaternions ?? null) === localData && previous.derived.centerOfMass === centerOfMass) return previous;
        previous = {modelId: model.model_id, instanceId: 0, fittedScaleMm, mappedKeypoints, landmarks: landmarkPoints, segmentOrigins,
            rotations: worldData ? {boneNames: segmentNames, worldQuaternions: worldData, localQuaternions: localData!} : null,
            segmentLengths, derived: {centerOfMass, xcom: null}};
        return previous;
    };
    groups.set(group, read);
    return read;
}

export function recordedModelFrame(run: PlaybackRun, samples: PlaybackSamples, model: ModelDefinition, group: string, time: number): ResolvedModelFrame {
    return prepareRecordedModelFrame(run, samples, model, group)(time);
}
