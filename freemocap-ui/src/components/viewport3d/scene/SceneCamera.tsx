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

// Debounce window: ignore calls while a previous animation is still in flight.
// The refinement loop fires every ~150 ms for 2 s, but camera-controls needs
// ~1–2 s to complete a smooth setLookAt transition.  Calling setLookAt again
// mid-flight restarts the interpolation → looks jumpy.
let _lastFitCallMs = 0;
const FIT_COOLDOWN_MS = 1800;

// Exponential moving average of the skeleton bounding-box center, so the
// camera target doesn't jitter frame-to-frame when the skeleton wiggles.
const _emaCenter = new Vector3();
let _emaInitialized = false;
const EMA_ALPHA = 0.3; // weight for new observation (0–1; higher = faster tracking)

/** Fit camera to skeleton-only keypoints, looking from the front.
 *
 *  Z-up coordinate system (matched to THREE default-up = (0,0,1)):
 *    Z ↑ up (along spine)    X → right (across shoulders)    Y → forward (front)
 *
 *  Camera is positioned along +Y (in front of the person) at a distance
 *  proportional to the skeleton's bounding-box extent, with a slight height
 *  offset so the view is slightly above center — a natural "eye-level" angle.
 *
 *  Debounced: accepts the first call immediately, then ignores calls within
 *  the cooldown window so the animation can finish before a new target is set.
 *  A fresh call after the cooldown has elapsed refinines the position if the
 *  skeleton has drifted significantly.
 *
 *  Uses skeleton-only data (NOT raw keypoints) so charuco board corners don't
 *  pull the bounding box away from the subject.
 */
export function fitCameraToPoints(
    controls: CameraControlsImpl | null,
    frame: KeypointsFrame | null,
): void {
    if (!controls || !frame || frame.pointNames.length === 0) return;

    const now = performance.now();
    if (now - _lastFitCallMs < FIT_COOLDOWN_MS) return;
    _lastFitCallMs = now;

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

    const rawCenter = new Vector3();
    box.getCenter(rawCenter);

    // EMA-filter the center so the look-at target doesn't jump if the
    // skeleton wiggles between cooldown windows.
    if (!_emaInitialized) {
        _emaCenter.copy(rawCenter);
        _emaInitialized = true;
    } else {
        _emaCenter.lerp(rawCenter, EMA_ALPHA);
    }

    const size = new Vector3();
    box.getSize(size);

    // Distance from the front: scale to the largest horizontal extent
    // so the whole skeleton is framed.  The 1.4× factor assumes a
    // typical ~50° perspective camera FOV.
    const frontDist = Math.max(size.x, size.y) * 1.4 + 0.5;
    const heightOffset = size.z * 0.15; // slight above-center angle

    const camX = _emaCenter.x;
    const camY = _emaCenter.y + frontDist;      // in front (along +Y)
    const camZ = _emaCenter.z + heightOffset;    // slightly above

    controls.setLookAt(camX, camY, camZ, _emaCenter.x, _emaCenter.y, _emaCenter.z, true);
}
