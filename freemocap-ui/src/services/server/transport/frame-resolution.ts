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
import {
    OverlayLayer,
    type DerivedPointsFrame,
    type OverlayFrame,
    type PointsFrame,
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

/** Strip a 4-column (x,y,z,reprojection_error) block to 3-interleaved xyz. */
function xyzFromFourColumns(data: Float32Array, rowCount: number): Float32Array {
    const out = new Float32Array(rowCount * 3);
    for (let i = 0; i < rowCount; i++) {
        out[i * 3] = data[i * 4];
        out[i * 3 + 1] = data[i * 4 + 1];
        out[i * 3 + 2] = data[i * 4 + 2];
    }
    return out;
}

export interface ResolvedFrameChannels {
    /** One per tracked model, in the frame's own order. */
    models: ResolvedModelFrame[];
    /** Every detector's 3D keypoints, merged. Detector name spaces do not collide. */
    keypoints: PointsFrame | null;
    overlays: OverlayFrame[];
}

/** Every tracker's KEYPOINTS_3D in one frame.
 *
 *  Merged rather than "the first one" because a session runs several detectors — a pose
 *  detector and a charuco detector — and taking the first silently dropped the other's
 *  points. Their names are disjoint, so concatenating is lossless. */
function mergeTrackerKeypoints(frame: FrameMessage): PointsFrame | null {
    const names: string[] = [];
    const blocks: { block: ChannelBlock; count: number }[] = [];
    for (const tracker of frame.trackers) {
        const kp = channelByKind(tracker.channels, KEYPOINTS_3D);
        if (!kp || !kp.names) continue;
        names.push(...kp.names);
        blocks.push({ block: kp, count: kp.names.length });
    }
    if (names.length === 0) return null;
    const data = new Float32Array(names.length * 3);
    let offset = 0;
    for (const entry of blocks) {
        data.set(xyzFromFourColumns(float32(entry.block.data), entry.count), offset * 3);
        offset += entry.count;
    }
    return { names, data };
}

/** One instance's channels, named against ITS model. */
function resolveModelFrame(
    model: ModelDefinition,
    channels: ChannelBlock[],
    fittedScaleMm: number | null,
): ResolvedModelFrame {
    const segmentNames: readonly string[] = model.segments.map((s) => s.name);
    const landmarkNames: readonly string[] = model.landmarks.map((l) => l.name);

    const so = channelByKind(channels, SEGMENT_ORIGINS);
    const segmentOrigins: PointsFrame | null = so
        ? { names: segmentNames, data: float32(so.data) }
        : null;

    // LANDMARKS_3D is the model's landmarks placed by the FIT rather than by triangulation
    // noise — which is what draws a charuco board as a reconstructed rigid object rather
    // than as a cloud of measured corners.
    const lm = channelByKind(channels, LANDMARKS_3D);
    const landmarks: PointsFrame | null = lm
        ? {
              names: landmarkNames,
              data: xyzFromFourColumns(float32(lm.data), landmarkNames.length),
          }
        : null;

    const rw = channelByKind(channels, ROTATIONS_WORLD);
    const rl = channelByKind(channels, ROTATIONS_LOCAL);
    const rotations: RotationsFrame | null =
        rw || rl
            ? {
                  boneNames: segmentNames,
                  worldQuaternions: rw ? float32(rw.data) : new Float32Array(0),
                  localQuaternions: rl ? float32(rl.data) : new Float32Array(0),
              }
            : null;

    let centerOfMass: [number, number, number] | null = null;
    let xcom: [number, number, number] | null = null;
    const dp = channelByKind(channels, DERIVED_POINTS);
    if (dp && dp.names) {
        const derivedNames = dp.names;
        const raw = float32(dp.data);
        const rowOf = (name: string): [number, number, number] | null => {
            const idx = derivedNames.indexOf(name);
            if (idx === -1) return null;
            const x = raw[idx * 3];
            if (Number.isNaN(x)) return null;
            return [raw[idx * 3], raw[idx * 3 + 1], raw[idx * 3 + 2]];
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
        fittedScaleMm,
        segmentOrigins,
        landmarks,
        rotations,
        segmentLengths,
        derived,
    };
}

export function resolveFrameChannels(frame: FrameMessage): ResolvedFrameChannels {
    const modelById = new Map(frame.models.map((m) => [m.model_id, m]));

    const models: ResolvedModelFrame[] = [];
    for (const instance of frame.instances) {
        const model = modelById.get(instance.model_id);
        // An instance naming a model the frame does not carry cannot be drawn — the frame
        // is meant to be self-contained, so this is a backend bug rather than something to
        // paper over with a guessed model.
        if (!model) continue;
        models.push(
            resolveModelFrame(model, instance.channels, instance.fitted_scale_mm ?? null),
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
                    data: float32(c.data),
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
        const segmentNames = model.segments.map((s) => s.name);
        for (const c of instance.channels) {
            if (c.kind === OVERLAY_REPROJECTIONS && c.camera_id) {
                overlays.push({
                    cameraId: c.camera_id,
                    layer: OverlayLayer.REPROJECTIONS,
                    modelId: model.model_id,
                    frameNumber: frame.frame_number,
                    names: segmentNames,
                    data: float32(c.data),
                    imageSize: c.image_size,
                });
            }
        }
    }

    return { models, keypoints: mergeTrackerKeypoints(frame), overlays };
}
