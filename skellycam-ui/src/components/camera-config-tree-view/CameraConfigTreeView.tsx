import React, { useEffect } from "react";
import { CameraConfigTreeViewHeader } from "./CameraConfigTreeViewHeader";
import { CameraGroupTreeItem } from "./CameraGroupTreeItem";
import { NoCamerasPlaceholder } from "./NoCamerasPlaceholder";
import {
    useAppDispatch,
    useAppSelector,
    selectCameras,
    selectIsLoading,
    selectConnectedCameras,
    selectSelectedCameras,
    selectIsPaused,
    detectCameras,
    Camera,
} from "@/store";
import { useServer } from "@/services/server/ServerContextProvider";
import { useTranslation } from 'react-i18next';

export const CameraConfigTreeView: React.FC = () => {
    const dispatch = useAppDispatch();
    const { t } = useTranslation();
    const { isConnected } = useServer();
    const cameras = useAppSelector(selectCameras);
    const isLoading = useAppSelector(selectIsLoading);
    const connectedCameras = useAppSelector(selectConnectedCameras);
    const selectedCameras = useAppSelector(selectSelectedCameras);
    const isPaused = useAppSelector(selectIsPaused);

    const availableCameras = cameras
        .filter((cam: Camera) => cam.connectionStatus !== "connected")
        .sort((a, b) => a.index - b.index);

    useEffect(() => {
        if (isConnected && cameras.length === 0) {
            dispatch(detectCameras({ filterVirtual: true }));
        }
    }, [isConnected, cameras.length, dispatch]);

    return (
        <div className="camera-tree-root border-1 border-black m-1">
            <CameraConfigTreeViewHeader
                cameraCount={cameras.length}
                isLoading={isLoading}
                isPaused={isPaused}
                hasSelectedCameras={selectedCameras.length > 0}
            />

            {cameras.length === 0 ? (
                <NoCamerasPlaceholder />
            ) : (
                <div className="flex flex-col">
                    {connectedCameras.length > 0 && (
                        <CameraGroupTreeItem
                            groupId="cameras-connected"
                            title={t("connectedCameras")}
                            cameras={connectedCameras}
                        />
                    )}
                    {availableCameras.length > 0 && (
                        <CameraGroupTreeItem
                            groupId="cameras-available"
                            title={t("availableCameras")}
                            cameras={availableCameras}
                        />
                    )}
                </div>
            )}
        </div>
    );
};
