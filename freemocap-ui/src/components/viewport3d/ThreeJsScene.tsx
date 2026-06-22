import {RefObject, useEffect, useRef} from "react";
import type CameraControlsImpl from "camera-controls";
import {useFrame, useThree} from "@react-three/fiber";
import {Vector2} from "three";
import {EffectComposer} from "three/examples/jsm/postprocessing/EffectComposer";
import {RenderPass} from "three/examples/jsm/postprocessing/RenderPass";
import {UnrealBloomPass} from "three/examples/jsm/postprocessing/UnrealBloomPass";
import {SceneCamera} from "./scene/SceneCamera";
import {SceneEnvironment} from "./scene/SceneEnvironment";
import {KeypointsRenderer} from "./renderers/KeypointsRenderer";
import {FaceRenderer} from "@/components/viewport3d/renderers/FaceRenderer";
import {ConnectionRenderer} from "@/components/viewport3d/renderers/ConnectionRenderer";
import {MocapCameraRenderer} from "@/components/viewport3d/renderers/MocapCameraRenderer";
import {CenterOfMassRenderer} from "@/components/viewport3d/renderers/CenterOfMassRenderer";
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
    const { subscribeToKeypoints, subscribeToSkeleton } = useKeypointsSource();

    useEffect(() => {
        const unsubs = [
            subscribeToKeypoints(() => invalidate()),
            subscribeToSkeleton(() => invalidate()),
            workerDataStore.subscribeToVisibility(() => invalidate()),
            workerDataStore.subscribeToCalibration(() => invalidate()),
            workerDataStore.subscribeToSchemaState(() => invalidate()),
        ];
        return () => unsubs.forEach(fn => fn());
    }, [invalidate, subscribeToKeypoints, subscribeToSkeleton]);

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
            if (elapsed > 8) console.debug(`R3F frame cost: ${elapsed.toFixed(1)}ms`);
        });
    });
    return null;
}

/**
 * Bloom post-processing pass — only pixels brighter than the threshold glow.
 * The CoM sphere's emissive white squares are the primary bloom source;
 * keypoints and connection lines (MeshBasicMaterial, full-brightness) are
 * just under the threshold so they don't bleed.
 */
function BloomLayer() {
    const { gl, scene, camera, size } = useThree();
    const composerRef = useRef<EffectComposer | null>(null);

    useEffect(() => {
        const composer = new EffectComposer(gl);
        composer.addPass(new RenderPass(scene, camera));
        const bloom = new UnrealBloomPass(
            new Vector2(size.width, size.height),
            1.0,    // strength — visible but not cartoonish
            0.4,    // radius — tight glow around the object
            0.9,    // threshold — only very bright pixels bloom (CoM white squares)
        );
        composer.addPass(bloom);
        composerRef.current = composer;
        return () => composer.dispose();
    }, [gl, scene, camera, size]);

    useEffect(() => {
        const composer = composerRef.current;
        if (!composer) return;
        composer.setSize(size.width, size.height);
    }, [size]);

    // Render via the composer instead of r3f's default output.
    // gl.autoClear is set false so r3f's internal draw doesn't clear before the
    // composer re-renders. Priority 1 runs this callback last in the useFrame chain.
    useFrame(() => {
        gl.autoClear = false;
        composerRef.current?.render();
    }, 1);

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
            {/* Dev-only: queues a microtask + perf.now() every rendered frame.
                Gated out of production so it adds zero per-frame overhead. */}
            {import.meta.env.DEV && <FrameProfiler />}
            <SceneCamera controlsRef={cameraControlsRef} />
            <SceneEnvironment />
            <KeypointsRenderer />
            {visibility.centerOfMass && <CenterOfMassRenderer />}
            {visibility.connections && <ConnectionRenderer />}
            {visibility.face && <FaceRenderer />}
            {visibility.cameras && <MocapCameraRenderer />}
            <BloomLayer />
        </>
    );
}
