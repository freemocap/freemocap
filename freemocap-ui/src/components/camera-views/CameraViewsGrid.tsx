import React, {useMemo} from "react";
import {Box, keyframes} from "@mui/material";
import ReactGridLayout, {noCompactor} from "react-grid-layout";
import "react-grid-layout/css/styles.css";
import "react-resizable/css/styles.css";
import {CameraViewWithOverlay} from "./CameraViewWithOverlay";
import {useServer} from "@/services/server/ServerContextProvider";
import {useTranslation} from "react-i18next";
import {useAppSelector} from "@/store/hooks";
import {selectAutoApply, selectCameras, selectIsLoading} from "@/store/slices/cameras/cameras-selectors";
import {useGridLayout} from "@/hooks/useGridLayout";

const recordingBorderPulse = keyframes`
    0% { border-color: #ff2020; box-shadow: 0 0 4px rgba(255, 32, 32, 0.4); }
    50% { border-color: #aa1010; box-shadow: 0 0 8px rgba(255, 32, 32, 0.15); }
    100% { border-color: #ff2020; box-shadow: 0 0 4px rgba(255, 32, 32, 0.4); }
`;

interface CameraViewsGridProps {
    /** null = auto-optimize, number = manual column count */
    manualColumns: number | null;
    /** Increment to force a layout reset */
    resetKey: number;
}

export const CameraViewsGrid: React.FC<CameraViewsGridProps> = ({ manualColumns, resetKey }) => {
    const { connectedCameraIds } = useServer();
    const { t } = useTranslation();
    const isRecording = useAppSelector(state => state.recording.isRecording);
    const isLoading = useAppSelector(selectIsLoading);
    const isAutoApply = useAppSelector(selectAutoApply);
    // Watch camera configs for rotation/resolution changes
    const cameras = useAppSelector(selectCameras);

    const sortedCameraIds = useMemo(() => {
        const indexByCameraId = new Map<string, number>();
        for (const cam of cameras) {
            indexByCameraId.set(cam.id, cam.index);
        }
        return [...connectedCameraIds].sort((a, b) => {
            const idxA = indexByCameraId.get(a) ?? Infinity;
            const idxB = indexByCameraId.get(b) ?? Infinity;
            return idxA - idxB;
        });
    }, [connectedCameraIds, cameras]);

    const configFingerprint = useMemo(() => {
        return cameras
            .map((cam) => {
                const cfg = cam.actualConfig;
                return `${cam.id}:${cfg.rotation}:${cfg.resolution.width}x${cfg.resolution.height}`;
            })
            .join("|");
    }, [cameras]);

    const {
        containerRef,
        width,
        layout,
        gridHandlers,
        gridConfig,
    } = useGridLayout({
        itemIds: sortedCameraIds,
        margin: [4, 4],
        manualColumns,
        resetKey,
        measureParent: true,
        extraResetDeps: [configFingerprint],
    });

    if (sortedCameraIds.length === 0) {
        return (
            <Box
                ref={containerRef}
                sx={{
                    height: "100%",
                    width: "100%",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: "text.secondary",
                    fontSize: "1.2rem",
                    padding: 4,
                    textAlign: "center",
                }}
            >
                <div>
                    <div>{t("noCamerasConnected")}</div>
                    <div style={{ fontSize: "0.9rem", marginTop: "0.5rem" }}>
                        {t("waitingForCameraStreams")}
                    </div>
                </div>
            </Box>
        );
    }

    return (
        <Box
            ref={containerRef}
            sx={{
                position: "relative",
                width: "100%",
                height: "100%",
                minHeight: 300,
                overflow: "hidden",
                "& .react-grid-placeholder": {
                    backgroundColor: "primary.main",
                    opacity: 0.15,
                    borderRadius: "4px",
                },
                "& .react-grid-item > .react-resizable-handle": {
                    zIndex: 10,
                    opacity: 0.4,
                    transition: "opacity 0.2s ease",
                },
                "& .react-grid-item:hover > .react-resizable-handle": {
                    opacity: 1,
                },
                "& .react-grid-item > .react-resizable-handle::after": {
                    width: "10px",
                    height: "10px",
                    right: "4px",
                    bottom: "4px",
                    borderRight: "2px solid rgba(255, 255, 255, 0.5)",
                    borderBottom: "2px solid rgba(255, 255, 255, 0.5)",
                },
            }}
        >
            <ReactGridLayout
                width={width}
                layout={layout}
                gridConfig={gridConfig}
                dragConfig={{ enabled: true }}
                resizeConfig={{ enabled: true }}
                compactor={noCompactor}
                {...gridHandlers}
            >
                {sortedCameraIds.map((cameraId) => {
                    const cam = cameras.find(c => c.id === cameraId);
                    return (
                        <Box
                            key={cameraId}
                            sx={{
                                overflow: "hidden",
                                borderRadius: "4px",
                                border: isRecording
                                    ? "2px solid #ff2020"
                                    : "1px solid rgba(255,255,255,0.15)",
                                transition: "border 0.3s ease, box-shadow 0.3s ease",
                                ...(isRecording && {
                                    animation: `${recordingBorderPulse} 3s infinite ease-in-out`,
                                }),
                            }}
                        >
                            <CameraViewWithOverlay cameraIndex={cam?.index ?? -1} cameraId={cameraId} isLoading={isLoading} isAutoApply={isAutoApply} />
                        </Box>
                    );
                })}
            </ReactGridLayout>
        </Box>
    );
};
