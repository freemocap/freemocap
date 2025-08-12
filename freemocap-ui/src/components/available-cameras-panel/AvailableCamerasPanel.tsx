// skellycam-ui/src/components/available-cameras-panel/AvailableCamerasView.tsx
import {Accordion, AccordionDetails, Box, List, Paper, Stack, Typography, useTheme,} from "@mui/material";
import * as React from "react";
import {useEffect, useState} from "react";
import AccordionSummary from "@mui/material/AccordionSummary";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import VideocamIcon from "@mui/icons-material/Videocam";
import {CameraConfigPanel} from "@/components/available-cameras-panel/CameraConfigPanel";
import {CameraListItem} from "@/components/available-cameras-panel/CameraListItem";
import {RefreshDetectedCamerasButton} from "@/components/available-cameras-panel/RefreshDetectedCameras";
import {useAppDispatch, useAppSelector} from "@/store/AppStateStore";
import {ConnectToCamerasButton} from "@/components/available-cameras-panel/ConnectToCamerasButton";
import {selectAllCameras, toggleCameraSelection, updateCameraConfig,} from "@/store/slices/cameras-slices/camerasSlice";
import {connectToCameras} from "@/store/thunks/connect-to-cameras-thunk";
import {CloseCamerasButton} from "@/components/available-cameras-panel/CloseCamerasButton";
import {CameraConfig, CameraDevice} from "@/store/slices/cameras-slices/camera-types";
import {ApplyCameraConfigsButton} from "@/components/available-cameras-panel/ApplyCameraConfigsButton";
import {PauseUnpauseButton} from "../PauseUnpauseButton";
// import { detectCameraDevices } from "@/store/thunks/detect-cameras-client-thunks";
import { detectCameraDevices } from "@/store/thunks/detect-cameras-thunks/detect-cameras-server-thunk";

export const AvailableCamerasPanel = () => {
    const theme = useTheme();
    const dispatch = useAppDispatch();

    // Get data from the unified slice
    const camerasRecord = useAppSelector(selectAllCameras);
    const isLoading = useAppSelector((state) => state.cameras.isLoading);
    const [expandedConfigs, setExpandedConfigs] = useState<Set<string>>(new Set());
    const [camerasArray, setCamerasArray] = useState<CameraDevice[]>([]);

    useEffect(() => {
        // Whenever the camerasRecord changes, update the camerasArray
        if (!camerasRecord) {
            setCamerasArray([]);
            return;
        }

        // Convert cameras record to array for easier rendering
        const newCamerasArray = Object.values(camerasRecord).sort((a, b) =>
            a.config.camera_index - b.config.camera_index
        );

        setCamerasArray(newCamerasArray);
    }, [camerasRecord]);




    // Handle expanding/collapsing camera config panels
    const toggleConfig = (cameraId: string) => {
        setExpandedConfigs((prev) => {
            const newSet = new Set(prev);
            if (newSet.has(cameraId)) {
                newSet.delete(cameraId);
            } else {
                newSet.add(cameraId);
            }
            return newSet;
        });
    };

    // Initial camera detection
    useEffect(() => {
        if (camerasArray.length > 0) {
            // If cameras are already detected, we don't need to detect again
            return;
        }
        dispatch(detectCameraDevices());
    }, [dispatch]);

    // Handle connection to selected cameras
    const handleConnectCameras = () => {
        dispatch(connectToCameras());
    };

    const handleConfigChange = (cameraId: string, newConfig: CameraConfig) => {
        // Update the Redux store
        dispatch(
            updateCameraConfig({
                cameraId,
                config: newConfig,
            })
        );
    };

    return (
        <Accordion
            defaultExpanded
            sx={{
                borderRadius: 2,
                "&:before": {display: "none"},
                boxShadow: theme.shadows[3],
                justifyContent: "left",
            }}
        >
            <Box
                sx={{
                    display: "flex",
                    alignItems: "center",
                    backgroundColor: theme.palette.primary.main,
                    borderTopLeftRadius: 8,
                    borderBottomLeftRadius: 8,
                }}
            >
                <AccordionSummary
                    expandIcon={
                        <ExpandMoreIcon
                            sx={{color: theme.palette.primary.contrastText}}
                        />
                    }
                    sx={{
                        flex: 1,
                        color: theme.palette.primary.contrastText,
                        "&:hover": {
                            backgroundColor: theme.palette.primary.light,
                        },
                    }}
                >
                    <Stack direction="row" alignItems="center" spacing={1}>
                        <VideocamIcon/>
                        <Typography variant="subtitle1" fontWeight="medium">
                            Cameras
                        </Typography>
                    </Stack>
                </AccordionSummary>
                <Box sx={{pr: 2}}>
                    <PauseUnpauseButton/>
                </Box>
                <Box sx={{pr: 2}}>
                    <ConnectToCamerasButton onClick={handleConnectCameras}/>
                </Box>
                <Box sx={{pr: 2}}>
                    <        ApplyCameraConfigsButton/>
                </Box>
                <Box sx={{pr: 2}}>
                    <RefreshDetectedCamerasButton isLoading={isLoading}/>
                </Box>
                <Box sx={{pr: 2}}>
                    <CloseCamerasButton/>
                </Box>
            </Box>

            <AccordionDetails sx={{bgcolor: "background.default"}}>
                <Paper
                    elevation={0}
                    sx={{
                        borderRadius: 2,
                        overflow: "hidden",
                    }}
                >
                    <List dense disablePadding>
                        {camerasArray.map((camera, index) => (
                            <React.Fragment key={camera.cameraId}>
                                <CameraListItem
                                    camera={camera}
                                    isLast={index === camerasArray.length - 1}
                                    isConfigExpanded={expandedConfigs.has(camera.cameraId)}
                                    onToggleSelect={() =>
                                        dispatch(toggleCameraSelection(camera.cameraId))
                                    }
                                    onToggleConfig={() => toggleConfig(camera.cameraId)}
                                />
                                {camera.selected && (
                                    <CameraConfigPanel
                                        config={camera.config}
                                        onConfigChange={(newConfig) => {
                                            handleConfigChange(camera.cameraId, newConfig);
                                        }}
                                        isExpanded={expandedConfigs.has(camera.cameraId)}
                                    />
                                )}
                            </React.Fragment>
                        ))}
                    </List>

                    {camerasArray.length === 0 && (
                        <Box
                            sx={{
                                p: 3,
                                textAlign: "center",
                                bgcolor: "background.paper",
                                borderRadius: 1,
                            }}
                        >
                            <Typography variant="body1" color="text.secondary">
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
                    )}
                </Paper>
            </AccordionDetails>
        </Accordion>
    );
};
