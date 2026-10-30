import {OverlayLayer, type OverlayFrame} from '../../transport/frame-types';

/** Camera overlays retain numerical arrays through the image-worker boundary. */
export interface SkeletonObservation {
    camera_id: string;
    frame_number: number;
    image_width: number;
    image_height: number;
    pointLayers: OverlayFrame[];
    landmarkLayers: {values: OverlayFrame; connections: readonly (readonly [string, string])[]}[];
    boxLayers: OverlayFrame[];
}

/** Append layer descriptors, never scalarize or copy numerical payloads. */
export function appendOverlay(
    observation: SkeletonObservation,
    values: OverlayFrame,
    connections: readonly (readonly [string, string])[] = [],
): void {
    if (values.layer === OverlayLayer.DETECTIONS) observation.pointLayers.push(values);
    else if (values.layer === OverlayLayer.REPROJECTIONS) observation.landmarkLayers.push({values, connections});
    else if (values.layer === OverlayLayer.BOXES) observation.boxLayers.push(values);
}
