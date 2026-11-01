import type {ResolvedModelFrame} from '@/services/server/transport/frame-types';
import {finitePoint, XYZ_OFFSETS, type PreparedModel} from './prepared-models';
import {writeRotation} from './prepared-bones';
import {BONE_SIDE_COLORS, classifyBone} from './RigidBodyBoneInstances';
import {Color} from 'three';
import type {ModelDefinition} from '@/services/server/transport/message-contract';

export const HIDDEN_LINE_COORDINATE = 1e5;
export interface PreparedAttachedLines {
    frameIndex: number;
    originRow: number;
    rotationRow: number;
    lengthRow: number;
    authoredLength: number;
    baseEdge: number;
    positions: Float32Array;
    color: readonly number[];
    opacity: number;
    surfaces: NonNullable<NonNullable<ModelDefinition['presentation']>['attached_lines'][number]['surfaces']>;
}

/** Definition/layout-time only. Owns local vertices, never borrowed frame arrays. */
export function prepareAttachedLines(models: readonly PreparedModel[], baseEdge: number): PreparedAttachedLines[] {
    const result: PreparedAttachedLines[] = [];
    for (const model of models) {
        for (const lines of model.definition?.presentation?.attached_lines ?? []) {
            const row = model.definition!.segments.findIndex(segment => segment.name === lines.segment);
            if (row < 0) continue;
            result.push({frameIndex: model.frameIndex, originRow: model.originRows[row], rotationRow: model.rotationRows[row],
                lengthRow: model.lengthRows[row], authoredLength: lines.authored_length, baseEdge,
                // Construction contours are subordinate to the anatomical connections.
                positions: Float32Array.from(lines.positions),
                color: lines.material ? new Color(lines.material.color).toArray() : BONE_SIDE_COLORS[classifyBone(lines.segment)].map(value => value * 0.6),
                opacity: lines.material?.opacity ?? 0.85, surfaces: lines.surfaces ?? []});
            baseEdge += lines.positions.length / 6;
        }
    }
    return result;
}

/** Allocation-free frame update into the existing line batch. Missing pose hides the whole contour. */
export function writeAttachedPose(batch: PreparedAttachedLines, frame: ResolvedModelFrame, rotation: Float64Array): number {
    const origins = frame.segmentOrigins?.data, quats = frame.rotations?.worldQuaternions;
    const coordinates = frame.segmentOrigins?.coordinateOffsets ?? XYZ_OFFSETS;
    const o = batch.originRow * (frame.segmentOrigins?.stride ?? 3), q = batch.rotationRow * 4;
    // A present but invalid segment length is missing geometry, not permission to invent a size.
    const length = frame.segmentLengths ? frame.segmentLengths.data[batch.lengthRow] : undefined;
    const scale = frame.segmentLengths ? (length ?? NaN) / batch.authoredLength : (frame.fittedScaleMm ?? NaN);
    const norm = quats ? quats[q] ** 2 + quats[q + 1] ** 2 + quats[q + 2] ** 2 + quats[q + 3] ** 2 : NaN;
    if (!finitePoint(origins, o, coordinates) || !Number.isFinite(norm) || Math.abs(norm - 1) > 0.01
        || !Number.isFinite(scale) || scale <= 0) {
        return NaN;
    }
    writeRotation(rotation, quats![q], quats![q + 1], quats![q + 2], quats![q + 3]);
    return scale;
}

export function writeAttachedLines(batch: PreparedAttachedLines, frame: ResolvedModelFrame,
    target: Float32Array, rotation: Float64Array): boolean {
    const scale = writeAttachedPose(batch, frame, rotation), base = batch.baseEdge * 6;
    if (!Number.isFinite(scale)) {target.fill(HIDDEN_LINE_COORDINATE, base, base + batch.positions.length); return false;}
    const origins = frame.segmentOrigins!.data, coordinates = frame.segmentOrigins!.coordinateOffsets ?? XYZ_OFFSETS;
    const o = batch.originRow * (frame.segmentOrigins!.stride ?? 3);
    const local = batch.positions;
    for (let i = 0; i < local.length; i += 3) {
        const x = local[i] * scale, y = local[i + 1] * scale, z = local[i + 2] * scale;
        target[base + i] = origins![o + coordinates[0]] + rotation[0] * x + rotation[1] * y + rotation[2] * z;
        target[base + i + 1] = origins![o + coordinates[1]] + rotation[3] * x + rotation[4] * y + rotation[5] * z;
        target[base + i + 2] = origins![o + coordinates[2]] + rotation[6] * x + rotation[7] * y + rotation[8] * z;
    }
    return true;
}
