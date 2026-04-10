import {useCallback, useEffect, useRef} from "react";
import {Canvas} from "@react-three/fiber";
import {Box, IconButton, Tooltip, Typography} from "@mui/material";
import CenterFocusStrongIcon from "@mui/icons-material/CenterFocusStrong";
import HomeIcon from "@mui/icons-material/Home";
import type CameraControlsImpl from "camera-controls";
import {ThreeJsScene} from "@/components/viewport3d/ThreeJsScene";
import {fitCameraToSkeleton} from "@/components/viewport3d/fit-camera";
import {useServer} from "@/services";

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
                camera={{ position: [1e3, 1e3, 1e3], fov: 75, near: 0.1, far: 10000 }}
                gl={{ antialias: true, logarithmicDepthBuffer: true }}
            >
                <ThreeJsScene cameraControlsRef={cameraControlsRef} />
            </Canvas>

            <Box sx={{ position: 'absolute', left: 16, bottom: 16, bgcolor: 'background.paper', p: 1, borderRadius: 1, boxShadow: 1 }}>
                <Typography variant="caption" color="text.secondary">
                    Rotate: drag • Zoom: scroll • Pan: right-drag or two-finger
                </Typography>
            </Box>

            <Box sx={{ position: 'absolute', bottom: 16, right: 16, display: 'flex', gap: 1 }}>
                <Tooltip title="Fit camera to skeleton (F)">
                    <IconButton
                        onClick={handleFitToSkeleton}
                        size="small"
                        sx={{
                            bgcolor: 'background.paper',
                            boxShadow: 2,
                            '&:hover': { bgcolor: 'action.hover' },
                        }}
                    >
                        <CenterFocusStrongIcon fontSize="small" />
                    </IconButton>
                </Tooltip>

                <Tooltip title="Reset view">
                    <IconButton
                        onClick={() => {
                            const cam = cameraControlsRef.current?.camera;
                            if (cam) {
                                cam.position.set(1e3, 1e3, 1e3);
                                cam.lookAt(0, 0, 0);
                                cam.updateProjectionMatrix();
                            }
                            cameraControlsRef.current?.reset(true);
                        }}
                        size="small"
                        sx={{
                            bgcolor: 'background.paper',
                            boxShadow: 2,
                            '&:hover': { bgcolor: 'action.hover' },
                        }}
                    >
                        <HomeIcon fontSize="small" />
                    </IconButton>
                </Tooltip>
            </Box>
        </Box>
    );
}
