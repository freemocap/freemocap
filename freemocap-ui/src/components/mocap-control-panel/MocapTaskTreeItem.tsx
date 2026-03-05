import React, {useCallback, useMemo, useState} from "react";
import {
    Alert,
    Box,
    Button,
    Chip,
    IconButton,
    InputAdornment,
    Stack,
    TextField,
    Tooltip,
    Typography,
    useTheme,
} from "@mui/material";
import DirectionsRunIcon from "@mui/icons-material/DirectionsRun";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import StopIcon from "@mui/icons-material/Stop";
import FolderOpenIcon from "@mui/icons-material/FolderOpen";
import ClearIcon from "@mui/icons-material/Clear";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import InfoIcon from "@mui/icons-material/Info";
import CloseIcon from "@mui/icons-material/Close";
import FiberManualRecordIcon from "@mui/icons-material/FiberManualRecord";
import {CollapsibleSidebarSection} from "@/components/common/CollapsibleSidebarSection";
import {useMocap} from "@/hooks/useMocap";
import {useElectronIPC} from "@/services";
import {MediapipeConfigPanel} from "@/components/mocap-control-panel/MediapipeConfigPanel";
import {SkeletonFilterConfigPanel} from "@/components/mocap-control-panel/SkeletonFilterConfigPanel";

export const MocapTaskTreeItem: React.FC = () => {
    const theme = useTheme();
    const [localError, setLocalError] = useState<string | null>(null);
    const {api, isElectron} = useElectronIPC();

    const {
        error,
        isLoading,
        isRecording,
        recordingProgress,
        canStartRecording,
        canProcessMocapRecording,
        mocapRecordingPath,
        directoryInfo,
        isUsingManualPath,
        dispatchStopMocapRecording,
        dispatchStartMocapRecording,
        setManualRecordingPath,
        clearManualRecordingPath,
        dispatchProcessMocapRecording,
        clearError,
    } = useMocap();

    const handleClearError = useCallback((): void => {
        clearError();
        setLocalError(null);
    }, [clearError]);

    const handleSelectDirectory = async (): Promise<void> => {
        if (!isElectron || !api) {
            console.warn("Electron API not available");
            return;
        }
        try {
            const result: string | null = await api.fileSystem.selectDirectory.mutate();
            if (result) {
                await setManualRecordingPath(result);
            }
        } catch (err) {
            console.error("Failed to select directory:", err);
            setLocalError("Failed to select directory");
        }
    };

    const handlePathInputChange = async (
        e: React.ChangeEvent<HTMLInputElement>
    ): Promise<void> => {
        const newPath: string = e.target.value;
        if (newPath.includes("~") && isElectron && api) {
            try {
                const home: string = await api.fileSystem.getHomeDirectory.query();
                const expanded: string = newPath.replace(
                    /^~([/\\])?/,
                    home ? `${home}$1` : ""
                );
                await setManualRecordingPath(expanded);
            } catch (err) {
                console.error("Failed to expand home directory:", err);
                await setManualRecordingPath(newPath);
            }
        } else {
            await setManualRecordingPath(newPath);
        }
    };

    const handleClearManualPath = useCallback((): void => {
        clearManualRecordingPath();
    }, [clearManualRecordingPath]);

    const displayError = error || localError || directoryInfo?.errorMessage;

    const pathHelperText = useMemo(() => {
        if (isUsingManualPath) return "Using custom path";
        return "Using default recording directory";
    }, [isUsingManualPath]);

    // Derive status for collapsed summary
    const statusLabel = isRecording
        ? `Recording ${recordingProgress.toFixed(0)}%`
        : isLoading
            ? "Processing..."
            : "Idle";

    const statusColor = isRecording
        ? theme.palette.error.main
        : isLoading
            ? theme.palette.warning.main
            : theme.palette.grey[600];

    // Primary control: compact start/stop recording toggle in the header
    const headerRecordButton = isRecording ? (
        <Tooltip title="Stop mocap recording">
            <IconButton
                size="small"
                onClick={(e: React.MouseEvent) => {
                    e.stopPropagation();
                    dispatchStopMocapRecording();
                }}
                disabled={isLoading}
                sx={{
                    color: theme.palette.error.light,
                    border: `1.5px solid ${theme.palette.error.light}`,
                    borderRadius: 1,
                    p: 0.5,
                    "&:hover": {backgroundColor: "rgba(244,67,54,0.15)"},
                }}
            >
                <StopIcon fontSize="small" />
            </IconButton>
        </Tooltip>
    ) : (
        <Tooltip title={canStartRecording ? "Start mocap recording" : "Cannot record yet"}>
            <span>
                <IconButton
                    size="small"
                    onClick={(e: React.MouseEvent) => {
                        e.stopPropagation();
                        dispatchStartMocapRecording();
                    }}
                    disabled={!canStartRecording || isLoading}
                    sx={{
                        color: "inherit",
                        border: "1.5px solid rgba(255,255,255,0.25)",
                        borderRadius: 1,
                        p: 0.5,
                        "&:hover": {backgroundColor: "rgba(255,255,255,0.1)"},
                        "&.Mui-disabled": {
                            color: "rgba(255,255,255,0.3)",
                            borderColor: "rgba(255,255,255,0.1)",
                        },
                    }}
                >
                    <FiberManualRecordIcon fontSize="small" />
                </IconButton>
            </span>
        </Tooltip>
    );

    return (
        <CollapsibleSidebarSection
            icon={<DirectionsRunIcon sx={{color: "inherit"}} />}
            title="Motion Capture"
            summaryContent={
                <Chip
                    label={statusLabel}
                    size="small"
                    sx={{
                        height: 20,
                        fontSize: 11,
                        fontWeight: 600,
                        backgroundColor: statusColor,
                        color: theme.palette.getContrastText(statusColor),
                    }}
                />
            }
            primaryControl={headerRecordButton}
            defaultExpanded={false}
        >
            <Box sx={{p: 2, bgcolor: "background.paper"}}>
                <Stack spacing={2}>
                    {/* Error Display */}
                    {displayError && (
                        <Alert severity="error" onClose={handleClearError}>
                            {displayError}
                        </Alert>
                    )}

                    {/* Recording Controls */}
                    <Stack direction="row" spacing={2}>
                        <Button
                            variant="contained"
                            color="primary"
                            startIcon={<PlayArrowIcon />}
                            onClick={dispatchStartMocapRecording}
                            disabled={!canStartRecording || isLoading}
                            fullWidth
                        >
                            Start Mocap Recording
                        </Button>
                        {isRecording && (
                            <Button
                                variant="contained"
                                color="error"
                                startIcon={<StopIcon />}
                                onClick={dispatchStopMocapRecording}
                                disabled={isLoading}
                                fullWidth
                            >
                                Stop Recording
                            </Button>
                        )}
                    </Stack>

                    {/* Recording Path Input */}
                    <TextField
                        label="Mocap Recording Path"
                        value={mocapRecordingPath}
                        onChange={handlePathInputChange}
                        fullWidth
                        size="small"
                        helperText={pathHelperText}
                        InputProps={{
                            endAdornment: (
                                <InputAdornment position="end">
                                    {isUsingManualPath && (
                                        <Tooltip title="Clear manual path (revert to default)">
                                            <IconButton
                                                onClick={handleClearManualPath}
                                                edge="end"
                                                size="small"
                                            >
                                                <ClearIcon fontSize="small" />
                                            </IconButton>
                                        </Tooltip>
                                    )}
                                    <Tooltip title="Select directory">
                                        <IconButton
                                            onClick={handleSelectDirectory}
                                            edge="end"
                                            disabled={!isElectron}
                                        >
                                            <FolderOpenIcon />
                                        </IconButton>
                                    </Tooltip>
                                </InputAdornment>
                            ),
                        }}
                    />

                    {/* Directory Status Info */}
                    {directoryInfo && (
                        <Box
                            sx={{
                                p: 1.5,
                                borderRadius: 1,
                                border: `2px solid ${theme.palette.divider}`,
                            }}
                        >
                            <Stack spacing={1}>
                                <Box
                                    sx={{
                                        display: "flex",
                                        alignItems: "center",
                                        gap: 1,
                                    }}
                                >
                                    <InfoIcon fontSize="small" color="info" />
                                    <Typography variant="caption" fontWeight="medium">
                                        Mocap Folder Status
                                    </Typography>
                                </Box>

                                <Box
                                    sx={{
                                        display: "flex",
                                        gap: 1,
                                        flexWrap: "wrap",
                                    }}
                                >
                                    <Chip
                                        label={
                                            directoryInfo.exists
                                                ? "Directory exists"
                                                : "Directory will be created"
                                        }
                                        size="small"
                                        color={directoryInfo.exists ? "success" : "default"}
                                        icon={
                                            directoryInfo.exists ? (
                                                <CheckCircleIcon />
                                            ) : (
                                                <CloseIcon />
                                            )
                                        }
                                        variant={directoryInfo.exists ? "filled" : "outlined"}
                                        sx={
                                            !directoryInfo.exists
                                                ? {
                                                    borderColor: theme.palette.grey[400],
                                                    "& .MuiChip-icon": {
                                                        color: theme.palette.grey[600],
                                                    },
                                                }
                                                : {}
                                        }
                                    />
                                    <Chip
                                        label="Has videos"
                                        size="small"
                                        color={directoryInfo.hasVideos ? "success" : "default"}
                                        icon={
                                            directoryInfo.hasVideos ? (
                                                <CheckCircleIcon />
                                            ) : (
                                                <CloseIcon />
                                            )
                                        }
                                        variant={directoryInfo.hasVideos ? "filled" : "outlined"}
                                        sx={
                                            !directoryInfo.hasVideos
                                                ? {
                                                    borderColor: theme.palette.grey[400],
                                                    "& .MuiChip-icon": {
                                                        color: theme.palette.grey[600],
                                                    },
                                                }
                                                : {}
                                        }
                                    />
                                    <Chip
                                        label="Has synchronized_videos"
                                        size="small"
                                        color={
                                            directoryInfo.hasSynchronizedVideos
                                                ? "success"
                                                : "default"
                                        }
                                        icon={
                                            directoryInfo.hasSynchronizedVideos ? (
                                                <CheckCircleIcon />
                                            ) : (
                                                <CloseIcon />
                                            )
                                        }
                                        variant={
                                            directoryInfo.hasSynchronizedVideos
                                                ? "filled"
                                                : "outlined"
                                        }
                                        sx={
                                            !directoryInfo.hasSynchronizedVideos
                                                ? {
                                                    borderColor: theme.palette.grey[400],
                                                    "& .MuiChip-icon": {
                                                        color: theme.palette.grey[600],
                                                    },
                                                }
                                                : {}
                                        }
                                    />
                                    <Chip
                                        label="Has calibration TOML"
                                        size="small"
                                        color={
                                            directoryInfo.cameraMocapTomlPath
                                                ? "success"
                                                : "default"
                                        }
                                        icon={
                                            directoryInfo.cameraMocapTomlPath ? (
                                                <CheckCircleIcon />
                                            ) : (
                                                <CloseIcon />
                                            )
                                        }
                                        variant={
                                            directoryInfo.cameraMocapTomlPath
                                                ? "filled"
                                                : "outlined"
                                        }
                                        sx={
                                            !directoryInfo.cameraMocapTomlPath
                                                ? {
                                                    borderColor: theme.palette.grey[400],
                                                    "& .MuiChip-icon": {
                                                        color: theme.palette.grey[600],
                                                    },
                                                }
                                                : {}
                                        }
                                    />
                                </Box>

                                {directoryInfo.cameraMocapTomlPath && (
                                    <Box sx={{mt: 1}}>
                                        <Typography variant="caption" color="text.secondary">
                                            Found calibration file:
                                        </Typography>
                                        <Typography
                                            variant="caption"
                                            sx={{
                                                fontFamily: "monospace",
                                                display: "block",
                                                color: "success.main",
                                                wordBreak: "break-all",
                                            }}
                                        >
                                            {directoryInfo.cameraMocapTomlPath}
                                        </Typography>
                                    </Box>
                                )}
                            </Stack>
                        </Box>
                    )}

                    {/* Recording Progress */}
                    {isRecording && (
                        <Box sx={{width: "100%"}}>
                            <Typography
                                variant="caption"
                                color="text.secondary"
                                gutterBottom
                            >
                                Recording in Progress: {recordingProgress.toFixed(0)}%
                            </Typography>
                            <Box
                                sx={{
                                    width: "100%",
                                    height: 8,
                                    bgcolor: "grey.300",
                                    borderRadius: 1,
                                    overflow: "hidden",
                                }}
                            >
                                <Box
                                    sx={{
                                        width: `${recordingProgress}%`,
                                        height: "100%",
                                        bgcolor: theme.palette.primary.main,
                                        transition: "width 0.3s",
                                    }}
                                />
                            </Box>
                        </Box>
                    )}

                    {/* MediaPipe Detector Config */}
                    <MediapipeConfigPanel />

                    {/* Skeleton Filter Config */}
                    <SkeletonFilterConfigPanel />

                    {/* Process Recording Button */}
                    <Button
                        variant="contained"
                        color="secondary"
                        onClick={dispatchProcessMocapRecording}
                        disabled={!canProcessMocapRecording || isLoading}
                        fullWidth
                    >
                        Process Selected Recording
                    </Button>
                </Stack>
            </Box>
        </CollapsibleSidebarSection>
    );
};
