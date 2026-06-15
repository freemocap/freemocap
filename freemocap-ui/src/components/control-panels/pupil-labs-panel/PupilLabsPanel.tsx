import React, { useCallback } from "react";
import {
    Alert,
    Box,
    Button,
    Chip,
    Stack,
    Typography,
} from "@mui/material";
import VisibilityIcon from "@mui/icons-material/Visibility";
import { CollapsibleSidebarSection } from "@/components/common/CollapsibleSidebarSection";
import { useAppDispatch, useAppSelector } from "@/store";
import {
    connectPupilLabs,
    disconnectPupilLabs,
    getPupilLabsStatus,
    pupilLabsErrorCleared,
    selectPupilLabs,
} from "@/store/slices/pupil-labs";

export const PupilLabsPanel: React.FC = () => {
    const dispatch = useAppDispatch();
    const { isConnected, isConnecting, isDisconnecting, isRecording, error } =
        useAppSelector(selectPupilLabs);

    const handleConnect = useCallback(() => {
        dispatch(connectPupilLabs());
    }, [dispatch]);

    const handleDisconnect = useCallback(() => {
        dispatch(disconnectPupilLabs());
    }, [dispatch]);

    const handleRefreshStatus = useCallback(() => {
        dispatch(getPupilLabsStatus());
    }, [dispatch]);

    const handleClearError = useCallback(() => {
        dispatch(pupilLabsErrorCleared());
    }, [dispatch]);

    const summaryContent = (
        <Chip
            size="small"
            label={isConnected ? (isRecording ? "Recording" : "Connected") : "Disconnected"}
            color={isConnected ? (isRecording ? "error" : "success") : "default"}
            variant="outlined"
        />
    );

    return (
        <CollapsibleSidebarSection
            icon={<VisibilityIcon />}
            title="Pupil Labs"
            summaryContent={summaryContent}
            defaultExpanded={false}
        >
            <Stack spacing={1.5}>
                <Typography variant="body2" color="text.secondary">
                    Connect to Pupil Capture to stream 3D eye tracking data
                    into the FreeMoCap viewport.
                </Typography>

                {isConnected ? (
                    <>
                        <Typography variant="caption" color="success.main">
                            Connected to Pupil Capture
                            {isRecording && " — Recording active"}
                        </Typography>
                        <Stack direction="row" spacing={1}>
                            <Button
                                size="small"
                                variant="outlined"
                                color="error"
                                onClick={handleDisconnect}
                                disabled={isDisconnecting}
                            >
                                {isDisconnecting ? "Disconnecting..." : "Disconnect"}
                            </Button>
                            <Button
                                size="small"
                                variant="outlined"
                                onClick={handleRefreshStatus}
                            >
                                Refresh Status
                            </Button>
                        </Stack>
                    </>
                ) : (
                    <Button
                        size="small"
                        variant="contained"
                        onClick={handleConnect}
                        disabled={isConnecting}
                    >
                        {isConnecting ? "Connecting..." : "Connect to Pupil Capture"}
                    </Button>
                )}

                {error && (
                    <Alert
                        severity="error"
                        onClose={handleClearError}
                        sx={{ fontSize: "0.75rem" }}
                    >
                        {error}
                    </Alert>
                )}

                {isConnected && (
                    <Box>
                        <Typography variant="caption" color="text.secondary">
                            Eye gaze data appears in the 3D viewport.
                            Toggle visibility with the "Eye gaze" checkbox
                            in the viewport overlay.
                        </Typography>
                    </Box>
                )}
            </Stack>
        </CollapsibleSidebarSection>
    );
};
