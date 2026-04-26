import React, {useCallback, useMemo, useState} from "react";
import {
    Alert,
    Box,
    Button,
    Chip, FormControlLabel,
    IconButton,
    InputAdornment,
    Stack, Switch,
    TextField,
    Tooltip,
    Typography,
    useTheme,
} from "@mui/material";
import SquareFootIcon from "@mui/icons-material/SquareFoot";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import StopIcon from "@mui/icons-material/Stop";
import FolderOpenIcon from "@mui/icons-material/FolderOpen";
import LaunchIcon from "@mui/icons-material/Launch";
import ClearIcon from "@mui/icons-material/Clear";
import RefreshIcon from "@mui/icons-material/Refresh";
import {DirectoryStatusPanel} from "@/components/common/DirectoryStatusPanel";
import {useCalibration} from "@/hooks/useCalibration";
import {useDirectoryWatcher} from "@/hooks/useDirectoryWatcher";
import {useElectronIPC} from "@/services";
import {CalibrationSolverSection} from "@/components/control-panels/calibration-control-panel/CalibrationSolverSection";
import {CharucoBoardConfigSection} from "@/components/control-panels/calibration-control-panel/CharucoBoardConfigSection";
import {CollapsibleSidebarSection} from "@/components/common/CollapsibleSidebarSection";
import {selectPlannedRecordingName} from "@/store/slices/recording";
import {selectEffectiveRecordingPath} from "@/store/slices/active-recording/active-recording-slice";
import {useAppSelector} from "@/store";
import {config} from "zod";

export const CalibrationPanel: React.FC = () => {
    const theme = useTheme();
    const [localError, setLocalError] = useState<string | null>(null);
    const {api, isElectron} = useElectronIPC();

    const {
        error,
        config,
        isLoading,
        isRecording,
        recordingProgress,
        updateCalibrationConfig,
        canCalibrate,
        calibrationRecordingPath,
        directoryInfo,
        isUsingManualPath,
        dispatchStopCalibrationRecording,
        dispatchStartCalibrationRecording,
        setManualRecordingPath,
        clearManualRecordingPath,
        validateDirectory,
        calibrateSelectedRecording,
        clearError,
    } = useCalibration();

    // Planned recording info (potential recording when no actual recording exists)
    const plannedName = useAppSelector(selectPlannedRecordingName);

    // Effective path: actual activeRecording if any, otherwise the planned path
    const effectiveCalibrationPath = useAppSelector(selectEffectiveRecordingPath);

    // Determine if we're showing a pending (not yet created) recording
    const isPendingRecording = !calibrationRecordingPath && !!plannedName;

    // Auto-poll directory status instead of requiring manual refresh
    const {triggerRefresh, isWatching} = useDirectoryWatcher(
        calibrationRecordingPath,
        validateDirectory,
        3000,
    );

    const handleClearError = useCallback((): void => {
        clearError();
        setLocalError(null);
    }, [clearError]);

    const handleSelectDirectory = async (): Promise<void> => {
        if (!isElectron || !api) return;
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

    const handleOpenFolder = async (): Promise<void> => {
        if (!isElectron || !api || !effectiveCalibrationPath) return;
        try {
            await api.fileSystem.openFolder.mutate({path: effectiveCalibrationPath});
        } catch (err) {
            console.error("Failed to open folder:", err);
            setLocalError("Failed to open folder in file explorer");
        }
    };

    const handlePathInputChange = async (
        e: React.ChangeEvent<HTMLInputElement>,
    ): Promise<void> => {
        const newPath: string = e.target.value;
        if (newPath.includes("~") && api) {
            try {
                const home: string = await api.fileSystem.getHomeDirectory.query();
                const expanded: string = newPath.replace(/^~([\/])?/, home ? home + '$1' : "");
                await setManualRecordingPath(expanded);
            } catch {
                await setManualRecordingPath(newPath);
            }
        } else {
            await setManualRecordingPath(newPath);
        }
    };

    const calibStatus: "ok" | "none" | "bad" = useMemo(() => {
        if (directoryInfo?.cameraCalibrationTomlPath) return "ok";
        if (!calibrationRecordingPath || !directoryInfo) return "none";
        return "bad";
    }, [directoryInfo, calibrationRecordingPath]);

    const displayError = error || localError || directoryInfo?.errorMessage;

    const statusLabel = isRecording
        ? "Recording " + recordingProgress.toFixed(0) + "%"
        : isLoading
            ? "Processing..."
            : isPendingRecording
                ? "Pending"
                : directoryInfo?.cameraCalibrationTomlPath
                    ? "Calibrated"
                    : "Idle";

    const statusColor = isRecording
        ? theme.palette.error.main
        : isLoading
            ? theme.palette.warning.main
            : isPendingRecording
                ? theme.palette.grey[500]
                : directoryInfo?.cameraCalibrationTomlPath
                    ? theme.palette.success.main
                    : theme.palette.grey[600];

    return (
        <CollapsibleSidebarSection
            icon={<SquareFootIcon sx={{color: "inherit"}}/>}
            title="Capture Volume Calibration"
            summaryContent={<Chip
                label={statusLabel}
                size="small"
                sx={{
                    ml: "auto",
                    height: 20,
                    fontSize: 11,
                    fontWeight: 600,
                    backgroundColor: statusColor,
                    color: theme.palette.getContrastText(statusColor),
                }}
            />}
            defaultExpanded={false}
        >
            <Box sx={{p: 2}}>

                <Stack spacing={2}>
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
                            startIcon={<PlayArrowIcon/>}
                            onClick={dispatchStartCalibrationRecording}
                            // disabled={!canStartRecording || isLoading}
                            disabled={ isLoading}
                            fullWidth
                        >
                            Start Calibration Recording
                        </Button>
                        {isRecording && (
                            <Button
                                variant="contained"
                                color="error"
                                startIcon={<StopIcon/>}
                                onClick={dispatchStopCalibrationRecording}
                                disabled={isLoading}
                                fullWidth
                            >
                                Stop Recording
                            </Button>
                        )}
                    </Stack>

                    {/* Recording Path Input */}
                    <TextField
                        label="Calibration Recording Path"
                        value={effectiveCalibrationPath || ''}
                        onChange={handlePathInputChange}
                        fullWidth
                        size="small"
                        helperText={isUsingManualPath ? "Using custom path" : isPendingRecording ? "Pending capture - will create on record" : "Using default recording directory"}
                        InputProps={{
                            endAdornment: (
                                <InputAdornment position="end">
                                    {isUsingManualPath && (
                                        <Tooltip title="Clear manual path (revert to default)">
                                            <IconButton onClick={clearManualRecordingPath} edge="end" size="small">
                                                <ClearIcon fontSize="small"/>
                                            </IconButton>
                                        </Tooltip>
                                    )}
                                    <Tooltip title="Re-check calibration folder">
                                        <span>
                                            <IconButton
                                                onClick={triggerRefresh}
                                                edge="end"
                                                size="small"
                                                disabled={!calibrationRecordingPath || isLoading}
                                            >
                                                <RefreshIcon fontSize="small"/>
                                            </IconButton>
                                        </span>
                                    </Tooltip>
                                    <Tooltip title="Open folder in file explorer">
                                        <span>
                                            <IconButton
                                                onClick={handleOpenFolder}
                                                edge="end"
                                                size="small"
                                                disabled={!isElectron || !effectiveCalibrationPath}
                                            >
                                                <LaunchIcon fontSize="small"/>
                                            </IconButton>
                                        </span>
                                    </Tooltip>
                                    <Tooltip title="Select directory">
                                        <IconButton onClick={handleSelectDirectory} edge="end" disabled={!isElectron}>
                                            <FolderOpenIcon/>
                                        </IconButton>
                                    </Tooltip>
                                </InputAdornment>
                            ),
                        }}
                    />
                    
                    {/* Pending recording indicator */}
                    {isPendingRecording && (
                        <Box sx={{p: 1, borderRadius: 1, bgcolor: theme.palette.action.hover}}>
                            <Stack direction="row" spacing={1} alignItems="center">
                                <Chip
                                    label="Pending capture"
                                    size="small"
                                    variant="outlined"
                                    sx={{height: 18, fontSize: '0.65rem', borderStyle: 'dashed', opacity: 0.7}}
                                />
                                <Typography variant="caption" color="text.secondary" sx={{fontFamily: 'monospace'}}>
                                    {plannedName}
                                </Typography>
                            </Stack>
                        </Box>
                    )}

                    <Button
                        variant="contained"
                        color="secondary"
                        onClick={calibrateSelectedRecording}
                        disabled={!canCalibrate || isLoading}
                        fullWidth
                    >
                        Calibrate Selected Recording
                    </Button>
                    {/* Directory Status (auto-refreshing via useDirectoryWatcher) */}
                    <DirectoryStatusPanel
                        title="Calibration Folder Status"
                        tomlLabel="Has calibration TOML"
                        directoryInfo={directoryInfo ? {
                            ...directoryInfo,
                            tomlPath: directoryInfo.cameraCalibrationTomlPath,
                        } : null}
                        status={calibStatus}
                        onRefresh={triggerRefresh}
                        refreshDisabled={!calibrationRecordingPath || isLoading}
                        isRefreshing={false}
                    />

                    {/* Groundplane */}
                    <FormControlLabel
                        control={
                            <Switch
                                size="small"
                                checked={config.useGroundplane}
                                onChange={(_, checked) =>
                                    updateCalibrationConfig({useGroundplane: checked})
                                }
                                disabled={isLoading}
                            />
                        }
                        label={
                            <Typography variant="body2">
                                Align to ground plane to initial charuco position
                            </Typography>
                        }
                    />
                    <CharucoBoardConfigSection />

                    <CalibrationSolverSection/>

                    {isRecording && (
                        <Box sx={{width: "100%"}}>
                            <Typography variant="caption" color="text.secondary" gutterBottom>
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
                                        width: recordingProgress + "%",
                                        height: "100%",
                                        bgcolor: theme.palette.primary.main,
                                        transition: "width 0.3s",
                                    }}
                                />
                            </Box>
                        </Box>
                    )}


                </Stack>
            </Box>
        </CollapsibleSidebarSection>
    )
        ;
};
