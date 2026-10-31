import type {KeypointsFrame} from './KeypointsSourceContext';
import type {PointsFrame, ResolvedModelFrame} from '@/services/server/transport/frame-types';

import {POSITION_COMPONENTS, validatePointStorage, validateKeypointStorage, copyPointCoordinates, copyKeypointCoordinates} from './keypoint-storage';

export type NumericalStream = 'keypoints' | 'modelFrames';
export type NumericalFrame = KeypointsFrame | ResolvedModelFrame[];
interface StatusGroup {startIndex: number; count: number; labels: readonly string[]}
interface ArrayLayout {names: readonly string[]; offset: number; length: number;
    statusOffset?: number; statusLabels?: readonly string[]; statusGroups?: readonly StatusGroup[]}
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
const QUATERNION_COMPONENTS = 4;
const sameNames = (left: readonly string[], right: readonly string[]) =>
    left === right || left.length === right.length && left.every((name, index) => name === right[index]);
function samePoints(layout: ArrayLayout | null, points: PointsFrame | null, components: number = POSITION_COMPONENTS): boolean {
    return layout === null ? points === null : points !== null && layout.length === points.names.length * components && sameNames(layout.names, points.names)
        && (layout.statusOffset !== undefined) === (points.sampleStatus !== undefined)
        && sameNames(layout.statusLabels ?? [], points.statusLabels ?? []);
}

function keypointStatusGroups(points: KeypointsFrame): readonly StatusGroup[] {
    if ('interleaved' in points) return points.statusGroups ?? [];
    const groups: StatusGroup[] = [];
    let startIndex = 0;
    for (const source of points.pointSources) {
        if (source.sampleStatus) {
            if (!source.statusLabels || source.sampleStatus.length !== source.names.length) throw new Error('Invalid point status layout');
            groups.push({startIndex, count: source.names.length, labels: source.statusLabels});
        }
        startIndex += source.names.length;
    }
    return groups;
}

function keypointStatusMatches(layout: ArrayLayout, points: KeypointsFrame): boolean {
    const groups = layout.statusGroups;
    if ('interleaved' in points) {
        const current = points.statusGroups;
        return groups === current || (groups?.length ?? 0) === (current?.length ?? 0) && (groups ?? []).every((group, index) =>
            group.startIndex === current![index].startIndex && group.count === current![index].count && sameNames(group.labels, current![index].labels));
    }
    let startIndex = 0, groupIndex = 0;
    for (const source of points.pointSources) {
        if (source.sampleStatus) {
            const group = groups?.[groupIndex++];
            if (!group || !source.statusLabels || group.startIndex !== startIndex || group.count !== source.names.length
                || !sameNames(group.labels, source.statusLabels)) return false;
        }
        startIndex += source.names.length;
    }
    return groupIndex === (groups?.length ?? 0);
}

export function frameLayoutMatches(layout: FrameLayout, type: NumericalStream, frame: NumericalFrame): boolean {
    if (type === 'keypoints') {
        const points = frame as KeypointsFrame;
        return layout.points !== null && layout.points.length === points.pointNames.length * POSITION_COMPONENTS && sameNames(layout.points.names, points.pointNames)
            && keypointStatusMatches(layout.points, points);
    }
    const models = frame as ResolvedModelFrame[];
    if (layout.models.length !== models.length) return false;
    return models.every((model, index) => {
        const planned = layout.models[index];
        const rotation = model.rotations;
        return planned.modelId === model.modelId && planned.instanceId === model.instanceId &&
            samePoints(planned.origins, model.segmentOrigins) && samePoints(planned.landmarks, model.landmarks) &&
            samePoints(planned.mapped, model.mappedKeypoints) && (samePoints(planned.lengths, model.segmentLengths, 1) && (!model.segmentLengths || model.segmentLengths.data.length === model.segmentLengths.names.length)) &&
            (planned.rotations === null ? rotation === null : rotation !== null &&
                planned.rotations.worldLength === rotation.worldQuaternions.length && planned.rotations.localLength === rotation.localQuaternions.length &&
                sameNames(planned.rotations.names, rotation.boneNames));
    });
}

export function prepareFrameLayout(type: NumericalStream, frame: NumericalFrame): FrameLayout {
    let byteLength = 0;
    const arrayLayout = (names: readonly string[], data: Float32Array, components: number): ArrayLayout => {
        if (data.length !== names.length * components) throw new Error('Viewport frame does not match its declared names');
        byteLength = Math.ceil(byteLength / Float32Array.BYTES_PER_ELEMENT) * Float32Array.BYTES_PER_ELEMENT;
        const result = {names, offset: byteLength, length: data.length};
        byteLength += data.byteLength;
        return result;
    };
    if (type === 'keypoints') {
        const points = frame as KeypointsFrame;
        validateKeypointStorage(points);
        const layout: ArrayLayout = {names: points.pointNames, offset: 0, length: points.pointNames.length * POSITION_COMPONENTS};
        byteLength = layout.length * Float32Array.BYTES_PER_ELEMENT;
        const groups = keypointStatusGroups(points);
        if (groups.length) {
            layout.statusOffset = byteLength;
            layout.statusGroups = groups;
            byteLength += points.pointNames.length;
        }
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
            byteLength = Math.ceil(byteLength / Float32Array.BYTES_PER_ELEMENT) * Float32Array.BYTES_PER_ELEMENT;
            const result: ArrayLayout = {names: points.names, offset: byteLength, length: points.names.length * POSITION_COMPONENTS};
            byteLength += result.length * Float32Array.BYTES_PER_ELEMENT;
            if (points.sampleStatus) {
                if (!points.statusLabels || points.sampleStatus.length !== points.names.length) throw new Error('Invalid point status layout');
                result.statusOffset = byteLength;
                result.statusLabels = points.statusLabels;
                byteLength += points.names.length;
            }
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
        if ((target === null) !== (data === undefined) || target && data && target.length !== data.length)
            throw new Error('Viewport scalar storage does not match declared layout');
        if (target && data) new Float32Array(buffer, target.offset, target.length).set(data);
    };
    if (type === 'keypoints') {
        if (!layout.points) throw new Error('Missing viewport keypoint layout');
        copyKeypointCoordinates(new Float32Array(buffer, layout.points.offset, layout.points.length), frame as KeypointsFrame);
        if (layout.points.statusOffset !== undefined) {
            const points = frame as KeypointsFrame;
            const status = new Uint8Array(buffer, layout.points.statusOffset, layout.points.names.length);
            status.fill(0); // Unlabelled ranges have no status group, not an inferred meaning.
            if ('interleaved' in points) {
                if (!points.sampleStatus || points.sampleStatus.length !== status.length) throw new Error('Invalid packed point status');
                status.set(points.sampleStatus);
            } else {
                let startIndex = 0;
                for (const source of points.pointSources) {
                    if (source.sampleStatus) {
                        if (source.sampleStatus.length !== source.names.length) throw new Error('Invalid point source status');
                        status.set(source.sampleStatus, startIndex);
                    }
                    startIndex += source.names.length;
                }
            }
        }
        return;
    }
    const frames = frame as ResolvedModelFrame[];
    if (frames.length !== layout.models.length) throw new Error('Viewport model count does not match declared layout');
    const copyPoints = (target: ArrayLayout | null, points: PointsFrame | null) => {
        if ((target === null) !== (points === null)) throw new Error('Viewport point presence does not match declared layout');
        if (!target || !points) return;
        if (target.length !== points.names.length * POSITION_COMPONENTS)
            throw new Error('Viewport point destination does not match declared layout');
        copyPointCoordinates(new Float32Array(buffer, target.offset, target.length), points);
        if (target.statusOffset !== undefined) {
            if (!points.sampleStatus || points.sampleStatus.length !== target.names.length) throw new Error('Invalid point status length');
            new Uint8Array(buffer, target.statusOffset, target.names.length).set(points.sampleStatus);
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
        if ((target.rotations === null) !== (model.rotations === null)) throw new Error('Viewport rotation presence does not match declared layout');
        if (target.rotations && model.rotations) {
            if (target.rotations.worldLength !== model.rotations.worldQuaternions.length || target.rotations.localLength !== model.rotations.localQuaternions.length)
                throw new Error('Viewport rotation storage does not match declared layout');
            new Float32Array(buffer, target.rotations.worldOffset, target.rotations.worldLength).set(model.rotations.worldQuaternions);
            new Float32Array(buffer, target.rotations.localOffset, target.rotations.localLength).set(model.rotations.localQuaternions);
        }
    }
}

export function readFrameBuffer(buffer: ArrayBuffer, layout: FrameLayout, type: NumericalStream): NumericalFrame {
    if (buffer.byteLength !== layout.byteLength) throw new Error('Viewport transfer buffer has the wrong size');
    const points = (source: ArrayLayout | null): PointsFrame | null => source ?
        {names: source.names, data: new Float32Array(buffer, source.offset, source.length),
            ...(source.statusOffset === undefined ? {} : {sampleStatus: new Uint8Array(buffer, source.statusOffset, source.names.length),
                statusLabels: source.statusLabels})} : null;
    if (type === 'keypoints') {
        if (!layout.points) throw new Error('Missing viewport keypoint layout');
        return {pointNames: layout.points.names, interleaved: new Float32Array(buffer, layout.points.offset, layout.points.length),
            ...(layout.points.statusOffset === undefined ? {} : {sampleStatus: new Uint8Array(buffer, layout.points.statusOffset, layout.points.names.length),
                statusGroups: layout.points.statusGroups})};
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
    if (points) {
        if ('interleaved' in points) {
            buffers.add(points.interleaved.buffer);
            if (points.sampleStatus) buffers.add(points.sampleStatus.buffer);
        } else for (const source of points.pointSources) {
            buffers.add(source.data.buffer);
            if (source.sampleStatus) buffers.add(source.sampleStatus.buffer);
        }
    }
    for (const model of models ?? []) {
        if (model.segmentOrigins?.sampleStatus) buffers.add(model.segmentOrigins.sampleStatus.buffer);
        if (model.landmarks?.sampleStatus) buffers.add(model.landmarks.sampleStatus.buffer);
        if (model.mappedKeypoints?.sampleStatus) buffers.add(model.mappedKeypoints.sampleStatus.buffer);
        if (model.segmentOrigins) buffers.add(model.segmentOrigins.data.buffer);
        if (model.landmarks) buffers.add(model.landmarks.data.buffer);
        if (model.mappedKeypoints) buffers.add(model.mappedKeypoints.data.buffer);
        if (model.segmentLengths) buffers.add(model.segmentLengths.data.buffer);
        if (model.rotations) {buffers.add(model.rotations.worldQuaternions.buffer); buffers.add(model.rotations.localQuaternions.buffer);}
    }
    return buffers;
}
