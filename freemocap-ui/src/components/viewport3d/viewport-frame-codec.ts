import type {KeypointsFrame} from './KeypointsSourceContext';
import type {PointsFrame, ResolvedModelFrame} from '@/services/server/transport/frame-types';

export type NumericalStream = 'keypoints' | 'modelFrames';
export type NumericalFrame = KeypointsFrame | ResolvedModelFrame[];
interface ArrayLayout {names: readonly string[]; offset: number; length: number}
interface ModelLayout {
    modelId: string; instanceId: number; scalarOffset: number;
    origins: ArrayLayout | null; landmarks: ArrayLayout | null; mapped: ArrayLayout | null;
    lengths: ArrayLayout | null;
    rotations: {names: readonly string[]; worldOffset: number; localOffset: number; worldLength: number; localLength: number} | null;
}
export interface FrameLayout {
    byteLength: number;
    points: ArrayLayout | null;
    models: ModelLayout[];
}
// These are the renderer frame contract's scalar fields, not generic tensor dimensions.
const enum FrameScalar {FittedScale, LengthScale, CenterX, CenterY, CenterZ, XcomX, XcomY, XcomZ, Presence, Count}
const enum ScalarPresence {FittedScale = 1, LengthScale = 2, Center = 4, Xcom = 8}
const POSITION_COMPONENTS = 3;
const QUATERNION_COMPONENTS = 4;
function validatePointStorage(points: PointsFrame): void {
    const stride = points.stride ?? POSITION_COMPONENTS;
    const offsets = points.coordinateOffsets ?? [0, 1, 2];
    if (!Number.isInteger(stride) || stride < POSITION_COMPONENTS ||
        points.data.length !== points.names.length * stride || offsets.length !== POSITION_COMPONENTS ||
        offsets[0] === offsets[1] || offsets[0] === offsets[2] || offsets[1] === offsets[2] ||
        offsets.some(index => !Number.isInteger(index) || index < 0 || index >= stride)) {
        throw new Error('Viewport point storage does not match declared layout');
    }
}
const sameNames = (left: readonly string[], right: readonly string[]) =>
    left === right || left.length === right.length && left.every((name, index) => name === right[index]);
function samePoints(layout: ArrayLayout | null, points: PointsFrame | null, components = 3): boolean {
    return layout === null ? points === null : points !== null && layout.length === points.names.length * components && sameNames(layout.names, points.names);
}

export function frameLayoutMatches(layout: FrameLayout, type: NumericalStream, frame: NumericalFrame): boolean {
    if (type === 'keypoints') {
        const points = frame as KeypointsFrame;
        return layout.points !== null && layout.points.length === points.interleaved.length && sameNames(layout.points.names, points.pointNames);
    }
    const models = frame as ResolvedModelFrame[];
    if (layout.models.length !== models.length) return false;
    return models.every((model, index) => {
        const planned = layout.models[index];
        const rotation = model.rotations;
        return planned.modelId === model.modelId && planned.instanceId === model.instanceId &&
            samePoints(planned.origins, model.segmentOrigins) && samePoints(planned.landmarks, model.landmarks) &&
            samePoints(planned.mapped, model.mappedKeypoints) && samePoints(planned.lengths, model.segmentLengths, 1) &&
            (planned.rotations === null ? rotation === null : rotation !== null &&
                planned.rotations.worldLength === rotation.worldQuaternions.length && planned.rotations.localLength === rotation.localQuaternions.length &&
                sameNames(planned.rotations.names, rotation.boneNames));
    });
}

export function prepareFrameLayout(type: NumericalStream, frame: NumericalFrame): FrameLayout {
    let byteLength = 0;
    const arrayLayout = (names: readonly string[], data: Float32Array, components: number): ArrayLayout => {
        if (data.length !== names.length * components) throw new Error('Viewport frame does not match its declared names');
        const result = {names, offset: byteLength, length: data.length};
        byteLength += data.byteLength;
        return result;
    };
    if (type === 'keypoints') {
        const points = frame as KeypointsFrame;
        const layout = arrayLayout(points.pointNames, points.interleaved, POSITION_COMPONENTS);
        return {points: layout, models: [], byteLength};
    }
    const models = (frame as ResolvedModelFrame[]).map(model => {
        // Byte alignment only; no padding components are added to scientific values.
        byteLength = Math.ceil(byteLength / Float64Array.BYTES_PER_ELEMENT) * Float64Array.BYTES_PER_ELEMENT;
        const scalarOffset = byteLength;
        byteLength += FrameScalar.Count * Float64Array.BYTES_PER_ELEMENT;
        const pointLayout = (points: PointsFrame | null): ArrayLayout | null => {
            if (!points) return null;
            validatePointStorage(points);
            const result = {names: points.names, offset: byteLength, length: points.names.length * POSITION_COMPONENTS};
            byteLength += result.length * Float32Array.BYTES_PER_ELEMENT;
            return result;
        };
        const origins = pointLayout(model.segmentOrigins), landmarks = pointLayout(model.landmarks), mapped = pointLayout(model.mappedKeypoints);
        const lengths = model.segmentLengths ? arrayLayout(model.segmentLengths.names, model.segmentLengths.data, 1) : null;
        let rotations: ModelLayout['rotations'] = null;
        if (model.rotations) {
            const worldData = model.rotations.worldQuaternions, localData = model.rotations.localQuaternions;
            const world = arrayLayout(worldData.length ? model.rotations.boneNames : [], worldData, QUATERNION_COMPONENTS);
            const local = arrayLayout(localData.length ? model.rotations.boneNames : [], localData, QUATERNION_COMPONENTS);
            rotations = {names: model.rotations.boneNames, worldOffset: world.offset, localOffset: local.offset,
                worldLength: world.length, localLength: local.length};
        }
        return {modelId: model.modelId, instanceId: model.instanceId, scalarOffset, origins, landmarks, mapped, lengths, rotations};
    });
    return {points: null, models, byteLength};
}

export function writeFrameBuffer(buffer: ArrayBuffer, layout: FrameLayout, type: NumericalStream, frame: NumericalFrame): void {
    if (buffer.byteLength !== layout.byteLength) throw new Error('Viewport transfer buffer has the wrong size');
    const copy = (target: ArrayLayout | null, data: Float32Array | undefined) => {
        if (target && data) new Float32Array(buffer, target.offset, target.length).set(data);
    };
    if (type === 'keypoints') {copy(layout.points, (frame as KeypointsFrame).interleaved); return;}
    const frames = frame as ResolvedModelFrame[];
    const copyPoints = (target: ArrayLayout | null, points: PointsFrame | null) => {
        if (!target || !points) return;
        validatePointStorage(points);
        const stride = points.stride ?? POSITION_COMPONENTS, offsets = points.coordinateOffsets ?? [0, 1, 2];
        if (stride === POSITION_COMPONENTS && offsets[0] === 0 && offsets[1] === 1 && offsets[2] === 2) {copy(target, points.data); return;}
        const data = new Float32Array(buffer, target.offset, target.length);
        for (let row = 0; row < points.names.length; row++) {
            const from = row * stride, to = row * POSITION_COMPONENTS;
            data[to] = points.data[from + offsets[0]]; data[to + 1] = points.data[from + offsets[1]]; data[to + 2] = points.data[from + offsets[2]];
        }
    };
    for (let index = 0; index < frames.length; index++) {
        const model = frames[index], target = layout.models[index];
        const scalars = new Float64Array(buffer, target.scalarOffset, FrameScalar.Count);
        let presence = 0;
        if (model.fittedScaleMm !== null) {scalars[FrameScalar.FittedScale] = model.fittedScaleMm; presence |= ScalarPresence.FittedScale;}
        if (model.segmentLengths?.fittedScaleMm != null) {scalars[FrameScalar.LengthScale] = model.segmentLengths.fittedScaleMm; presence |= ScalarPresence.LengthScale;}
        if (model.derived.centerOfMass) {scalars.set(model.derived.centerOfMass, FrameScalar.CenterX); presence |= ScalarPresence.Center;}
        if (model.derived.xcom) {scalars.set(model.derived.xcom, FrameScalar.XcomX); presence |= ScalarPresence.Xcom;}
        scalars[FrameScalar.Presence] = presence;
        copyPoints(target.origins, model.segmentOrigins); copyPoints(target.landmarks, model.landmarks);
        copyPoints(target.mapped, model.mappedKeypoints); copy(target.lengths, model.segmentLengths?.data);
        if (target.rotations && model.rotations) {
            new Float32Array(buffer, target.rotations.worldOffset, target.rotations.worldLength).set(model.rotations.worldQuaternions);
            new Float32Array(buffer, target.rotations.localOffset, target.rotations.localLength).set(model.rotations.localQuaternions);
        }
    }
}

export function readFrameBuffer(buffer: ArrayBuffer, layout: FrameLayout, type: NumericalStream): NumericalFrame {
    if (buffer.byteLength !== layout.byteLength) throw new Error('Viewport transfer buffer has the wrong size');
    const points = (source: ArrayLayout | null): PointsFrame | null => source ?
        {names: source.names, data: new Float32Array(buffer, source.offset, source.length)} : null;
    if (type === 'keypoints') {
        if (!layout.points) throw new Error('Missing viewport keypoint layout');
        return {pointNames: layout.points.names, interleaved: new Float32Array(buffer, layout.points.offset, layout.points.length)};
    }
    return layout.models.map(model => {
        const scalars = new Float64Array(buffer, model.scalarOffset, FrameScalar.Count);
        const presence = scalars[FrameScalar.Presence];
        const fittedScaleMm = presence & ScalarPresence.FittedScale ? scalars[FrameScalar.FittedScale] : null;
        const lengths = points(model.lengths);
        return {modelId: model.modelId, instanceId: model.instanceId, fittedScaleMm,
            segmentOrigins: points(model.origins), landmarks: points(model.landmarks), mappedKeypoints: points(model.mapped),
            segmentLengths: lengths ? {...lengths, fittedScaleMm: presence & ScalarPresence.LengthScale ? scalars[FrameScalar.LengthScale] : null} : null,
            rotations: model.rotations ? {boneNames: model.rotations.names,
                worldQuaternions: new Float32Array(buffer, model.rotations.worldOffset, model.rotations.worldLength),
                localQuaternions: new Float32Array(buffer, model.rotations.localOffset, model.rotations.localLength)} : null,
            derived: {centerOfMass: presence & ScalarPresence.Center ? [scalars[FrameScalar.CenterX], scalars[FrameScalar.CenterY], scalars[FrameScalar.CenterZ]] : null,
                xcom: presence & ScalarPresence.Xcom ? [scalars[FrameScalar.XcomX], scalars[FrameScalar.XcomY], scalars[FrameScalar.XcomZ]] : null}};
    });
}

/** Current published views are borrowed until their next subscriber notification. */
export function referencedFrameBuffers(points: KeypointsFrame | null, models: ResolvedModelFrame[] | null): Set<ArrayBufferLike> {
    const buffers = new Set<ArrayBufferLike>();
    if (points) buffers.add(points.interleaved.buffer);
    for (const model of models ?? []) {
        if (model.segmentOrigins) buffers.add(model.segmentOrigins.data.buffer);
        if (model.landmarks) buffers.add(model.landmarks.data.buffer);
        if (model.mappedKeypoints) buffers.add(model.mappedKeypoints.data.buffer);
        if (model.segmentLengths) buffers.add(model.segmentLengths.data.buffer);
        if (model.rotations) {buffers.add(model.rotations.worldQuaternions.buffer); buffers.add(model.rotations.localQuaternions.buffer);}
    }
    return buffers;
}
