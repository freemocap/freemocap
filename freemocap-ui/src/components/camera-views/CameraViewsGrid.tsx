import React, {useMemo} from "react";
import ReactGridLayout, {noCompactor} from "react-grid-layout";
import "react-grid-layout/css/styles.css";
import "react-resizable/css/styles.css";
import {CameraViewWithOverlay} from "./CameraViewWithOverlay";
import {useServer} from "@/services/server/ServerContextProvider";
import {useTranslation} from "react-i18next";
import {useAppSelector} from "@/store/hooks";
import {selectAutoApply, selectCameras, selectIsLoading} from "@/store/slices/cameras/cameras-selectors";
import {useGridLayout} from "@/hooks/useGridLayout";

interface CameraViewsGridProps {
    manualColumns: number | null;
    resetKey: number;
}

export const CameraViewsGrid: React.FC<CameraViewsGridProps> = ({ manualColumns, resetKey }) => {
    const { connectedCameraIds } = useServer();
    const { t } = useTranslation();
    const isRecording = useAppSelector(state => state.recording.isRecording);
    const isLoading = useAppSelector(selectIsLoading);
    const isAutoApply = useAppSelector(selectAutoApply);
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
            <div
                ref={containerRef}
                className="flex items-center justify-center h-full w-full text-center"
                style={{
                    color: "var(--color-text-secondary)",
                    fontSize: "1.2rem",
                    padding: 32,
                }}
            >
                <div>
                    <div>{t("noCamerasConnected")}</div>
                    <div style={{ fontSize: "0.9rem", marginTop: "0.5rem" }}>
                        {t("waitingForCameraStreams")}
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div
            ref={containerRef}
            className="pos-rel overflow-hidden w-full h-full"
            style={{minHeight: 300}}
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
                        <div
                            key={cameraId}
                            className="overflow-hidden br-1"
                            style={{
                                border: isRecording
                                    ? "2px solid #ff2020"
                                    : "1px solid rgba(255,255,255,0.15)",
                                transition: "border 0.3s ease, box-shadow 0.3s ease",
                                ...(isRecording ? {animation: 'recordingBorderPulse 3s infinite ease-in-out'} : {}),
                            }}
                        >
                            <CameraViewWithOverlay cameraIndex={cam?.index ?? -1} cameraId={cameraId} isLoading={isLoading} isAutoApply={isAutoApply} />
                        </div>
                    );
                })}
            </ReactGridLayout>
        </div>
    );
};
