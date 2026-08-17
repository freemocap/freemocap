// transport/frame-resolution.ts
//
// Resolve one decoded FrameMessage into the typed frames the subscribers
// consume. Channel routing is by kind (KEYPOINTS_3D / OVERLAY_2D live on the
// trackers; everything else lives on the instances). Segment/landmark channels
// are index-keyed against the frame's own model (row order == model segment
// order), so their names are resolved from the model that rides the frame.

import type { ChannelBlock, FrameMessage, ModelDefinition } from "./message-contract";
import {
    OverlayLayer,
    type DerivedPointsFrame,
    type OverlayFrame,
    type PointsFrame,
    type RotationsFrame,
    type SegmentLengthsFrame,
} from "./frame-types";

const KEYPOINTS_3D = "KEYPOINTS_3D";
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
    keypoints: PointsFrame | null;
    segmentOrigins: PointsFrame | null;
    rotations: RotationsFrame | null;
    derived: DerivedPointsFrame;
    segmentLengths: SegmentLengthsFrame | null;
    overlays: OverlayFrame[];
}

export function resolveFrameChannels(frame: FrameMessage): ResolvedFrameChannels {
    const model: ModelDefinition | undefined = frame.models[0];
    const segmentNames: readonly string[] = model ? model.segments.map((s) => s.name) : [];
    const instanceChannels = frame.instances.flatMap((i) => i.channels);
    const trackerChannels = frame.trackers.flatMap((t) => t.channels);

    // keypoints — tracker KEYPOINTS_3D (inline names, 4-col xyz + reprojection_error)
    let keypoints: PointsFrame | null = null;
    const kp = channelByKind(trackerChannels, KEYPOINTS_3D);
    if (kp && kp.names) {
        keypoints = { names: kp.names, data: xyzFromFourColumns(float32(kp.data), kp.names.length) };
    }

    // segment origins — instances SEGMENT_ORIGINS (index-keyed, 3-col xyz)
    let segmentOrigins: PointsFrame | null = null;
    const so = channelByKind(instanceChannels, SEGMENT_ORIGINS);
    if (so) {
        segmentOrigins = { names: segmentNames, data: float32(so.data) };
    }

    // rotations — instances ROTATIONS_WORLD / ROTATIONS_LOCAL (index-keyed, 4-col wxyz)
    let rotations: RotationsFrame | null = null;
    const rw = channelByKind(instanceChannels, ROTATIONS_WORLD);
    const rl = channelByKind(instanceChannels, ROTATIONS_LOCAL);
    if (rw || rl) {
        rotations = {
            boneNames: segmentNames,
            worldQuaternions: rw ? float32(rw.data) : new Float32Array(0),
            localQuaternions: rl ? float32(rl.data) : new Float32Array(0),
        };
    }

    // derived — instances DERIVED_POINTS (inline names center_of_mass / xcom, 3-col xyz)
    let centerOfMass: [number, number, number] | null = null;
    let xcom: [number, number, number] | null = null;
    const dp = channelByKind(instanceChannels, DERIVED_POINTS);
    if (dp && dp.names) {
        const raw = float32(dp.data);
        const rowOf = (name: string): [number, number, number] | null => {
            const idx = dp.names!.indexOf(name);
            if (idx === -1) return null;
            const x = raw[idx * 3];
            if (Number.isNaN(x)) return null;
            return [raw[idx * 3], raw[idx * 3 + 1], raw[idx * 3 + 2]];
        };
        centerOfMass = rowOf("center_of_mass");
        xcom = rowOf("xcom");
    }

    // segment lengths — instances SEGMENT_LENGTHS (index-keyed, 1-col length_mm)
    let segmentLengths: SegmentLengthsFrame | null = null;
    const sl = channelByKind(instanceChannels, SEGMENT_LENGTHS);
    if (sl) {
        segmentLengths = { names: segmentNames, data: float32(sl.data) };
    }

    // overlays — OVERLAY_2D (trackers, detections) + OVERLAY_REPROJECTIONS (instances, reprojections)
    const overlays: OverlayFrame[] = [];
    for (const t of frame.trackers) {
        for (const c of t.channels) {
            if (c.kind === OVERLAY_2D && c.camera_id && c.names) {
                overlays.push({
                    cameraId: c.camera_id,
                    layer: OverlayLayer.DETECTIONS,
                    frameNumber: frame.frame_number,
                    names: c.names,
                    data: float32(c.data),
                });
            }
        }
    }
    for (const inst of frame.instances) {
        for (const c of inst.channels) {
            if (c.kind === OVERLAY_REPROJECTIONS && c.camera_id) {
                overlays.push({
                    cameraId: c.camera_id,
                    layer: OverlayLayer.REPROJECTIONS,
                    frameNumber: frame.frame_number,
                    names: segmentNames,
                    data: float32(c.data),
                });
            }
        }
    }

    return { keypoints, segmentOrigins, rotations, derived: { centerOfMass, xcom }, segmentLengths, overlays };
}
