import {RefObject} from "react";
import type CameraControlsImpl from "camera-controls";
import {SceneCamera} from "./scene/SceneCamera";
import {SceneEnvironment} from "./scene/SceneEnvironment";
import {KeypointsRenderer} from "./renderers/KeypointsRenderer";
import {FaceRenderer} from "@/components/viewport3d/renderers/FaceRenderer";
import {ConnectionRenderer} from "@/components/viewport3d/renderers/ConnectionRenderer";
import {MocapCameraRenderer} from "@/components/viewport3d/renderers/MocapCameraRenderer";
import {useViewportState} from "@/components/viewport3d/scene/ViewportStateContext";
import {useCalibrationTomlLoader} from "@/components/viewport3d/hooks/useCalibrationTomlLoader";

interface ThreeJsSceneProps {
    cameraControlsRef: RefObject<CameraControlsImpl>;
}

export function ThreeJsScene({ cameraControlsRef }: ThreeJsSceneProps) {
    const { visibility } = useViewportState();
    useCalibrationTomlLoader();

    return (
        <>
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
