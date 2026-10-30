import type { ResolvedModelFrame } from '@/services/server/transport/frame-types';
import { BONE_SIDE_COLORS, classifyBone, classifyRegion, REGION_CROSS_SECTION, DEFAULT_SEGMENT_LENGTH, computeBoneMatrix } from './RigidBodyBoneInstances';
import { finitePoint, hideMatrix, XYZ_OFFSETS, type PreparedModel } from './prepared-models';

export interface PreparedBones {
    model: PreparedModel;
    baseSlot: number;
    axisMatrices: Float64Array;
    proportions: Float64Array;
    radii: Float64Array;
    colors: Float32Array;
}

export function prepareBones(model: PreparedModel, baseSlot: number): PreparedBones {
    const segments = model.definition?.segments ?? [];
    const axisMatrices = new Float64Array(segments.length * 9);
    const proportions = new Float64Array(segments.length), radii = new Float64Array(segments.length);
    const colors = new Float32Array(segments.length * 3);
    segments.forEach((segment, row) => {
        // Preserve the existing shortest-arc primary-axis transform and its rest semantics.
        // This authored transform is independent of the current frame.
        const matrix = computeBoneMatrix([0, 0, 0], [1, 0, 0, 0], segment.rest_orientation, segment.primary_axis, 1, 1)!;
        for (let r = 0; r < 3; r++) for (let c = 0; c < 3; c++) axisMatrices[row * 9 + r * 3 + c] = matrix[c * 4 + r];
        proportions[row] = Number.isFinite(segment.length_proportion) && segment.length_proportion > 0 ? segment.length_proportion : 0;
        radii[row] = REGION_CROSS_SECTION[classifyRegion(segment.name)];
        const rgb = BONE_SIDE_COLORS[classifyBone(segment.name)];
        for (let c = 0; c < 3; c++) colors[row * 3 + c] = rgb[c] * 0.7;
    });
    return {model, baseSlot, axisMatrices, proportions, radii, colors};
}

/** Explicit renderer boundary: incoming presentation rows are XYZ and scalar-first WXYZ. */
export function writeRotation(target: Float64Array, w: number, x: number, y: number, z: number): void {
    target[0] = 1 - 2 * (y * y + z * z); target[1] = 2 * (x * y - w * z); target[2] = 2 * (x * z + w * y);
    target[3] = 2 * (x * y + w * z); target[4] = 1 - 2 * (x * x + z * z); target[5] = 2 * (y * z - w * x);
    target[6] = 2 * (x * z - w * y); target[7] = 2 * (y * z + w * x); target[8] = 1 - 2 * (x * x + y * y);
}

export function writeBoneMatrices(prepared: PreparedBones, frame: ResolvedModelFrame, target: Float32Array, rotation: Float64Array): void {
    const {model, baseSlot, proportions, radii, axisMatrices} = prepared;
    const origins = frame.segmentOrigins?.data, quats = frame.rotations?.worldQuaternions;
    const stride = frame.segmentOrigins?.stride ?? 3, coordinates = frame.segmentOrigins?.coordinateOffsets ?? XYZ_OFFSETS;
    for (let row = 0; row < proportions.length; row++) {
        const o = model.originRows[row] * stride, q = model.rotationRows[row] * 4, m = (baseSlot + row) * 16;
        if (!finitePoint(origins, o, coordinates) || !finitePoint(quats, q) || !Number.isFinite(quats?.[q + 3])) {hideMatrix(target, m); continue;}
        const fitted = frame.segmentLengths?.data[model.lengthRows[row]];
        const scale = frame.segmentLengths?.fittedScaleMm;
        const length = fitted !== undefined && Number.isFinite(fitted) && fitted > 0 ? fitted
            : proportions[row] > 0 && scale != null && scale > 0 ? proportions[row] * scale : DEFAULT_SEGMENT_LENGTH;
        if (!Number.isFinite(length) || length <= 0) {hideMatrix(target, m); continue;}
        writeRotation(rotation, quats![q], quats![q + 1], quats![q + 2], quats![q + 3]);
        const a = row * 9;
        for (let col = 0; col < 3; col++) {
            const size = col === 2 ? length : radii[row];
            for (let r = 0; r < 3; r++) target[m + col * 4 + r] = (
                rotation[r * 3] * axisMatrices[a + col] + rotation[r * 3 + 1] * axisMatrices[a + 3 + col]
                + rotation[r * 3 + 2] * axisMatrices[a + 6 + col]) * size;
            target[m + col * 4 + 3] = 0;
        }
        target[m + 12] = origins![o + coordinates[0]]; target[m + 13] = origins![o + coordinates[1]]; target[m + 14] = origins![o + coordinates[2]]; target[m + 15] = 1;
    }
}
