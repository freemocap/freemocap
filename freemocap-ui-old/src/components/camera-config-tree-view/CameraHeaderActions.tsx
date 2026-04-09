import React, {useState} from "react";
import {CircularProgress, IconButton, Stack, Tooltip} from "@mui/material";
import VideocamIcon from "@mui/icons-material/Videocam";
import VideocamOffIcon from "@mui/icons-material/VideocamOff";
import PauseIcon from "@mui/icons-material/Pause";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import YoutubeSearchedForIcon from "@mui/icons-material/YoutubeSearchedFor";
import {camerasConnectOrUpdate, closeCameras, pauseUnpauseCameras, useAppDispatch, useAppSelector,} from "@/store";
import {selectSelectedCameras} from "@/store/slices/cameras/cameras-selectors";
import {detectCameras} from "@/store/slices/cameras/cameras-thunks";

interface CameraHeaderActionsProps {
    isLoading: boolean;
    isPaused: boolean;
    onPauseToggle: () => void;
}

export const CameraHeaderActions: React.FC<CameraHeaderActionsProps> = ({
    isLoading,
    isPaused,
    onPauseToggle,
}) => {
    const dispatch = useAppDispatch();
    const selectedCameras = useAppSelector(selectSelectedCameras);
    const hasSelected = selectedCameras.length > 0;
    const [isActionInProgress, setIsActionInProgress] = useState(false);

    const handleRefreshCameras = async (e: React.MouseEvent): Promise<void> => {
        e.stopPropagation();
        setIsActionInProgress(true);
        try {
            await dispatch(detectCameras({filterVirtual: true})).unwrap();
        } catch (error) {
            console.error("Error detecting cameras:", error);
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
            console.error("Error with camera operation:", error);
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
            console.error("Error closing cameras:", error);
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
            console.error("Error pausing/unpausing cameras:", error);
        } finally {
            setIsActionInProgress(false);
        }
    };

    const iconButtonSx = {
        color: "inherit",
        "&:hover": {
            backgroundColor: "rgba(255,255,255,0.1)",
        },
    };

    return (
        <Stack direction="row" spacing={0.5}>
            {/* Connect/Apply */}
            <Tooltip title="Connect selected cameras or apply config updates">
                <span>
                    <IconButton
                        size="small"
                        onClick={handleConnectOrApply}
                        disabled={!hasSelected}
                        sx={iconButtonSx}
                    >
                        <VideocamIcon fontSize="small" />
                    </IconButton>
                </span>
            </Tooltip>

            {/* Pause/Resume */}
            <Tooltip title={isPaused ? "Resume streaming" : "Pause streaming"}>
                <span>
                    <IconButton
                        size="small"
                        onClick={handlePauseUnpause}
                        sx={iconButtonSx}
                    >
                        {isPaused ? (
                            <PlayArrowIcon fontSize="small" />
                        ) : (
                            <PauseIcon fontSize="small" />
                        )}
                    </IconButton>
                </span>
            </Tooltip>

            {/* Close All */}
            <Tooltip title="Close all cameras">
                <span>
                    <IconButton
                        size="small"
                        onClick={handleCloseCameras}
                        sx={iconButtonSx}
                    >
                        <VideocamOffIcon fontSize="small" />
                    </IconButton>
                </span>
            </Tooltip>

            {/* Detect/Refresh */}
            <Tooltip title="Detect available cameras">
                <span>
                    <IconButton
                        size="small"
                        onClick={handleRefreshCameras}
                        sx={iconButtonSx}
                    >
                        {isLoading || isActionInProgress ? (
                            <CircularProgress size={18} sx={{color: "inherit"}} />
                        ) : (
                            <YoutubeSearchedForIcon fontSize="small" />
                        )}
                    </IconButton>
                </span>
            </Tooltip>
        </Stack>
    );
};
