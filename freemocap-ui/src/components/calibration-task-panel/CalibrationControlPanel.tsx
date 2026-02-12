import React, {useCallback, useEffect, useMemo, useState} from "react";
import {
    Alert,
    Box,
    Button,
    Checkbox,
    Chip,
    FormControl,
    FormControlLabel,
    IconButton,
    InputAdornment,
    InputLabel,
    MenuItem,
    Select,
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
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import InfoIcon from "@mui/icons-material/Info";
import CloseIcon from "@mui/icons-material/Close";
import FiberManualRecordIcon from "@mui/icons-material/FiberManualRecord";
import {CollapsibleSidebarSection} from "@/components/common/CollapsibleSidebarSection";
import {useCalibration} from "@/hooks/useCalibration";
import {useElectronIPC} from "@/services";

type BoardPreset = "5x3" | "7x5" | "custom";

interface BoardPresetConfig {
    xSquares: number;
    ySquares: number;
}

const BOARD_PRESETS: Record<Exclude<BoardPreset, "custom">, BoardPresetConfig> = {
    "5x3": {xSquares: 5, ySquares: 3},
    "7x5": {xSquares: 7, ySquares: 5},
};

export const CalibrationControlPanel: React.FC = () => {
    const theme = useTheme();
    const [localError, setLocalError] = useState<string | null>(null);
    const {api} = useElectronIPC();

    const {
        config,
        error,
        isLoading,
        isRecording,
        recordingProgress,
        canStartRecording,
        canCalibrate,
        calibrationRecordingPath,
        directoryInfo,
        isUsingManualPath,
        updateCalibrationConfig,
        dispatchStopCalibrationRecording,
        dispatchStartCalibrationRecording,
        setManualRecordingPath,
        clearManualRecordingPath,
        validateDirectory,
        calibrateSelectedRecording,
        clearError,
    } = useCalibration();

    useEffect(() => {
        if (calibrationRecordingPath) {
            validateDirectory(calibrationRecordingPath);
        }
    }, [calibrationRecordingPath, validateDirectory]);

    const currentPreset = useMemo<BoardPreset>(() => {
        for (const [preset, presetConfig] of Object.entries(BOARD_PRESETS)) {
            if (
                presetConfig.xSquares === config.charucoBoardXSquares &&
                presetConfig.ySquares === config.charucoBoardYSquares
            ) {
                return preset as BoardPreset;
            }
        }
        return "custom";
    }, [config.charucoBoardXSquares, config.charucoBoardYSquares]);

    const handleClearError = useCallback((): void => {
        clearError();
        setLocalError(null);
    }, [clearError]);

    const handlePresetChange = useCallback(
        (preset: BoardPreset): void => {
            if (preset === "custom") return;
            const presetConfig = BOARD_PRESETS[preset];
            updateCalibrationConfig({
                charucoBoardXSquares: presetConfig.xSquares,
                charucoBoardYSquares: presetConfig.ySquares,
            });
        },
        [updateCalibrationConfig]
    );

    const handleXSquaresChange = useCallback(
        (value: string): void => {
            const numValue = parseInt(value, 10);
            if (!isNaN(numValue) && numValue > 0) {
                updateCalibrationConfig({charucoBoardXSquares: numValue});
            }
        },
        [updateCalibrationConfig]
    );

    const handleYSquaresChange = useCallback(
        (value: string): void => {
            const numValue = parseInt(value, 10);
            if (!isNaN(numValue) && numValue > 0) {
                updateCalibrationConfig({charucoBoardYSquares: numValue});
            }
        },
        [updateCalibrationConfig]
    );

    const handleSelectDirectory = async (): Promise<void> => {
        if (!api) {
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
        if (newPath.includes("~") && api) {
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

    // Primary control: compact start/stop recording toggle in the header
    const headerRecordButton = isRecording ? (
        <Tooltip title="Stop calibration recording">
            <IconButton
                size="small"
                onClick={(e: React.MouseEvent) => {
                    e.stopPropagation();
                    dispatchStopCalibrationRecording();
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
        <Tooltip title={canStartRecording ? "Start calibration recording" : "Cannot record yet"}>
            <span>
                <IconButton
                    size="small"
                    onClick={(e: React.MouseEvent) => {
                        e.stopPropagation();
                        dispatchStartCalibrationRecording();
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
            icon={<SquareFootIcon sx={{color: "inherit"}} />}
            title="Calibration"
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

                    {/* Live Tracker Toggle */}
                    <FormControlLabel
                        control={
                            <Checkbox
                                checked={config.liveTrackCharuco}
                                onChange={(e) =>
                                    updateCalibrationConfig({
                                        liveTrackCharuco: e.target.checked,
                                    })
                                }
                                disabled={isLoading}
                                sx={{
                                    "&.Mui-checked": {
                                        color: theme.palette.text.primary,
                                    },
                                }}
                            />
                        }
                        label="Live Track Charuco Board"
                    />

                    {/* Recording Controls */}
                    <Stack direction="row" spacing={2}>
                        <Button
                            variant="contained"
                            color="primary"
                            startIcon={<PlayArrowIcon />}
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
                                startIcon={<StopIcon />}
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
                                        Calibration Folder Status
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
                                            directoryInfo.cameraCalibrationTomlPath
                                                ? "success"
                                                : "default"
                                        }
                                        icon={
                                            directoryInfo.cameraCalibrationTomlPath ? (
                                                <CheckCircleIcon />
                                            ) : (
                                                <CloseIcon />
                                            )
                                        }
                                        variant={
                                            directoryInfo.cameraCalibrationTomlPath
                                                ? "filled"
                                                : "outlined"
                                        }
                                        sx={
                                            !directoryInfo.cameraCalibrationTomlPath
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

                                {directoryInfo.cameraCalibrationTomlPath && (
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
                                            {directoryInfo.cameraCalibrationTomlPath}
                                        </Typography>
                                    </Box>
                                )}
                            </Stack>
                        </Box>
                    )}

                    {/* Board Size Configuration */}
                    <Stack direction="row" spacing={2}>
                        <FormControl size="small" sx={{minWidth: 140}}>
                            <InputLabel id="board-preset-label">Preset</InputLabel>
                            <Select
                                labelId="board-preset-label"
                                value={currentPreset}
                                label="Preset"
                                onChange={(e) =>
                                    handlePresetChange(e.target.value as BoardPreset)
                                }
                                disabled={isLoading}
                                sx={{color: theme.palette.text.primary}}
                            >
                                <MenuItem value="5x3">5×3</MenuItem>
                                <MenuItem value="7x5">7×5</MenuItem>
                                <MenuItem value="custom">Custom</MenuItem>
                            </Select>
                        </FormControl>
                        <TextField
                            label="X Squares"
                            type="number"
                            value={config.charucoBoardXSquares}
                            onChange={(e) => handleXSquaresChange(e.target.value)}
                            disabled={isLoading}
                            size="small"
                            sx={{flex: 1}}
                            inputProps={{min: 2, max: 20}}
                        />
                        <TextField
                            label="Y Squares"
                            type="number"
                            value={config.charucoBoardYSquares}
                            onChange={(e) => handleYSquaresChange(e.target.value)}
                            disabled={isLoading}
                            size="small"
                            sx={{flex: 1}}
                            inputProps={{min: 2, max: 20}}
                        />
                    </Stack>

                    {/* Square Length */}
                    <TextField
                        label="Square Length (mm)"
                        type="number"
                        value={config.charucoSquareLength}
                        onChange={(e) =>
                            updateCalibrationConfig({
                                charucoSquareLength: parseFloat(e.target.value) || 0,
                            })
                        }
                        disabled={isLoading}
                        size="small"
                        fullWidth
                        inputProps={{min: 1, step: 0.1}}
                    />

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

                    {/* Calibrate Button */}
                    <Button
                        variant="contained"
                        color="secondary"
                        onClick={calibrateSelectedRecording}
                        disabled={!canCalibrate || isLoading}
                        fullWidth
                    >
                        Calibrate Selected Recording
                    </Button>
                </Stack>
            </Box>
        </CollapsibleSidebarSection>
    );
};
