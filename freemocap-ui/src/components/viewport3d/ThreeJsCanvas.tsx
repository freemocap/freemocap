import { useCallback, useEffect, useRef } from "react";
import { Canvas } from "@react-three/fiber";
import { Box, IconButton, Tooltip } from "@mui/material";
import CenterFocusStrongIcon from "@mui/icons-material/CenterFocusStrong";
import type CameraControlsImpl from "camera-controls";
import { ThreeJsScene } from "@/components/viewport3d/ThreeJsScene";
import { fitCameraToSkeleton } from "@/components/viewport3d/fit-camera";
import { useServer } from "@/services";

export function ThreeJsCanvas() {
    const cameraControlsRef = useRef<CameraControlsImpl>(null!);
    const containerRef = useRef<HTMLDivElement>(null);
    const { getLatestTrackedPoints } = useServer();

    const handleFitToSkeleton = useCallback(() => {
        fitCameraToSkeleton(cameraControlsRef.current, getLatestTrackedPoints());
    }, [getLatestTrackedPoints]);

    // Press "F" while the viewport container is focused to fit camera to skeleton
    useEffect(() => {
        const container = containerRef.current;
        if (!container) return;

        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === "f" || e.key === "F") {
                e.preventDefault();
                handleFitToSkeleton();
            }
        };

        container.addEventListener("keydown", handleKeyDown);
        return () => container.removeEventListener("keydown", handleKeyDown);
    }, [handleFitToSkeleton]);

    return (
        <Box
            ref={containerRef}
            tabIndex={0}
            sx={{
                width: '100%',
                height: '100%',
                position: 'relative',
                outline: 'none',
            }}
        >
            <Canvas
                shadows
                camera={{ position: [5, 5, 5], fov: 75 }}
            >
                <ThreeJsScene cameraControlsRef={cameraControlsRef} />
            </Canvas>

            <Tooltip title="Fit camera to skeleton (F)" placement="left">
                <IconButton
                    onClick={handleFitToSkeleton}
                    size="small"
                    sx={{
                        position: 'absolute',
                        bottom: 16,
                        right: 16,
                        bgcolor: 'background.paper',
                        boxShadow: 2,
                        '&:hover': { bgcolor: 'action.hover' },
                    }}
                >
                    <CenterFocusStrongIcon fontSize="small" />
                </IconButton>
            </Tooltip>
        </Box>
    );
}