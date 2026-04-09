import {RefObject} from "react";
import {CameraControls} from "@react-three/drei";
import type CameraControlsImpl from "camera-controls";
import {SceneEnvironment} from "@/components/viewport3d/SceneEnvironment";
import {SkeletonRenderer} from "@/components/viewport3d/SkeletonRenderer";
import {RigidBodyRenderer} from "@/components/viewport3d/RigidBodyRenderer";

interface ThreeJsSceneProps {
    cameraControlsRef: RefObject<CameraControlsImpl>;
}

/** Top-level scene graph: camera controls, environment, and skeleton visualization. */
export function ThreeJsScene({ cameraControlsRef }: ThreeJsSceneProps) {
    return (
        <>
            <CameraControls ref={cameraControlsRef} makeDefault />
            <SceneEnvironment />
            <SkeletonRenderer />
            <RigidBodyRenderer />
        </>
    );
}
