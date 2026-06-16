import React, {useCallback, useEffect, useMemo, useState} from "react";
import {
    Alert,
    Box,
    Button,
    Chip,
    CircularProgress,
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
import FiberManualRecordIcon from "@mui/icons-material/FiberManualRecord";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import WarningAmberIcon from "@mui/icons-material/WarningAmber";
import CancelIcon from "@mui/icons-material/Cancel";
import RefreshIcon from "@mui/icons-material/Refresh";
import InsertDriveFileIcon from "@mui/icons-material/InsertDriveFile";
import {CollapsibleSidebarSection} from "@/components/common/CollapsibleSidebarSection";
import {DirectoryStatusPanel} from "@/components/common/DirectoryStatusPanel";
import {useMocap} from "@/hooks/useMocap";
import {useElectronIPC} from "@/services";
import {MediapipeConfigPanel} from "@/components/control-panels/mocap-control-panel/MediapipeConfigPanel";
import {SkeletonFilterConfigPanel} from "@/components/control-panels/mocap-control-panel/SkeletonFilterConfigPanel";
import {useCalibration} from "@/hooks/useCalibration";

export const MocapTaskTreeItem: React.FC = () => {
    const theme = useTheme();
    const [localError, setLocalError] = useState<string | null>(null);
    const [isRefreshing, setIsRefreshing] = useState(false);
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
        validateDirectory,
        calibrationTomlPath,
        setCalibrationTomlPath,
        clearCalibrationTomlPath,
        clearError,
    } = useMocap();

    
    // Get the most recent calibration recording path from calibration state
    const {
        calibrationRecordingPath: mostRecentCalibrationPath,
        directoryInfo: calibrationDirectoryInfo,
    } = useCalibration();

    useEffect(() => {
        if (mocapRecordingPath) {
            validateDirectory(mocapRecordingPath);
        }
    }, [mocapRecordingPath, validateDirectory]);

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

    const handleRefresh = useCallback(async (): Promise<void> => {
        if (!mocapRecordingPath) return;
        setIsRefreshing(true);
        try {
            await validateDirectory(mocapRecordingPath);
        } finally {
            setTimeout(() => setIsRefreshing(false), 400);
        }
    }, [mocapRecordingPath, validateDirectory]);

    const handleSelectCalibrationToml = async (): Promise<void> => {
        if (!isElectron || !api) {
            console.warn("Electron API not available");
            return;
        }
        try {
            const result: string | null = await api.fileSystem.selectTomlFile.mutate();
            if (result) {
                setCalibrationTomlPath(result);
            }
        } catch (err) {
            console.error("Failed to select TOML file:", err);
            setLocalError("Failed to select TOML file");
        }
    };

    const displayError = error || localError || directoryInfo?.errorMessage;

    const pathHelperText = useMemo(() => {
        if (isUsingManualPath) return "Using custom path";
        return "Using default recording directory";
    }, [isUsingManualPath]);

    // ─── Effective calibration path (considers all sources) ────────────────────
    const effectiveCalibrationTomlPath = useMemo(() => {
        if (calibrationTomlPath) return calibrationTomlPath;
        if (directoryInfo?.cameraMocapTomlPath) return directoryInfo.cameraMocapTomlPath;
        if (calibrationDirectoryInfo?.cameraCalibrationTomlPath) return calibrationDirectoryInfo.cameraCalibrationTomlPath;
        return null;
    }, [calibrationTomlPath, directoryInfo?.cameraMocapTomlPath, calibrationDirectoryInfo?.cameraCalibrationTomlPath]);

    // ─── Mocap status derivation ──────────────────────────────────────────────
    const mocapStatus: "ok" | "none" | "bad" = useMemo(() => {
        if (effectiveCalibrationTomlPath) return "ok";
        if (!mocapRecordingPath || !directoryInfo) return "none";
        return "bad";
    }, [effectiveCalibrationTomlPath, mocapRecordingPath, directoryInfo]);

    const mocapStatusIcon = useMemo(() => {
        if (mocapStatus === "ok") {
            return (
                <Tooltip title="Calibration file found — ready to process">
                    <CheckCircleIcon fontSize="small" sx={{color: "#00e5ff"}} />
                </Tooltip>
            );
        }
        if (mocapStatus === "bad") {
            return (
                <Tooltip title="No calibration file found at this path">
                    <CancelIcon fontSize="small" sx={{color: theme.palette.error.main}} />
                </Tooltip>
            );
        }
        return (
            <Tooltip title="No mocap directory selected">
                <WarningAmberIcon fontSize="small" sx={{color: theme.palette.warning.main}} />
            </Tooltip>
        );
    }, [mocapStatus, theme]);

    const refreshButton = (
        <Tooltip title={mocapRecordingPath ? "Re-check mocap folder" : "No path set"}>
            <span>
                <IconButton
                    size="small"
                    onClick={(e: React.MouseEvent) => {
                        e.stopPropagation();
                        handleRefresh();
                    }}
                    disabled={!mocapRecordingPath || isLoading || isRefreshing}
                    sx={{
                        p: 0.5,
                        color: "inherit",
                        border: "1.5px solid rgba(255,255,255,0.25)",
                        borderRadius: 1,
                        "&:hover": {backgroundColor: "rgba(255,255,255,0.1)"},
                        "&.Mui-disabled": {
                            color: "rgba(255,255,255,0.3)",
                            borderColor: "rgba(255,255,255,0.1)",
                        },
                    }}
                >
                    {isRefreshing ? (
                        <CircularProgress size={16} color="inherit" />
                    ) : (
                        <RefreshIcon fontSize="small" />
                    )}
                </IconButton>
            </span>
        </Tooltip>
    );

    // Derive status for collapsed summary
    const statusLabel = isRecording
        ? `Recording ${recordingProgress.toFixed(0)}%`
        : isLoading
            ? "Processing..."
            : effectiveCalibrationTomlPath
                ? "Ready"
                : "Idle";

    const statusColor = isRecording
        ? theme.palette.error.main
        : isLoading
            ? theme.palette.warning.main
            : effectiveCalibrationTomlPath
                ? theme.palette.success.main
                : theme.palette.grey[600];

    // Primary controls: status icon + refresh + record start/stop
    const headerControls = (
        <Box sx={{display: "flex", alignItems: "center", gap: 0.75}}>
            {mocapStatusIcon}
            {refreshButton}
            {isRecording ? (
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
    )}
        </Box>
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
            primaryControl={headerControls}
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
                    <DirectoryStatusPanel
                        title="Mocap Folder Status"
                        tomlLabel="Has calibration TOML"
                        directoryInfo={directoryInfo ? {
                            ...directoryInfo,
                            tomlPath: directoryInfo.cameraMocapTomlPath,
                        } : null}
                        status={mocapStatus}
                        onRefresh={handleRefresh}
                        refreshDisabled={!mocapRecordingPath || isLoading || isRefreshing}
                        isRefreshing={isRefreshing}
                    />

                    {/* Calibration TOML Override */}
                    <Box sx={{p: 1.5, borderRadius: 1, border: `1px solid ${theme.palette.divider}`}}>
                        <Stack spacing={1}>
                            <Box sx={{display: "flex", alignItems: "center", gap: 1}}>
                                <InsertDriveFileIcon fontSize="small" color="info" />
                                <Typography variant="caption" fontWeight="medium">
                                    Calibration TOML
                                </Typography>
                            </Box>
                            <Typography variant="caption" color="text.secondary">
                                {calibrationTomlPath
                                    ? "Using specified calibration file"
                                    : effectiveCalibrationTomlPath
                                        ? "Using auto-detected calibration"
                                        : "No calibration file found"}
                            </Typography>
                            {effectiveCalibrationTomlPath && (
                                <Typography
                                    variant="caption"
                                    sx={{
                                        fontFamily: "monospace",
                                        display: "block",
                                        color: "success.main",
                                        wordBreak: "break-all",
                                    }}
                                >
                                    {effectiveCalibrationTomlPath}
                                </Typography>
                            )}
                            <Stack direction="row" spacing={1}>
                                <Button
                                    variant={calibrationTomlPath ? "outlined" : "contained"}
                                    size="small"
                                    onClick={clearCalibrationTomlPath}
                                    disabled={!calibrationTomlPath}
                                    sx={{flex: 1}}
                                >
                                    Use Most Recent
                                </Button>
                                <Button
                                    variant={calibrationTomlPath ? "contained" : "outlined"}
                                    size="small"
                                    startIcon={<InsertDriveFileIcon />}
                                    onClick={handleSelectCalibrationToml}
                                    disabled={!isElectron}
                                    sx={{flex: 1}}
                                >
                                    Select TOML
                                </Button>
                            </Stack>
                        </Stack>
                    </Box>

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
