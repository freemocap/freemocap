import React, { useEffect, useState } from "react";
import {
    Box,
    Paper,
    Typography,
    useTheme,
} from "@mui/material";
import { SimpleTreeView } from "@mui/x-tree-view/SimpleTreeView";
import { TreeItem } from "@mui/x-tree-view/TreeItem";
import ExpandMore from "@mui/icons-material/ExpandMore";
import ChevronRight from "@mui/icons-material/ChevronRight";
import VideoCameraFrontIcon from '@mui/icons-material/VideoCameraFront';

import { CameraConfigTreeViewHeader } from "./CameraConfigTreeViewHeader";
import { CameraGroupTreeItem } from "./CameraGroupTreeItem";
import { NoCamerasPlaceholder } from "./NoCamerasPlaceholder";
import {
    useAppDispatch,
    useAppSelector,
    selectCameras,
    selectCalibrationIsLoading,
    selectConnectedCameras,
    selectSelectedCameras,
    detectCameras,
    Camera
} from "@/store";
import {useServer} from "@/services/server/ServerContextProvider";


export const CameraConfigTreeView: React.FC = () => {
    const theme = useTheme();
    const dispatch = useAppDispatch();
    const {isConnected} = useServer()
    // Redux state
    const cameras = useAppSelector(selectCameras);
    const isLoading = useAppSelector(selectCalibrationIsLoading);
    const connectedCameras = useAppSelector(selectConnectedCameras);
    const selectedCameras = useAppSelector(selectSelectedCameras);

    // Local state
    const [expandedItems, setExpandedItems] = useState<string[]>([
        "cameras-root",
        "cameras-connected",
        "cameras-available"
    ]);
    const [isPaused, setIsPaused] = useState<boolean>(false);

    // Group cameras by status
    const availableCameras = cameras.filter((cam: Camera) => cam.connectionStatus !== "connected");
    const isConnectedToCameras = connectedCameras.length > 0;
    const hasSelectedCameras = selectedCameras.length > 0;

    // Initial camera detection
    useEffect(() => {
        if (isConnected  && cameras.length === 0) {
            dispatch(detectCameras({ filterVirtual: true }));
        }
    }, [isConnected, cameras.length, dispatch]);

    const handleExpandedItemsChange = (
        event: React.SyntheticEvent,
        itemIds: string[]
    ): void => {
        setExpandedItems(itemIds);
    };

    const handlePauseToggle = (): void => {
        setIsPaused(!isPaused);
    };


    return (
        <Paper
            elevation={3}
            sx={{
                borderRadius: 2,
                overflow: "hidden",
            }}
        >
            <SimpleTreeView
                expandedItems={expandedItems}
                onExpandedItemsChange={handleExpandedItemsChange}
                slots={{
                    collapseIcon: ExpandMore,
                    expandIcon: ChevronRight,
                }}
            >
                <TreeItem
                    itemId="cameras-root"
                    label={
                        <CameraConfigTreeViewHeader
                            cameraCount={cameras.length}
                            isConnected={isConnectedToCameras}
                            isLoading={isLoading}
                            isPaused={isPaused}
                            onPauseToggle={handlePauseToggle}
                            hasSelectedCameras={hasSelectedCameras}
                        />
                    }
                >
                    {cameras.length === 0 ? (
                        <NoCamerasPlaceholder />
                    ) : (
                        <>
                            {/* Connected Cameras Group */}
                            {isConnectedToCameras && connectedCameras.length > 0 && (
                                <CameraGroupTreeItem
                                    groupId="cameras-connected"
                                    title="Connected Cameras"
                                    cameras={connectedCameras}
                                    icon={<VideoCameraFrontIcon color="success" />}
                                    expandedItems={expandedItems}
                                />
                            )}

                            {/* Available Cameras Group */}
                            {availableCameras.length > 0 && (
                                <CameraGroupTreeItem
                                    groupId="cameras-available"
                                    title="Available Cameras"
                                    cameras={availableCameras}
                                    icon={<VideoCameraFrontIcon color="info" />}
                                    expandedItems={expandedItems}
                                />
                            )}
                        </>
                    )}
                </TreeItem>
            </SimpleTreeView>
        </Paper>
    );
};
