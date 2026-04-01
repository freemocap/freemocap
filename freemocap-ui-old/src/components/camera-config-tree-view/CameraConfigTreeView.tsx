import React, {useEffect, useState} from "react";
import {Box, Chip, Typography, useTheme} from "@mui/material";
import {SimpleTreeView} from "@mui/x-tree-view/SimpleTreeView";
import ExpandMore from "@mui/icons-material/ExpandMore";
import ChevronRight from "@mui/icons-material/ChevronRight";
import VideocamIcon from "@mui/icons-material/Videocam";
import VideoCameraFrontIcon from "@mui/icons-material/VideoCameraFront";

import {CollapsibleSidebarSection} from "@/components/common/CollapsibleSidebarSection";
import {CameraHeaderActions} from "./CameraHeaderActions";
import {CameraGroupTreeItem} from "./CameraGroupTreeItem";
import {
    Camera,
    detectCameras,
    selectCameras,
    selectConnectedCameras,
    selectIsLoading, selectSelectedCameras,
    useAppDispatch,
    useAppSelector,
} from "@/store";
import {useServer} from "@/hooks/useServer";

export const CameraConfigTreeView: React.FC = () => {
    const theme = useTheme();
    const dispatch = useAppDispatch();
    const {isConnected} = useServer();

    const cameras = useAppSelector(selectCameras);
    const isLoading = useAppSelector(selectIsLoading);
    const connectedCameras = useAppSelector(selectConnectedCameras);
    const selectedCameras = useAppSelector(selectSelectedCameras);

    // Expand state for the inner camera group tree
    const [expandedItems, setExpandedItems] = useState<string[]>([
        "cameras-connected",
        "cameras-available",
    ]);
    const [isPaused, setIsPaused] = useState<boolean>(false);

    const availableCameras = cameras.filter(
        (cam: Camera) => cam.connectionStatus !== "connected"
    );
    const isConnectedToCameras = connectedCameras.length > 0;

    // Detect cameras on initial connection
    useEffect(() => {
        if (isConnected && cameras.length === 0) {
            dispatch(detectCameras({filterVirtual: true}));
        }
    }, [isConnected, cameras.length, dispatch]);

    const handleExpandedItemsChange = (
        _event: React.SyntheticEvent,
        itemIds: string[]
    ): void => {
        setExpandedItems(itemIds);
    };

    const handlePauseToggle = (): void => {
        setIsPaused(!isPaused);
    };

    // Build summary content: camera count chips
    const summaryChips = (
        <Box sx={{display: "flex", gap: 0.5, alignItems: "center"}}>
            {connectedCameras.length > 0 && (
                <Chip
                    label={`${connectedCameras.length} connected`}
                    size="small"
                    sx={{
                        height: 18,
                        fontSize: 10,
                        fontWeight: 600,
                        backgroundColor: theme.palette.success.main,
                        color: theme.palette.getContrastText(theme.palette.success.main),
                    }}
                />
            )}
            {cameras.length > 0 && connectedCameras.length === 0 && (
                <Chip
                    label={`${cameras.length} detected`}
                    size="small"
                    variant="outlined"
                    sx={{
                        height: 18,
                        fontSize: 10,
                        borderColor: "rgba(255,255,255,0.4)",
                        color: "inherit",
                    }}
                />
            )}
        </Box>
    );

    return (
        <CollapsibleSidebarSection
            icon={<VideocamIcon sx={{color: "inherit"}} />}
            title="Cameras"
            summaryContent={summaryChips}
            primaryControl={
                <CameraHeaderActions
                    isLoading={isLoading}
                    isPaused={isPaused}
                    onPauseToggle={handlePauseToggle}
                />
            }
            defaultExpanded={true}
        >
            {cameras.length === 0 ? (
                <Box sx={{p: 3, textAlign: "center"}}>
                    <Typography variant="body2" color="text.secondary">
                        No cameras detected
                    </Typography>
                    <Typography
                        variant="caption"
                        color="text.disabled"
                        sx={{mt: 1, display: "block"}}
                    >
                        Click refresh to scan for available cameras
                    </Typography>
                </Box>
            ) : (
                <SimpleTreeView
                    expandedItems={expandedItems}
                    onExpandedItemsChange={handleExpandedItemsChange}
                    slots={{
                        collapseIcon: ExpandMore,
                        expandIcon: ChevronRight,
                    }}
                >
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
                </SimpleTreeView>
            )}
        </CollapsibleSidebarSection>
    );
};
