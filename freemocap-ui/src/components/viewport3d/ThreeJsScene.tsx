import {RefObject} from "react";
import type CameraControlsImpl from "camera-controls";
import {SceneCamera} from "./scene/SceneCamera";
import {SceneEnvironment} from "./scene/SceneEnvironment";
import {KeypointsRenderer} from "./renderers/KeypointsRenderer";
import {FaceRenderer} from "@/components/viewport3d/renderers/FaceRenderer";
import {ConnectionRenderer} from "@/components/viewport3d/renderers/ConnectionRenderer";
import {useViewportState} from "@/components/viewport3d/scene/ViewportStateContext";

interface ThreeJsSceneProps {
    cameraControlsRef: RefObject<CameraControlsImpl>;
}

export function ThreeJsScene({ cameraControlsRef }: ThreeJsSceneProps) {
    const { visibility } = useViewportState();

    return (
        <>
            <SceneCamera controlsRef={cameraControlsRef} />
            <SceneEnvironment />
            <KeypointsRenderer />
            {/*{visibility.rigidBodies && <RigidBodyRenderer />}*/}
            {visibility.connections && <ConnectionRenderer />}
            {visibility.face && <FaceRenderer />}
        </>
    );
}
