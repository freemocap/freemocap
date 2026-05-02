import {RefObject} from "react";
import type CameraControlsImpl from "camera-controls";
import {useFrame} from "@react-three/fiber";
import {SceneCamera} from "./scene/SceneCamera";
import {SceneEnvironment} from "./scene/SceneEnvironment";
import {KeypointsRenderer} from "./renderers/KeypointsRenderer";
import {FaceRenderer} from "@/components/viewport3d/renderers/FaceRenderer";
import {ConnectionRenderer} from "@/components/viewport3d/renderers/ConnectionRenderer";
import {MocapCameraRenderer} from "@/components/viewport3d/renderers/MocapCameraRenderer";
import {useViewportState} from "@/components/viewport3d/scene/ViewportStateContext";

/** Logs when a single R3F frame's work (useFrame callbacks + GPU upload) takes too long. */
function FrameProfiler() {
    useFrame(() => {
        const t0 = performance.now();
        // queueMicrotask fires after all useFrame hooks and Three.js GPU uploads in this
        // tick but before the next browser task, giving a real intra-frame cost.
        queueMicrotask(() => {
            const elapsed = performance.now() - t0;
            if (elapsed > 8) console.warn(`R3F frame cost: ${elapsed.toFixed(1)}ms`);
        });
    });
    return null;
}

interface ThreeJsSceneProps {
    cameraControlsRef: RefObject<CameraControlsImpl>;
}

export function ThreeJsScene({ cameraControlsRef }: ThreeJsSceneProps) {
    const { visibility } = useViewportState();

    return (
        <>
            <FrameProfiler />
            <SceneCamera controlsRef={cameraControlsRef} />
            <SceneEnvironment />
            <KeypointsRenderer />
            {/*{visibility.rigidBodies && <RigidBodyRenderer />}*/}
            {visibility.connections && <ConnectionRenderer />}
            {visibility.face && <FaceRenderer />}
            {visibility.cameras && <MocapCameraRenderer />}
        </>
    );
}
