import { useCallback, useEffect } from "react";
import { CameraControls } from "@react-three/drei";
import type CameraControlsImpl from "camera-controls";
import { Box3, Vector3 } from "three";
import { RefObject } from "react";
import type { KeypointsFrame } from "../KeypointsSourceContext";

const PADDING = 0.5;

interface SceneCameraProps {
    controlsRef: RefObject<CameraControlsImpl>;
}

export function SceneCamera({ controlsRef }: SceneCameraProps) {
    return <CameraControls ref={controlsRef} makeDefault />;
}

/** Fit camera to bounding box of all visible keypoints. */
export function fitCameraToPoints(
    controls: CameraControlsImpl | null,
    frame: KeypointsFrame | null,
): void {
    if (!controls || !frame || frame.pointNames.length === 0) return;
    const { pointNames, interleaved } = frame;
    const box = new Box3();
    for (let i = 0; i < pointNames.length; i++) {
        const off = i * 4;
        const vis = interleaved[off + 3];
        const x = interleaved[off];
        const y = interleaved[off + 1];
        const z = interleaved[off + 2];
        if (vis > 0 && Number.isFinite(x) && Number.isFinite(y) && Number.isFinite(z)) {
            box.expandByPoint(new Vector3(x, y, z));
        }
    }
    if (box.isEmpty()) return;
    box.expandByScalar(PADDING);
    controls.fitToBox(box, true);
}
