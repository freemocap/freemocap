import type {PointsFrame} from '@/services/server/transport/frame-types';
import type {KeypointsFrame} from './KeypointsSourceContext';

export const XYZ_OFFSETS = [0, 1, 2] as const;
export const POSITION_COMPONENTS = XYZ_OFFSETS.length;

export function validatePointStorage(points: PointsFrame): void {
    const stride = points.stride ?? POSITION_COMPONENTS;
    const offsets = points.coordinateOffsets ?? XYZ_OFFSETS;
    if (!Number.isInteger(stride) || stride < POSITION_COMPONENTS ||
        points.data.length !== points.names.length * stride || offsets.length !== POSITION_COMPONENTS ||
        offsets[0] === offsets[1] || offsets[0] === offsets[2] || offsets[1] === offsets[2] ||
        offsets.some(index => !Number.isInteger(index) || index < 0 || index >= stride)) {
        throw new Error('Viewport point storage does not match declared layout');
    }
}

/** Pack directly into the consumer-owned destination, without an intermediate XYZ array. */
export function copyPointCoordinates(target: Float32Array, points: PointsFrame, targetRow = 0): void {
    validatePointStorage(points);
    const stride = points.stride ?? POSITION_COMPONENTS, offsets = points.coordinateOffsets ?? XYZ_OFFSETS;
    const targetOffset = targetRow * POSITION_COMPONENTS;
    if (targetOffset < 0 || targetOffset + points.names.length * POSITION_COMPONENTS > target.length)
        throw new Error('Viewport point destination does not match declared layout');
    if (stride === POSITION_COMPONENTS && offsets[0] === 0 && offsets[1] === 1 && offsets[2] === 2) {
        target.set(points.data, targetOffset);
        return;
    }
    for (let row = 0; row < points.names.length; row++) {
        const from = row * stride, to = targetOffset + row * POSITION_COMPONENTS;
        target[to] = points.data[from + offsets[0]];
        target[to + 1] = points.data[from + offsets[1]];
        target[to + 2] = points.data[from + offsets[2]];
    }
}

export function validateKeypointStorage(frame: KeypointsFrame): void {
    if ('interleaved' in frame) {
        if (frame.interleaved.length !== frame.pointNames.length * POSITION_COMPONENTS)
            throw new Error('Viewport keypoint storage does not match declared names');
    } else {
        let count = 0;
        for (const source of frame.pointSources) {validatePointStorage(source); count += source.names.length;}
        if (count !== frame.pointNames.length) throw new Error('Viewport keypoint sources do not match declared names');
    }
}

export function copyKeypointCoordinates(target: Float32Array, frame: KeypointsFrame): void {
    validateKeypointStorage(frame);
    if (target.length !== frame.pointNames.length * POSITION_COMPONENTS)
        throw new Error('Viewport keypoint destination does not match declared names');
    if ('interleaved' in frame) {target.set(frame.interleaved); return;}
    let row = 0;
    for (const source of frame.pointSources) {copyPointCoordinates(target, source, row); row += source.names.length;}
}

/** Direct rendering fallback only: resize when the layout size changes, then reuse the owned array. */
export class KeypointPackingWorkspace {
    private coordinates = new Float32Array();
    packFrame(frame: KeypointsFrame): Float32Array {
        if ('interleaved' in frame) return frame.interleaved;
        const length = frame.pointNames.length * POSITION_COMPONENTS;
        if (this.coordinates.length !== length) this.coordinates = new Float32Array(length);
        copyKeypointCoordinates(this.coordinates, frame);
        return this.coordinates;
    }
}

/** Occasional inspection lookup; never projects a complete frame. */
export function keypointPosition(frame: KeypointsFrame, index: number): [number, number, number] | null {
    if (index < 0 || index >= frame.pointNames.length) return null;
    if ('interleaved' in frame) {
        const offset = index * POSITION_COMPONENTS;
        return [frame.interleaved[offset], frame.interleaved[offset + 1], frame.interleaved[offset + 2]];
    }
    for (const source of frame.pointSources) {
        if (index < source.names.length) {
            const offset = index * (source.stride ?? POSITION_COMPONENTS), coordinates = source.coordinateOffsets ?? XYZ_OFFSETS;
            return [source.data[offset + coordinates[0]], source.data[offset + coordinates[1]], source.data[offset + coordinates[2]]];
        }
        index -= source.names.length;
    }
    return null;
}

/** Channel views for infrequent camera framing; packed input also remains a borrowed view. */
export function keypointSources(frame: KeypointsFrame): readonly PointsFrame[] {
    return 'interleaved' in frame ? [{names: frame.pointNames, data: frame.interleaved}] : frame.pointSources;
}

export function hasVisibleKeypoints(frame: KeypointsFrame): boolean {
    for (const source of keypointSources(frame)) {
        const stride = source.stride ?? POSITION_COMPONENTS, offsets = source.coordinateOffsets ?? XYZ_OFFSETS;
        for (let index = 0; index < source.names.length; index++) {
            const row = index * stride;
            if (Number.isFinite(source.data[row + offsets[0]]) && Number.isFinite(source.data[row + offsets[1]]) && Number.isFinite(source.data[row + offsets[2]])) return true;
        }
    }
    return false;
}
