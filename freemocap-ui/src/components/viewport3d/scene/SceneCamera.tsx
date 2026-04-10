import { useCallback, useEffect } from "react";
import { CameraControls } from "@react-three/drei";
import type CameraControlsImpl from "camera-controls";
import { Box3, Vector3 } from "three";
import { useServer } from "@/services";
import { Point3d } from "../helpers/viewport3d-types";
import { RefObject } from "react";

const PADDING = 0.5;

interface SceneCameraProps {
    controlsRef: RefObject<CameraControlsImpl>;
}

export function SceneCamera({ controlsRef }: SceneCameraProps) {
    return <CameraControls ref={controlsRef} makeDefault />;
}

/** Fit camera to bounding box of all keypoints. */
export function fitCameraToPoints(
    controls: CameraControlsImpl | null,
    points: Record<string, Point3d>,
): void {
    if (!controls || Object.keys(points).length === 0) return;
    const box = new Box3();
    for (const pt of Object.values(points)) {
        box.expandByPoint(new Vector3(pt.x, pt.y, pt.z));
    }
    box.expandByScalar(PADDING);
    controls.fitToBox(box, true);
}
