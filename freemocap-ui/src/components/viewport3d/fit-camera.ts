import { Box3, Vector3 } from "three";
import type CameraControlsImpl from "camera-controls";
import { Z_OFFSET } from "@/components/skeleton-colors.ts/skeleton-config";
import {Point3d} from "@/services";

const PADDING = 0.5;

/**
 * Compute a bounding box around all tracked points and smoothly
 * transition the camera to frame it. No-ops if there are no points
 * or CameraControls isn't ready.
 */
export function fitCameraToSkeleton(
    controls: CameraControlsImpl | null,
    points: Map<string, Point3d>,
): void {
    if (!controls || points.size === 0) return;

    const box = new Box3();
    for (const point of points.values()) {
        box.expandByPoint(new Vector3(point.x, point.y, point.z + Z_OFFSET));
    }
    box.expandByScalar(PADDING);

    controls.fitToBox(box, true);
}
