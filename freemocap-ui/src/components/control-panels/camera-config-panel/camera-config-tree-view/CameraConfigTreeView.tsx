import React, {useEffect, useState} from "react";
import {Box, useTheme,} from "@mui/material";
import {SimpleTreeView} from "@mui/x-tree-view/SimpleTreeView";
import ExpandMore from "@mui/icons-material/ExpandMore";
import ChevronRight from "@mui/icons-material/ChevronRight";
import VideoCameraFrontIcon from '@mui/icons-material/VideoCameraFront';

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
import {useServer} from "@/services/server/ServerContextProvider";
import {useTranslation} from 'react-i18next';
import {CollapsibleSidebarSection} from "../../../common/CollapsibleSidebarSection";


export const CameraConfigTreeView: React.FC = () => {
    const theme = useTheme();
    const dispatch = useAppDispatch();
    const {t} = useTranslation();
    const {isConnected} = useServer();

    // Redux state
    const cameras = useAppSelector(selectCameras);
    const isLoading = useAppSelector(selectIsLoading);
    const connectedCameras = useAppSelector(selectConnectedCameras);

    // Local state
    const [expandedItems, setExpandedItems] = useState<string[]>([
        "cameras-root",
        "cameras-connected",
        "cameras-available"
    ]);

    // Pause state from Redux (shared with keyboard shortcut)
    const isPaused = useAppSelector(selectIsPaused);

    // Group cameras by status
    const availableCameras = cameras.filter((cam: Camera) => cam.connectionStatus !== "connected");
    const isConnectedToCameras = connectedCameras.length > 0;

    // Initial camera detection
    useEffect(() => {
        if (isConnected && cameras.length === 0) {
            dispatch(detectCameras({filterVirtual: true}));
        }
    }, [isConnected, cameras.length, dispatch]);

    const handleExpandedItemsChange = (
        event: React.SyntheticEvent,
        itemIds: string[]
    ): void => {
        setExpandedItems(itemIds);
    };


    return (
        <CollapsibleSidebarSection
            icon={<VideoCameraFrontIcon sx={{color: "inherit"}}/>}
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
            <Box
                sx={{
                    color: "text.primary",
                    backgroundColor: theme.palette.background.paper,
                    borderRadius: 1,
                    mx: 1,
                    my: 0.5,
                }}
            >
                <SimpleTreeView
                    expandedItems={expandedItems}
                    onExpandedItemsChange={handleExpandedItemsChange}
                    slots={{
                        collapseIcon: ExpandMore,
                        expandIcon: ChevronRight,
                    }}
                    sx={{
                        flexGrow: 1,
                        '& .MuiTreeItem-content': {
                            padding: '2px 4px',
                            margin: '1px 0',
                        },
                        '& .MuiTreeItem-label': {
                            fontSize: 13,
                            padding: '1px 0',
                        },
                    }}
                >
                    {cameras.length === 0 ? (
                        <NoCamerasPlaceholder/>
                    ) : (
                        <>
                            {/* Connected Cameras Group */}
                            {isConnectedToCameras && connectedCameras.length > 0 && (
                                <CameraGroupTreeItem
                                    groupId="cameras-connected"
                                    title={t("connectedCameras")}
                                    cameras={connectedCameras}
                                    icon={<VideoCameraFrontIcon color="success"/>}
                                    expandedItems={expandedItems}
                                />
                            )}

                            {/* Available Cameras Group */}
                            {availableCameras.length > 0 && (
                                <CameraGroupTreeItem
                                    groupId="cameras-available"
                                    title={t("availableCameras")}
                                    cameras={availableCameras}
                                    icon={<VideoCameraFrontIcon color="info"/>}
                                    expandedItems={expandedItems}
                                />
                            )}
                        </>
                    )}
                </SimpleTreeView>
            </Box>
        </CollapsibleSidebarSection>
    );
};
