import React from "react";
import {Box, CircularProgress, IconButton, Stack, Tooltip, Typography, useTheme} from "@mui/material";
import VideocamIcon from "@mui/icons-material/Videocam";
import VideocamOffIcon from "@mui/icons-material/VideocamOff";
import PauseIcon from "@mui/icons-material/Pause";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import YoutubeSearchedForIcon from "@mui/icons-material/YoutubeSearchedFor";
import SystemUpdateAltIcon from "@mui/icons-material/SystemUpdateAlt";

import {useAppDispatch, useAppSelector} from "@/store";
import {selectSelectedCameras} from "@/store/slices/cameras/cameras-selectors";
import {
    closeCameras,
    camerasConnectOrUpdate,
    detectCameras,
    pauseUnpauseCameras,
} from "@/store/slices/cameras/cameras-thunks";

interface CameraConfigTreeViewHeaderProps {
    cameraCount: number;
    isLoading: boolean;
    isPaused: boolean;
    onPauseToggle: () => void;
    hasSelectedCameras: boolean;
}

export const CameraConfigTreeViewHeader: React.FC<CameraConfigTreeViewHeaderProps> = ({
    cameraCount,
    isLoading,
    isPaused,
    onPauseToggle,
}) => {
    const theme = useTheme();
    const dispatch = useAppDispatch();
    const selectedCameras = useAppSelector(selectSelectedCameras);
    const hasSelected = selectedCameras.length > 0;

    const [isActionInProgress, setIsActionInProgress] = React.useState(false);

    const handleRefreshCameras = async (e: React.MouseEvent): Promise<void> => {
        e.stopPropagation();

        setIsActionInProgress(true);
        try {
            await dispatch(detectCameras({filterVirtual: true})).unwrap();
        } catch (error) {
            console.error('Error detecting cameras:', error);
        } finally {
            setIsActionInProgress(false);
        }
    };

    const handleConnectOrApply = async (e: React.MouseEvent): Promise<void> => {
        e.stopPropagation();

        setIsActionInProgress(true);
        try {
            await dispatch(camerasConnectOrUpdate()).unwrap();
        } catch (error) {
            console.error('Error with camera operation:', error);
        } finally {
            setIsActionInProgress(false);
        }
    };

    const handleCloseCameras = async (e: React.MouseEvent): Promise<void> => {
        e.stopPropagation();

        setIsActionInProgress(true);
        try {
            await dispatch(closeCameras()).unwrap();
            console.log('Closed all cameras');
        } catch (error) {
            console.error('Error closing cameras:', error);
        } finally {
            setIsActionInProgress(false);
        }
    };

    const handlePauseUnpause = async (e: React.MouseEvent): Promise<void> => {
        e.stopPropagation();

        setIsActionInProgress(true);
        try {
            await dispatch(pauseUnpauseCameras()).unwrap();
            onPauseToggle();
        } catch (error) {
            console.error('Error pausing/unpausing cameras:', error);
        } finally {
            setIsActionInProgress(false);
        }
    };

    const handleHeaderClick = (e: React.MouseEvent): void => {
        e.stopPropagation();
    };

    return (
        <Box
            onClick={handleHeaderClick}
            sx={{
                display: "flex",
                alignItems: "center",
                py: 1,
                backgroundColor: theme.palette.primary.main,
                color: theme.palette.primary.contrastText,
            }}
        >
            <VideocamIcon sx={{ml: 2, mr: 1}} />
            <Typography variant="h6" sx={{flexGrow: 1}}>
                Cameras ({cameraCount})
            </Typography>

            <Stack direction="row" spacing={1} sx={{mr: 2}}>
                {/* Connect/Apply Button - Always visible, changes icon and behavior */}
                <Tooltip title={"Connect to selected cameras or update connected cameras"}>
                    <span>
                        <IconButton
                            size="small"
                            onClick={handleConnectOrApply}
                            sx={{color: "inherit"}}
                        >

                                <VideocamIcon
                                    sx={{
                                        color: theme.palette.secondary.main,
                                        border: `2px solid ${theme.palette.secondary.main}`,
                                        borderRadius: '4px',
                                        padding: '2px',
                                        scale: '1.6'
                                    }}
                                />
                            )
                        </IconButton>
                    </span>
                </Tooltip>

                {/* Pause/Play Button - Always visible, disabled when not connected */}
                <Tooltip title={isPaused ? "Resume streaming" : "Pause streaming"}>
                    <span>
                        <IconButton
                            size="small"
                            onClick={handlePauseUnpause}
                            sx={{
                                color: "inherit",
                            }}
                        >
                            {isPaused ? <PlayArrowIcon /> : <PauseIcon />}
                        </IconButton>
                    </span>
                </Tooltip>

                {/* Close Button - Always visible, disabled when not connected */}
                <Tooltip title={"Close all cameras"}>
                    <span>
                        <IconButton
                            size="small"
                            onClick={handleCloseCameras}
                            sx={{
                                color: "inherit",
                            }}
                        >
                            <VideocamOffIcon />
                        </IconButton>
                    </span>
                </Tooltip>

                {/* Refresh/Detect Button - Always visible */}
                <Tooltip title="Detect available cameras">
                    <span>
                        <IconButton
                            size="small"
                            onClick={handleRefreshCameras}
                            sx={{color: "inherit"}}
                        >
                            {isLoading || isActionInProgress ? (
                                <CircularProgress size={20} sx={{color: "inherit"}} />
                            ) : (
                                <YoutubeSearchedForIcon />
                            )}
                        </IconButton>
                    </span>
                </Tooltip>
            </Stack>
        </Box>
    );
};
