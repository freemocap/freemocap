import React, {useEffect} from "react";

import {CameraTreeItem} from "./CameraTreeItem";
import {NoCamerasPlaceholder} from "./NoCamerasPlaceholder";
import {CameraHeaderActions} from "./CameraHeaderActions";
import {
    Camera,
    detectCameras,
    selectCameras,
    selectConnectedCameras,
    selectIsLoading,
    selectIsPaused,
    useAppDispatch,
    useAppSelector
} from "@/store";
import {useServer} from "@/services/server/ServerContextProvider";
import {useTranslation} from 'react-i18next';


export const CameraConfigTreeView: React.FC = () => {
    const dispatch = useAppDispatch();
    const {t} = useTranslation();
    const {isConnected} = useServer();

    const cameras = useAppSelector(selectCameras);
    const isLoading = useAppSelector(selectIsLoading);
    const connectedCameras = useAppSelector(selectConnectedCameras);
    const isPaused = useAppSelector(selectIsPaused);

    useEffect(() => {
        if (isConnected && cameras.length === 0) {
            dispatch(detectCameras({filterVirtual: true}));
        }
    }, [isConnected, cameras.length, dispatch]);

    return (
        <div className="camera-config-sidebar-panel flex flex-col flex-1 bg-middark br-2 p-1 min-h-0">
            {/* Header */}
            <div className="camera-group-header flex flex-row flex-wrap items-center gap-1 p-1 pos-rel z-2">
                <p className="flex flex-row text md text-gray">{cameras.length} {t('cameras')}</p>
                {connectedCameras.length > 0 && (
                    <span className="text md" style={{color: 'var(--color-success)'}}>
                        {connectedCameras.length} Streaming
                    </span>
                )}
                <div className="flex-1" />
                <div className="button-group flex items-center gap-1 pos-rel">
                    <CameraHeaderActions isLoading={isLoading} isPaused={isPaused} />
                </div>
            </div>

            {/* Camera list */}
            <div className="camera-list-container flex flex-col overflow-y z-1 pos-rel">
                {cameras.length === 0 ? (
                    <NoCamerasPlaceholder />
                ) : (
                    cameras
                        .slice()
                        .sort((a: Camera, b: Camera) => a.index - b.index)
                        .map((camera: Camera) => (
                            <CameraTreeItem key={camera.id} camera={camera} />
                        ))
                )}
            </div>
        </div>
    );
};
