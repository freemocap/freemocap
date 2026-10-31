// transport/frame-resolution.ts
//
// Resolve one decoded FrameMessage into the typed frames the subscribers consume.
//
// A frame carries SEVERAL models — a tracked person and a tracked charuco board are two —
// so this resolves one `ResolvedModelFrame` per instance rather than flattening everything
// into a single set of channels. Flattening was only ever correct because there happened to
// be one model: it silently labelled every instance's rows with `models[0]`'s segment names.
//
// Channel routing is by kind: KEYPOINTS_3D / OVERLAY_2D live on the trackers (one per
// detector); everything else lives on the instances. Segment/landmark channels are
// index-keyed against their OWN model, so their names come from that model.

import type { ChannelBlock, FrameMessage, ModelDefinition } from "./message-contract";
import {snapshotEqual} from './snapshot-equality';
import {
    OverlayLayer,
    type DerivedPointsFrame,
    type OverlayFrame,
    type PointsFrame,
    type PointSourcesFrame,
    type ResolvedModelFrame,
    type RotationsFrame,
    type SegmentLengthsFrame,
} from "./frame-types";

const KEYPOINTS_3D = "KEYPOINTS_3D";
const LANDMARKS_3D = "LANDMARKS_3D";
const SEGMENT_ORIGINS = "SEGMENT_ORIGINS";
const ROTATIONS_LOCAL = "ROTATIONS_LOCAL";
const ROTATIONS_WORLD = "ROTATIONS_WORLD";
const DERIVED_POINTS = "DERIVED_POINTS";
const OVERLAY_2D = "OVERLAY_2D";
const BOXES_2D = "BOXES_2D";
const SEGMENT_LENGTHS = "SEGMENT_LENGTHS";
const OVERLAY_REPROJECTIONS = "OVERLAY_REPROJECTIONS";

function channelByKind(channels: ChannelBlock[], kind: string): ChannelBlock | undefined {
    return channels.find((c) => c.kind === kind);
}

/** View a packed float32 little-endian byte string as a Float32Array. The
 *  codec hands us an owned Uint8Array (byteOffset 0), so alignment is safe. */
function float32(data: Uint8Array): Float32Array {
    return new Float32Array(data.buffer, data.byteOffset, data.byteLength / 4);
}

function overlayValues(channel: ChannelBlock, names: readonly string[]): Float32Array {
    const required = channel.kind === BOXES_2D
        ? ['x1', 'y1', 'x2', 'y2', 'confidence', 'detector_ran'] : ['x', 'y', 'visibility'];
    if (new Set(channel.columns).size !== channel.columns.length || required.some(name => !channel.columns.includes(name)) ||
        channel.data.byteLength !== names.length * channel.columns.length * Float32Array.BYTES_PER_ELEMENT) {
        throw new Error('Camera overlay bytes do not match declared components and identities');
    }
    return float32(channel.data);
}

/** Retain owned scientific values and select XYZ using declared component names. */
function pointView(channel: ChannelBlock, names: readonly string[]): PointsFrame {
    const stride = channel.columns.length;
    if (new Set(channel.columns).size !== stride || channel.data.byteLength !== names.length * stride * Float32Array.BYTES_PER_ELEMENT)
        throw new Error('Point channel bytes do not match unique declared components and identities');
    const coordinateOffsets = ['x', 'y', 'z'].map(component => channel.columns.indexOf(component)) as [number, number, number];
    if (coordinateOffsets.some(index => index < 0)) throw new Error('3D point channel requires declared XYZ components');
    if (channel.sample_status && channel.sample_status.length !== names.length)
        throw new Error('Temporal status must have one value per entity');
    return {names, data: float32(channel.data), stride, coordinateOffsets,
        sampleStatus: channel.sample_status, statusLabels: channel.status_labels};
}

const QUATERNION_COMPONENTS = ['w', 'x', 'y', 'z'] as const;
function quaternionValues(channel: ChannelBlock, names: readonly string[]): Float32Array {
    const width = QUATERNION_COMPONENTS.length;
    const offsets = QUATERNION_COMPONENTS.map(component => channel.columns.indexOf(component));
    if (channel.columns.length !== width || new Set(channel.columns).size !== width || offsets.some(index => index < 0) ||
        channel.data.byteLength !== names.length * width * Float32Array.BYTES_PER_ELEMENT)
        throw new Error('Quaternion channel bytes do not match declared WXYZ components and identities');
    const source = float32(channel.data);
    if (offsets.every((offset, index) => offset === index)) return source;
    const ordered = new Float32Array(source.length);
    for (let row = 0; row < names.length; row++) {
        const start = row * width;
        ordered[start] = source[start + offsets[0]];
        ordered[start + 1] = source[start + offsets[1]];
        ordered[start + 2] = source[start + offsets[2]];
        ordered[start + 3] = source[start + offsets[3]];
    }
    return ordered;
}

const modelLayouts = new WeakMap<ModelDefinition, {segments: readonly string[]; landmarks: readonly string[]}>();
function modelLayout(model: ModelDefinition) {
    let layout = modelLayouts.get(model);
    if (!layout) {
        layout = {segments: model.segments.map(segment => segment.name), landmarks: model.landmarks.map(landmark => landmark.name)};
        modelLayouts.set(model, layout);
    }
    return layout;
}

export interface ResolvedFrameChannels {
    /** One per tracked model, in the frame's own order. */
    models: ResolvedModelFrame[];
    /** Every detector's 3D keypoints, merged. Detector name spaces do not collide. */
    keypoints: PointSourcesFrame | null;
    overlays: OverlayFrame[];
}

/** Every tracker's KEYPOINTS_3D in one frame.
 *
 *  Merged rather than "the first one" because a session runs several detectors — a pose
 *  detector and a charuco detector — and taking the first silently dropped the other's
 *  points. Their names are disjoint, so concatenating is lossless. */
function mergeTrackerKeypoints(frame: FrameMessage, previous: PointSourcesFrame | null): PointSourcesFrame | null {
    const sources: PointsFrame[] = [];
    for (const tracker of frame.trackers) {
        const channel = channelByKind(tracker.channels, KEYPOINTS_3D);
        if (channel?.names) sources.push(pointView(channel, channel.names));
    }
    if (!sources.some(source => source.names.length)) return null;
    const sameLayout = previous && sources.length === previous.sources.length &&
        sources.every((source, index) => snapshotEqual(source.names, previous.sources[index].names));
    const names = sameLayout ? previous.names : sources.flatMap(source => [...source.names]);
    return {names, sources};
}

/** One instance's channels, named against ITS model. */
function resolveModelFrame(
    model: ModelDefinition,
    channels: ChannelBlock[],
    fittedScaleMm: number | null,
    instanceId: number,
): ResolvedModelFrame {
    const {segments: segmentNames, landmarks: landmarkNames} = modelLayout(model);

    const so = channelByKind(channels, SEGMENT_ORIGINS);
    const segmentOrigins: PointsFrame | null = so
        ? pointView(so, segmentNames)
        : null;

    // LANDMARKS_3D is the model's landmarks placed by the FIT rather than by triangulation
    // noise — which is what draws a charuco board as a reconstructed rigid object rather
    // than as a cloud of measured corners.
    const lm = channelByKind(channels, LANDMARKS_3D);
    const landmarks: PointsFrame | null = lm
        ? pointView(lm, landmarkNames)
        : null;

    const mapped = channelByKind(channels, "MAPPED_KEYPOINTS_3D");
    const mappedKeypoints: PointsFrame | null = mapped
        ? pointView(mapped, landmarkNames)
        : null;

    const rw = channelByKind(channels, ROTATIONS_WORLD);
    const rl = channelByKind(channels, ROTATIONS_LOCAL);
    const rotations: RotationsFrame | null =
        rw || rl
            ? {
                  boneNames: segmentNames,
                  worldQuaternions: rw ? quaternionValues(rw, segmentNames) : new Float32Array(0),
                  localQuaternions: rl ? quaternionValues(rl, segmentNames) : new Float32Array(0),
              }
            : null;

    let centerOfMass: [number, number, number] | null = null;
    let xcom: [number, number, number] | null = null;
    const dp = channelByKind(channels, DERIVED_POINTS);
    if (dp && dp.names) {
        const derivedNames = dp.names;
        const points = pointView(dp, derivedNames);
        const raw = points.data, stride = points.stride!, offsets = points.coordinateOffsets!;
        const rowOf = (name: string): [number, number, number] | null => {
            const idx = derivedNames.indexOf(name);
            if (idx === -1) return null;
            const x = raw[idx * stride + offsets[0]];
            if (Number.isNaN(x)) return null;
            return [x, raw[idx * stride + offsets[1]], raw[idx * stride + offsets[2]]];
        };
        centerOfMass = rowOf("center_of_mass");
        xcom = rowOf("xcom");
    }
    const derived: DerivedPointsFrame = { centerOfMass, xcom };

    // The fitted scale rides WITH the lengths: both come from the same fit, so travelling
    // together is what stops them disagreeing about which frame they came from.
    const sl = channelByKind(channels, SEGMENT_LENGTHS);
    const segmentLengths: SegmentLengthsFrame | null = sl
        ? { names: segmentNames, data: float32(sl.data), fittedScaleMm }
        : null;

    return {
        modelId: model.model_id,
        instanceId,
        fittedScaleMm,
        segmentOrigins,
        landmarks,
        mappedKeypoints,
        rotations,
        segmentLengths,
        derived,
    };
}

export function resolveFrameChannels(frame: FrameMessage): ResolvedFrameChannels {
    return new FrameResolver().resolve(frame);
}

/** Reuse only immutable-by-contract published values, never overwrite a retained frame. */
export class FrameResolver {
    private definitions: readonly ModelDefinition[] | null = null;
    private modelById = new Map<string, ModelDefinition>();
    private previous: FrameMessage | null = null;
    private latest: ResolvedFrameChannels | null = null;
    reset(): void {
        this.definitions = null;
        this.modelById.clear();
        this.previous = null;
        this.latest = null;
    }
    resolve(frame: FrameMessage): ResolvedFrameChannels {
        const definitionsChanged = this.definitions !== frame.models;
        if (definitionsChanged) {
            this.definitions = frame.models;
            this.modelById = new Map(frame.models.map(model => [model.model_id, model]));
        }
        const modelById = this.modelById;
        const sameChannels = (left: ChannelBlock[], right: ChannelBlock[]) => left.length === right.length && left.every((channel, index) => {
            const other = right[index];
            return channel.data === other.data && channel.kind === other.kind && channel.camera_id === other.camera_id
                && snapshotEqual(channel.names, other.names) && snapshotEqual(channel.columns, other.columns) && snapshotEqual(channel.image_size, other.image_size);
        });
        const reuseModels = !definitionsChanged && this.previous && this.latest && frame.instances.length === this.previous.instances.length
            && frame.instances.every((instance, index) => {
                const old = this.previous!.instances[index];
                return instance.model_id === old.model_id && instance.instance_id === old.instance_id && Object.is(instance.fitted_scale_mm, old.fitted_scale_mm)
                    && sameChannels(instance.channels, old.channels);
            });

        const models: ResolvedModelFrame[] = [];
        for (const instance of reuseModels ? [] : frame.instances) {
            const model = modelById.get(instance.model_id);
            // An instance naming a model the frame does not carry cannot be drawn — the frame
            // is meant to be self-contained, so this is a backend bug rather than something to
            // paper over with a guessed model.
            if (!model) continue;
            models.push(
                resolveModelFrame(model, instance.channels, instance.fitted_scale_mm ?? null, instance.instance_id),
            );
        }

        const overlays: OverlayFrame[] = [];
        for (const tracker of frame.trackers) {
            for (const c of tracker.channels) {
                if (c.kind === OVERLAY_2D && c.camera_id && c.names) {
                    overlays.push({
                        cameraId: c.camera_id,
                        layer: OverlayLayer.DETECTIONS,
                        frameNumber: frame.frame_number,
                        names: c.names,
                        columns: c.columns,
                        data: overlayValues(c, c.names),
                        imageSize: c.image_size,
                    });
                }
                // The detector's crop for this camera. Named by detection stage, so a
                // tracker running several stages reports one row each.
                if (c.kind === BOXES_2D && c.camera_id && c.names) {
                    overlays.push({
                        cameraId: c.camera_id,
                        layer: OverlayLayer.BOXES,
                        frameNumber: frame.frame_number,
                        names: c.names,
                        columns: c.columns,
                        data: overlayValues(c, c.names),
                        imageSize: c.image_size,
                    });
                }
            }
        }
        for (const instance of frame.instances) {
            const model = modelById.get(instance.model_id);
            if (!model) continue;
            // Named against THIS instance's model: reprojections are segment-origin rows, and
            // labelling them from another model's segment list is how a board's overlay would
            // come out wearing a human's names.
            const segmentNames = modelLayout(model).segments;
            for (const c of instance.channels) {
                if (c.kind === OVERLAY_REPROJECTIONS && c.camera_id) {
                    overlays.push({
                        cameraId: c.camera_id,
                        layer: OverlayLayer.REPROJECTIONS,
                        modelId: model.model_id,
                        frameNumber: frame.frame_number,
                        names: segmentNames,
                        columns: c.columns,
                        data: overlayValues(c, segmentNames),
                        imageSize: c.image_size,
                    });
                }
            }
        }

        const reusePoints = this.previous && this.latest && frame.trackers.length === this.previous.trackers.length
            && frame.trackers.every((tracker, index) => {
                const old = this.previous!.trackers[index];
                const current = channelByKind(tracker.channels, KEYPOINTS_3D), prior = channelByKind(old.channels, KEYPOINTS_3D);
                return tracker.tracker_id === old.tracker_id && (current && prior ? sameChannels([current], [prior]) : current === prior);
            });
        const result = {models: reuseModels ? this.latest!.models : models, keypoints: reusePoints ? this.latest!.keypoints : mergeTrackerKeypoints(frame, this.latest?.keypoints ?? null), overlays};
        this.previous = frame; this.latest = result;
        return result;
    }
}
