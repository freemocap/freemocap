import {RefObject, useEffect} from "react";
import type CameraControlsImpl from "camera-controls";
import {useFrame, useThree} from "@react-three/fiber";
import {SceneCamera} from "./scene/SceneCamera";
import {SceneEnvironment} from "./scene/SceneEnvironment";
import {KeypointsRenderer} from "./renderers/KeypointsRenderer";
import {FaceRenderer} from "@/components/viewport3d/renderers/FaceRenderer";
import {ConnectionRenderer} from "@/components/viewport3d/renderers/ConnectionRenderer";
import {MocapCameraRenderer} from "@/components/viewport3d/renderers/MocapCameraRenderer";
import {useViewportState} from "@/components/viewport3d/scene/ViewportStateContext";
import {useKeypointsSource} from "./KeypointsSourceContext";
import {workerDataStore} from "./WorkerDataStore";

/**
 * Calls invalidate() whenever scene data changes so the WebGL render loop
 * only fires on-demand instead of 60fps. Covers keypoints (high-frequency),
 * visibility, calibration, and schema (low-frequency).
 * CameraControls from drei handles its own invalidation while the camera moves.
 */
function DataInvalidator() {
    const invalidate = useThree(state => state.invalidate);
    const { subscribeToKeypointsRaw, subscribeToKeypointsFiltered } = useKeypointsSource();

    useEffect(() => {
        const unsubs = [
            subscribeToKeypointsRaw(() => invalidate()),
            subscribeToKeypointsFiltered(() => invalidate()),
            workerDataStore.subscribeToVisibility(() => invalidate()),
            workerDataStore.subscribeToCalibration(() => invalidate()),
            workerDataStore.subscribeToSchemaState(() => invalidate()),
        ];
        return () => unsubs.forEach(fn => fn());
    }, [invalidate, subscribeToKeypointsRaw, subscribeToKeypointsFiltered]);

    return null;
}

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
            <DataInvalidator />
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
