import type { ResolvedModelFrame } from '@/services/server/transport/frame-types';
import type { ModelDefinition } from '@/services/server/transport/message-contract';

/** Names are shared by the transfer layout; content comparison also supports live sources. */
export function sameNames(a: readonly string[] | undefined, b: readonly string[] | undefined): boolean {
    if (a === b) return true;
    if (!a || !b || a.length !== b.length) return false;
    for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) return false;
    return true;
}

export function prepareRows(names: readonly string[] | undefined, wanted: readonly string[]): Int32Array {
    const indices = new Map(names?.map((name, index) => [name, index]));
    return Int32Array.from(wanted, name => indices.get(name) ?? -1);
}

export interface PreparedModel {
    frameIndex: number;
    modelId: string;
    instanceId: number;
    definition: ModelDefinition | undefined;
    originNames: readonly string[] | undefined;
    rotationNames: readonly string[] | undefined;
    lengthNames: readonly string[] | undefined;
    landmarkNames: readonly string[] | undefined;
    mappedNames: readonly string[] | undefined;
    originRows: Int32Array;
    rotationRows: Int32Array;
    lengthRows: Int32Array;
    landmarkRows: Int32Array;
}

/** Metadata only: never retains a borrowed frame buffer after the source releases it. */
export function preparedModelsMatch(prepared: readonly PreparedModel[], frames: readonly ResolvedModelFrame[], definitions: ReadonlyMap<string, ModelDefinition>): boolean {
    if (prepared.length !== frames.length) return false;
    for (let i = 0; i < frames.length; i++) {
        const p = prepared[i], f = frames[i];
        if (p.modelId !== f.modelId || p.instanceId !== f.instanceId || p.definition !== definitions.get(f.modelId)
            || !sameNames(p.originNames, f.segmentOrigins?.names)
            || !sameNames(p.rotationNames, f.rotations?.boneNames)
            || !sameNames(p.lengthNames, f.segmentLengths?.names)
            || !sameNames(p.landmarkNames, f.landmarks?.names)
            || !sameNames(p.mappedNames, f.mappedKeypoints?.names)) return false;
    }
    return true;
}

export function prepareModels(frames: readonly ResolvedModelFrame[], definitions: ReadonlyMap<string, ModelDefinition>): PreparedModel[] {
    return frames.map((frame, frameIndex) => {
        const definition = definitions.get(frame.modelId);
        const segments = definition?.segments.map(segment => segment.name) ?? [];
        return {
            frameIndex, modelId: frame.modelId, instanceId: frame.instanceId, definition,
            originNames: frame.segmentOrigins?.names, rotationNames: frame.rotations?.boneNames,
            lengthNames: frame.segmentLengths?.names, landmarkNames: frame.landmarks?.names,
            mappedNames: frame.mappedKeypoints?.names,
            originRows: prepareRows(frame.segmentOrigins?.names, segments),
            rotationRows: prepareRows(frame.rotations?.boneNames, segments),
            lengthRows: prepareRows(frame.segmentLengths?.names, segments),
            landmarkRows: prepareRows(frame.landmarks?.names, definition?.landmarks.map(point => point.name) ?? []),
        };
    });
}

export const XYZ_OFFSETS: readonly [number, number, number] = [0, 1, 2];
export function finitePoint(data: Float32Array | undefined, offset: number, coordinates: readonly number[] = XYZ_OFFSETS): boolean {
    return !!data && offset >= 0 && Number.isFinite(data[offset + coordinates[0]]) && Number.isFinite(data[offset + coordinates[1]]) && Number.isFinite(data[offset + coordinates[2]]);
}

export function hideMatrix(target: Float32Array, offset: number): void {
    target.fill(0, offset, offset + 16);
    target[offset + 15] = 1;
}
