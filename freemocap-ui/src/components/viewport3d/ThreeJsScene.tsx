import {RefObject} from "react";
import type CameraControlsImpl from "camera-controls";
import {SceneCamera} from "./scene/SceneCamera";
import {SceneEnvironment} from "./scene/SceneEnvironment";
import {KeypointsRenderer} from "./renderers/KeypointsRenderer";

interface ThreeJsSceneProps {
    cameraControlsRef: RefObject<CameraControlsImpl>;
}

export function ThreeJsScene({ cameraControlsRef }: ThreeJsSceneProps) {
    // const { visibility } = useViewportState();

    return (
        <>
            <SceneCamera controlsRef={cameraControlsRef} />
            <SceneEnvironment />
            <KeypointsRenderer />
            {/*{visibility.rigidBodies && <RigidBodyRenderer />}*/}
            {/*{visibility.face && <FaceRenderer />}*/}
        </>
    );
}
