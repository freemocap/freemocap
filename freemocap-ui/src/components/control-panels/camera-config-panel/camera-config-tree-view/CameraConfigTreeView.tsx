import React, {useEffect} from "react";

import {CameraGroupTreeItem} from "./CameraGroupTreeItem";
import {NoCamerasPlaceholder} from "./NoCamerasPlaceholder";
import {CameraSummary} from "./CameraSummary";
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
import {recommendExposureForAll} from "@/store/slices/cameras/cameras-slice";
import {useServer} from "@/services/server/ServerContextProvider";
import {useTranslation} from 'react-i18next';
import {CollapsibleSidebarSection} from "../../../common/CollapsibleSidebarSection";
import IconButton from "@/components/ui-components/IconButton";


export const CameraConfigTreeView: React.FC = () => {
    const dispatch = useAppDispatch();
    const {t} = useTranslation();
    const {isConnected} = useServer();

    const cameras = useAppSelector(selectCameras);
    const isLoading = useAppSelector(selectIsLoading);
    const connectedCameras = useAppSelector(selectConnectedCameras);

    const isPaused = useAppSelector(selectIsPaused);

    const availableCameras = cameras.filter((cam: Camera) => cam.connectionStatus !== "connected");
    const isConnectedToCameras = connectedCameras.length > 0;

    useEffect(() => {
        if (isConnected && cameras.length === 0) {
            dispatch(detectCameras({filterVirtual: true}));
        }
    }, [isConnected, cameras.length, dispatch]);

    return (
        <CollapsibleSidebarSection
            icon={<span className="icon stream-icon icon-size-20" style={{color: "inherit"}} />}
            title={t('cameras')}
            summaryContent={
                <CameraSummary
                    cameraCount={cameras.length}
                    connectedCount={connectedCameras.length}
                />
            }
            secondaryControls={
                <CameraHeaderActions
                    isLoading={isLoading}
                    isPaused={isPaused}
                />
            }
            defaultExpanded={false}
        >
            <div className="br-1" style={{margin: '4px 8px'}}>
                {isConnectedToCameras && (
                    <div className="flex flex-row items-center gap-1 p-01" style={{paddingBottom: 4}}>
                        <IconButton
                            icon="scan-icon"
                            onClick={() => dispatch(recommendExposureForAll())}
                            title="Auto-recommend exposure for all cameras"
                            tooltip
                            tooltipText="Auto-recommend exposure for all cameras"
                            tooltipPosition="pos-right"
                        />
                        <p className="text sm text-gray">Auto-recommend exposure</p>
                    </div>
                )}
                {cameras.length === 0 ? (
                    <NoCamerasPlaceholder />
                ) : (
                    <>
                        {isConnectedToCameras && connectedCameras.length > 0 && (
                            <CameraGroupTreeItem
                                groupId="cameras-connected"
                                title={t("connectedCameras")}
                                cameras={connectedCameras}
                                icon={<span className="icon stream-icon icon-size-20" style={{color: 'var(--color-success)'}} />}
                            />
                        )}

                        {availableCameras.length > 0 && (
                            <CameraGroupTreeItem
                                groupId="cameras-available"
                                title={t("availableCameras")}
                                cameras={availableCameras}
                                icon={<span className="icon stream-icon icon-size-20" style={{color: 'var(--color-info)'}} />}
                            />
                        )}
                    </>
                )}
            </div>
        </CollapsibleSidebarSection>
    );
};
