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
import SquareFootIcon from "@mui/icons-material/SquareFoot";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import StopIcon from "@mui/icons-material/Stop";
import FolderOpenIcon from "@mui/icons-material/FolderOpen";
import ClearIcon from "@mui/icons-material/Clear";
import RefreshIcon from "@mui/icons-material/Refresh";
import {DirectoryStatusPanel} from "@/components/common/DirectoryStatusPanel";
import {useCalibration} from "@/hooks/useCalibration";
import {useDirectoryWatcher} from "@/hooks/useDirectoryWatcher";
import {useElectronIPC} from "@/services";
import {CalibrationSolverSection} from "@/components/control-panels/calibration-control-panel/CalibrationSolverSection";
import {CharucoBoardConfigSection} from "@/components/control-panels/calibration-control-panel/CharucoBoardConfigSection";
import {CollapsibleSidebarSection} from "@/components/common/CollapsibleSidebarSection";

export const CalibrationPanel: React.FC = () => {
    const theme = useTheme();
    const [localError, setLocalError] = useState<string | null>(null);
    const {api} = useElectronIPC();

    const {
        error,
        isLoading,
        isRecording,
        recordingProgress,
        canStartRecording,
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
        if (!api) return;
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
        e: React.ChangeEvent<HTMLInputElement>,
    ): Promise<void> => {
        const newPath: string = e.target.value;
        if (newPath.includes("~") && api) {
            try {
                const home: string = await api.fileSystem.getHomeDirectory.query();
                const expanded: string = newPath.replace(/^~([/\\])?/, home ? `${home}$1` : "");
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
        ? `Recording ${recordingProgress.toFixed(0)}%`
        : isLoading
            ? "Processing..."
            : directoryInfo?.cameraCalibrationTomlPath
                ? "Calibrated"
                : "Idle";

    const statusColor = isRecording
        ? theme.palette.error.main
        : isLoading
            ? theme.palette.warning.main
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

                    {/*<FormControlLabel*/}
                    {/*    control={*/}
                    {/*        <Checkbox*/}
                    {/*            checked={config.liveTrackCharuco}*/}
                    {/*            onChange={(e) =>*/}
                    {/*                updateCalibrationConfig({liveTrackCharuco: e.target.checked})*/}
                    {/*            }*/}
                    {/*            disabled={isLoading}*/}
                    {/*        />*/}
                    {/*    }*/}
                    {/*    label="Live Track Charuco Board"*/}
                    {/*/>*/}

                    {/* Recording Controls */}
                    <Stack direction="row" spacing={2}>
                        <Button
                            variant="contained"
                            color="primary"
                            startIcon={<PlayArrowIcon/>}
                            onClick={dispatchStartCalibrationRecording}
                            disabled={!canStartRecording || isLoading}
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
                        value={calibrationRecordingPath}
                        onChange={handlePathInputChange}
                        fullWidth
                        size="small"
                        helperText={isUsingManualPath ? "Using custom path" : "Using default recording directory"}
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
                                    <Tooltip title="Select directory">
                                        <IconButton onClick={handleSelectDirectory} edge="end">
                                            <FolderOpenIcon/>
                                        </IconButton>
                                    </Tooltip>
                                </InputAdornment>
                            ),
                        }}
                    />
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
                                        width: `${recordingProgress}%`,
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
