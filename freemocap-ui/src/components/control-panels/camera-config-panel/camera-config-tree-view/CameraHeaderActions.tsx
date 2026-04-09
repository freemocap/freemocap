import React, {useState} from "react";
import {Box, CircularProgress, IconButton, Tooltip, useTheme} from "@mui/material";
import VideocamIcon from "@mui/icons-material/Videocam";
import VideocamOffIcon from "@mui/icons-material/VideocamOff";
import PauseIcon from "@mui/icons-material/Pause";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import YoutubeSearchedForIcon from "@mui/icons-material/YoutubeSearchedFor";
import DeleteSweepIcon from "@mui/icons-material/DeleteSweep";
import ArrowDownwardIcon from "@mui/icons-material/ArrowDownward";

import {useAppDispatch, useAppSelector} from "@/store";
import {selectSelectedCameras} from "@/store/slices/cameras/cameras-selectors";
import {
    camerasConnectOrUpdate,
    closeCameras,
    detectCameras,
    pauseUnpauseCameras,
} from "@/store/slices/cameras/cameras-thunks";
import {savedSettingsCleared} from "@/store/slices/cameras/cameras-slice";
import {useTranslation} from 'react-i18next';

interface CameraHeaderActionsProps {
    isLoading: boolean;
    isPaused: boolean;
    isConnected: boolean;
}

export const CameraHeaderActions: React.FC<CameraHeaderActionsProps> = ({
    isLoading,
    isPaused,
    isConnected,
}) => {
    const dispatch = useAppDispatch();
    const {t} = useTranslation();
    const theme = useTheme();
    const selectedCameras = useAppSelector(selectSelectedCameras);

    const [isActionInProgress, setIsActionInProgress] = useState(false);

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
        } catch (error) {
            console.error('Error pausing/unpausing cameras:', error);
        } finally {
            setIsActionInProgress(false);
        }
    };

    const handleClearSavedSettings = (e: React.MouseEvent): void => {
        e.stopPropagation();
        dispatch(savedSettingsCleared());
    };

    const busy = isLoading || isActionInProgress;

    return (
        <>
            {/* Connect/Apply Button - Keep pink/magenta color with border */}
            <Tooltip title={t("connectCameras")}>
                <span>
                    <IconButton
                        size="small"
                        onClick={handleConnectOrApply}
                        sx={{
                            color: "secondary.main",
                            padding: "4px",
                            border: `2px solid ${theme.palette.secondary.main}`,
                            borderRadius: '8px',
                            "&:hover": {
                                color: "secondary.light",
                                border: `2px solid ${theme.palette.secondary.light}`,
                                backgroundColor: 'rgba(255, 255, 255, 0.1)',
                            }
                        }}
                    >
                        <Box sx={{ position: 'relative', display: 'inline-flex', width: 28, height: 28 }}>
                            <VideocamIcon
                                sx={{
                                    color: 'secondary.main',
                                    fontSize: 24,
                                }}
                            />
                            {!isConnected && (
                                <ArrowDownwardIcon
                                    sx={{
                                        position: 'absolute',
                                        top: -6,
                                        left: '50%',
                                        transform: 'translateX(-50%)',
                                        fontSize: 14,
                                        color: theme.palette.secondary.light,
                                        fontWeight: 'bold',
                                        strokeWidth: 3,
                                        stroke: theme.palette.secondary.dark,
                                        filter: 'drop-shadow(0 0 2px rgba(0,0,0,0.8))',
                                    }}
                                />
                            )}
                        </Box>
                    </IconButton>
                </span>
            </Tooltip>

            {/* Pause/Play Button */}
            <Tooltip title={isPaused ? t("resumeStreaming") : t("pauseStreaming")}>
                <span>
                    <IconButton
                        size="small"
                        onClick={handlePauseUnpause}
                        disabled={!isConnected}
                        sx={{
                            color: "inherit",
                            padding: "4px",
                            opacity: isConnected ? 1 : 0.4,
                        }}
                    >
                        {isPaused ? <PlayArrowIcon sx={{ fontSize: 24 }} /> : <PauseIcon sx={{ fontSize: 24 }} />}
                    </IconButton>
                </span>
            </Tooltip>

            {/* Close Button */}
            <Tooltip title={t("closeAllCameras")}>
                <span>
                    <IconButton
                        size="small"
                        onClick={handleCloseCameras}
                        disabled={!isConnected}
                        sx={{
                            color: "inherit",
                            padding: "4px",
                            opacity: isConnected ? 1 : 0.4,
                        }}
                    >
                        <VideocamOffIcon sx={{ fontSize: 24 }} />
                    </IconButton>
                </span>
            </Tooltip>

            {/* Refresh/Detect Button */}
            <Tooltip title={t("detectCameras")}>
                <span>
                    <IconButton
                        size="small"
                        onClick={handleRefreshCameras}
                        sx={{ color: "inherit", padding: "4px" }}
                    >
                        {busy ? (
                            <CircularProgress size={20} sx={{ color: "inherit" }} />
                        ) : (
                            <YoutubeSearchedForIcon sx={{ fontSize: 24 }} />
                        )}
                    </IconButton>
                </span>
            </Tooltip>

            {/* Clear Saved Settings Button */}
            <Tooltip title={t("clearCameraSettings")}>
                <span>
                    <IconButton
                        size="small"
                        onClick={handleClearSavedSettings}
                        sx={{ color: "inherit", padding: "4px" }}
                    >
                        <DeleteSweepIcon sx={{ fontSize: 24 }} />
                    </IconButton>
                </span>
            </Tooltip>
        </>
    );
};
