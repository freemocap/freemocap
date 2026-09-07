import type {PlaybackSource} from './playback-protocol';
import type {ModelDefinition} from '@/services/server/transport/message-contract';
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

export interface RecordingChannel {
    sensor_group: string; source: string; reference_frame: string | null;
    kind: string; names: string[]; components: Record<string, string>;
}
export interface RecordingTimeline {
    sensor_group: string; source: string; frame_numbers: number[]; timestamps_s: number[];
}
export interface PlaybackMedia {video_source: PlaybackSource; video_filename: string; nominal_fps: number; timeline: RecordingTimeline}
export interface RecordingStaticChannel { channel: RecordingChannel; values: Record<string, Record<string, number>> }
export interface PlaybackRun {
    run_id: number; models: ModelDefinition[]; channels: RecordingChannel[];
    static_channels: RecordingStaticChannel[]; timelines: RecordingTimeline[]; media: PlaybackMedia[];
}
export interface PlaybackManifest {recording_id: string; revision: string; selected_run_id: number; runs: PlaybackRun[]}
export interface PlaybackChannelData {channel: RecordingChannel; frame_numbers: number[]; timestamps_s: number[]; values: (number | null)[]}
export interface PlaybackWindow {revision: string; run_id: number; start_s: number; end_s: number; channels: PlaybackChannelData[]}

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

export function recordedModelFrame(run: PlaybackRun, window: PlaybackWindow, model: ModelDefinition, group: string, time: number): ResolvedModelFrame {
    const find = (kind: RecordingChannelKind): PlaybackChannelData | undefined => {
        const matches = window.channels.filter(item => item.channel.source === model.model_id &&
            item.channel.sensor_group === group && item.channel.kind === kind);
        if (matches.length > 1) throw new Error(`Ambiguous recording reference frame for ${kind}`);
        return matches[0];
    };
    const points = (kind: RecordingChannelKind): PointsFrame | null => {
        const item = find(kind);
        if (!item) return null;
        const data = orderedChannelFrame(item, time, {names: item.channel.names, components: POSITION_COMPONENTS});
        return data ? {names: item.channel.names, data} : null;
    };
    const staticChannel = (kind: RecordingChannelKind): RecordingStaticChannel | undefined => run.static_channels.find(item =>
        item.channel.source === model.model_id && item.channel.sensor_group === group && item.channel.kind === kind);
    const scalarValues = (item: RecordingStaticChannel): Float32Array => Float32Array.from(item.channel.names.map(name =>
        item.values[name][Object.keys(item.channel.components)[0]]));
    const scale = staticChannel(RecordingChannelKind.Scale);
    const lengths = staticChannel(RecordingChannelKind.Lengths);
    const world = find(RecordingChannelKind.WorldRotations), local = find(RecordingChannelKind.LocalRotations);
    const worldData = world ? orderedChannelFrame(world, time,
        {names: world.channel.names, components: ROTATION_COMPONENTS}) : null;
    const localData = local && world ? orderedChannelFrame(local, time,
        {names: world.channel.names, components: ROTATION_COMPONENTS}) : null;
    const derived = points(RecordingChannelKind.Derived);
    const comIndex = derived?.names.indexOf('center_of_mass') ?? -1;
    const com = derived && comIndex >= 0 ? Array.from(derived.data.slice(comIndex * 3, comIndex * 3 + 3)) : null;
    const fittedScaleMm = scale ? scalarValues(scale)[0] : null;
    return {
        modelId: model.model_id, fittedScaleMm,
        landmarks: points(RecordingChannelKind.Landmarks), segmentOrigins: points(RecordingChannelKind.Origins),
        rotations: world && worldData ? {boneNames: world.channel.names, worldQuaternions: worldData,
            localQuaternions: localData ?? new Float32Array(worldData.length).fill(NaN)} : null,
        segmentLengths: lengths ? {names: lengths.channel.names, data: scalarValues(lengths), fittedScaleMm} : null,
        derived: {centerOfMass: com?.every(Number.isFinite) ? [com[0], com[1], com[2]] : null, xcom: null},
    };
}
