import { useCallback, useEffect, useRef } from "react";
import { Canvas } from "@react-three/fiber";
import { Box } from "@mui/material";
import type CameraControlsImpl from "camera-controls";
import { ThreeJsScene } from "./ThreeJsScene";
import { ViewportOverlay } from "./scene/ViewportOverlay";
import { ViewportStateProvider } from "./scene/ViewportStateContext";
import { fitCameraToPoints } from "./scene/SceneCamera";
import { useServer } from "@/services";

export function ThreeJsCanvas() {
    const controlsRef = useRef<CameraControlsImpl>(null!);
    const containerRef = useRef<HTMLDivElement>(null);
    const { getLatestKeypointsRaw } = useServer();

    const handleFit = useCallback(() => {
        fitCameraToPoints(controlsRef.current, getLatestKeypointsRaw());
    }, [getLatestKeypointsRaw]);

    const handleReset = useCallback(() => {
        controlsRef.current?.reset(true);
    }, []);

    // "F" key shortcut
    useEffect(() => {
        const el = containerRef.current;
        if (!el) return;
        const onKey = (e: KeyboardEvent) => {
            if (e.key === "f" || e.key === "F") { e.preventDefault(); handleFit(); }
        };
        el.addEventListener("keydown", onKey);
        return () => el.removeEventListener("keydown", onKey);
    }, [handleFit]);

    return (
        <ViewportStateProvider>
            <Box
                ref={containerRef}
                tabIndex={0}
                sx={{ width: "100%", height: "100%", position: "relative", outline: "none" }}
            >
                <Canvas
                    shadows
                    camera={{ position: [1e3, 1e3, 1e3], fov: 75, near: 0.1, far: 1e5 }}
                    gl={{ antialias: true, logarithmicDepthBuffer: true }}
                >
                    <ThreeJsScene cameraControlsRef={controlsRef} />
                </Canvas>

                <ViewportOverlay onFitCamera={handleFit} onResetCamera={handleReset} />
            </Box>
        </ViewportStateProvider>
    );
}
