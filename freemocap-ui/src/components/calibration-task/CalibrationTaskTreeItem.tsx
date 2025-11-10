// components/CalibrationTaskTreeItem.tsx
import React, { useCallback, useState, useMemo, useEffect } from 'react';
import {
    Box,
    Typography,
    Stack,
    TextField,
    Button,
    FormControlLabel,
    Checkbox,
    Alert,
    useTheme,
    Select,
    MenuItem,
    FormControl,
    InputLabel,
    Chip,
    InputAdornment,
    IconButton,
    Tooltip,
} from '@mui/material';
import { TreeItem } from '@mui/x-tree-view/TreeItem';
import SquareFootIcon from '@mui/icons-material/SquareFoot';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import StopIcon from '@mui/icons-material/Stop';
import FolderOpenIcon from '@mui/icons-material/FolderOpen';
import ClearIcon from '@mui/icons-material/Clear';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import InfoIcon from '@mui/icons-material/Info';
import CloseIcon from '@mui/icons-material/Close';
import { useCalibration } from '@/hooks/useCalibration';
import { useElectronIPC } from '@/services';

type BoardPreset = '5x3' | '7x5';

interface BoardPresetConfig {
    xSquares: number;
    ySquares: number;
}

const BOARD_PRESETS: Record<BoardPreset, BoardPresetConfig> = {
    '5x3': { xSquares: 3, ySquares: 5 },
    '7x5': { xSquares: 7, ySquares: 5 },
};

export const CalibrationTaskTreeItem: React.FC = () => {
    const theme = useTheme();
    const [localError, setLocalError] = useState<string | null>(null);
    const { api, isElectron } = useElectronIPC();

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

    // Validate directory whenever path changes
    useEffect(() => {
        if (calibrationRecordingPath) {
            validateDirectory(calibrationRecordingPath);
        }
    }, [calibrationRecordingPath, validateDirectory]);

    // Determine current board preset based on config values
    const currentPreset = useMemo<BoardPreset>(() => {
        for (const [preset, presetConfig] of Object.entries(BOARD_PRESETS)) {
            if (
                presetConfig.xSquares === config.charucoBoardXSquares &&
                presetConfig.ySquares === config.charucoBoardYSquares
            ) {
                return preset as BoardPreset;
            }
        }
    }, [config.charucoBoardXSquares, config.charucoBoardYSquares]);

    const handleClearError = useCallback((): void => {
        clearError();
        setLocalError(null);
    }, [clearError]);

    const handlePresetChange = useCallback((preset: BoardPreset): void => {
        const presetConfig = BOARD_PRESETS[preset];
        updateCalibrationConfig({
            charucoBoardXSquares: presetConfig.xSquares,
            charucoBoardYSquares: presetConfig.ySquares,
        });
    }, [updateCalibrationConfig]);

    const handleSelectDirectory = async (): Promise<void> => {
        if (!isElectron || !api) {
            console.warn('Electron API not available');
            return;
        }

        try {
            const result: string | null = await api.fileSystem.selectDirectory.mutate();
            if (result) {
                await setManualRecordingPath(result);
            }
        } catch (error) {
            console.error('Failed to select directory:', error);
            setLocalError('Failed to select directory');
        }
    };

    const handlePathInputChange = async (e: React.ChangeEvent<HTMLInputElement>): Promise<void> => {
        const newPath: string = e.target.value;

        // Handle tilde expansion for home directory
        if (newPath.includes('~') && isElectron && api) {
            try {
                const home: string = await api.fileSystem.getHomeDirectory.query();
                const expanded: string = newPath.replace(/^~([\/\\])?/, home ? `${home}$1` : '');
                await setManualRecordingPath(expanded);
            } catch (error) {
                console.error('Failed to expand home directory:', error);
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

    // Helper text for the path input
    const pathHelperText = useMemo(() => {
        if (isUsingManualPath) {
            return 'Using custom path';
        }
        return 'Using default recording directory';
    }, [isUsingManualPath]);

    return (
        <TreeItem
            itemId="calibration-task"
            label={
                <Box sx={{ display: 'flex', alignItems: 'center', py: 1, pr: 1 }}>
                    <SquareFootIcon sx={{ mr: 1, color: theme.palette.secondary.main }} />
                    <Typography variant="subtitle1" sx={{ flexGrow: 1 }}>
                        Capture Volume Calibration
                    </Typography>
                </Box>
            }
        >
            <Box sx={{ p: 2, bgcolor: 'background.paper' }}>
                <Stack spacing={2}>
                    {/* Error Display */}
                    {displayError && (
                        <Alert severity="error" onClose={handleClearError}>
                            {displayError}
                        </Alert>
                    )}

                    {/* Calibration Recording Path Input */}
                    <Box>

                        {/* Live Tracker Toggle */}
                        <FormControlLabel
                            control={
                                <Checkbox
                                    checked={config.liveTrackCharuco}
                                    onChange={(e) => updateCalibrationConfig({ liveTrackCharuco: e.target.checked })}
                                    disabled={isLoading}
                                    sx={{ '&.Mui-checked': { color: theme.palette.text.primary } }}
                                />
                            }
                            label="Live Track Charuco Board"
                        />
                        {/* Recording Controls */}
                        <Stack direction="row" spacing={2} sx={{ mb: 2 }}>
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
                                                disabled={!isElectron}
                                            >
                                                <FolderOpenIcon />
                                            </IconButton>
                                        </Tooltip>
                                    </InputAdornment>
                                ),
                            }}
                        />
                    </Box>

                    {/* Directory Status Info */}
                    {directoryInfo && (
                        <Box sx={{
                            p: 1.5,
                            borderRadius: 1,
                            border: `2px solid ${theme.palette.divider}`
                        }}>
                            <Stack spacing={1}>
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                    <InfoIcon fontSize="small" color="info" />
                                    <Typography variant="caption" fontWeight="medium">
                                        Calibration Folder Status
                                    </Typography>
                                </Box>

                                <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                                    <Chip
                                        label={directoryInfo.exists ? "Directory exists" : "Directory will be created"}
                                        size="small"
                                        color={directoryInfo.exists ? "success" : "default"}
                                        icon={directoryInfo.exists ? <CheckCircleIcon /> : <CloseIcon />}
                                        variant={directoryInfo.exists ? "filled" : "outlined"}
                                        sx={!directoryInfo.exists ? {
                                            borderColor: theme.palette.grey[400],
                                            '& .MuiChip-icon': { color: theme.palette.grey[600] }
                                        } : {}}
                                    />

                                    <Chip
                                        label="Has videos"
                                        size="small"
                                        color={directoryInfo.hasVideos ? "success" : "default"}
                                        icon={directoryInfo.hasVideos ? <CheckCircleIcon /> : <CloseIcon />}
                                        variant={directoryInfo.hasVideos ? "filled" : "outlined"}
                                        sx={!directoryInfo.hasVideos ? {
                                            borderColor: theme.palette.grey[400],
                                            '& .MuiChip-icon': { color: theme.palette.grey[600] }
                                        } : {}}
                                    />

                                    <Chip
                                        label="Has synchronized_videos"
                                        size="small"
                                        color={directoryInfo.hasSynchronizedVideos ? "success" : "default"}
                                        icon={directoryInfo.hasSynchronizedVideos ? <CheckCircleIcon /> : <CloseIcon />}
                                        variant={directoryInfo.hasSynchronizedVideos ? "filled" : "outlined"}
                                        sx={!directoryInfo.hasSynchronizedVideos ? {
                                            borderColor: theme.palette.grey[400],
                                            '& .MuiChip-icon': { color: theme.palette.grey[600] }
                                        } : {}}
                                    />

                                    <Chip
                                        label="Has calibration TOML"
                                        size="small"
                                        color={directoryInfo.cameraCalibrationTomlPath ? "success" : "default"}
                                        icon={directoryInfo.cameraCalibrationTomlPath ? <CheckCircleIcon /> : <CloseIcon />}
                                        variant={directoryInfo.cameraCalibrationTomlPath ? "filled" : "outlined"}
                                        sx={!directoryInfo.cameraCalibrationTomlPath ? {
                                            borderColor: theme.palette.grey[400],
                                            '& .MuiChip-icon': { color: theme.palette.grey[600] }
                                        } : {}}
                                    />
                                </Box>

                                {directoryInfo.cameraCalibrationTomlPath && (
                                    <Box sx={{ mt: 1 }}>
                                        <Typography variant="caption" color="text.secondary">
                                            Found calibration file:
                                        </Typography>
                                        <Typography
                                            variant="caption"
                                            sx={{
                                                fontFamily: 'monospace',
                                                display: 'block',
                                                color: 'success.main',
                                                wordBreak: 'break-all'
                                            }}
                                        >
                                            {directoryInfo.cameraCalibrationTomlPath}
                                        </Typography>
                                    </Box>
                                )}
                            </Stack>
                        </Box>
                    )}

                    {/* Board Size Preset Selector */}
                    <FormControl fullWidth size="small">
                        <InputLabel id="board-preset-label">Board Size Preset</InputLabel>
                        <Select
                            labelId="board-preset-label"
                            value={currentPreset}
                            label="Board Size Preset"
                            onChange={(e) => handlePresetChange(e.target.value as BoardPreset)}
                            disabled={isLoading}
                        >
                            <MenuItem value="5x3">5×3 Charuco</MenuItem>
                            <MenuItem value="7x5">7×5 Charuco</MenuItem>
                        </Select>
                    </FormControl>

                    {/* Square Length */}
                    <TextField
                        label="Square Length (mm)"
                        type="number"
                        value={config.charucoSquareLength}
                        onChange={(e) => updateCalibrationConfig({
                            charucoSquareLength: parseFloat(e.target.value) || 0
                        })}
                        disabled={isLoading}
                        size="small"
                        fullWidth
                        inputProps={{ min: 1, step: 0.1 }}
                    />



                    {/* Recording Progress */}
                    {isRecording && (
                        <Box sx={{ width: '100%' }}>
                            <Typography variant="caption" color="text.secondary" gutterBottom>
                                Recording in Progress: {recordingProgress.toFixed(0)}%
                            </Typography>
                            <Box
                                sx={{
                                    width: '100%',
                                    height: 8,
                                    bgcolor: 'grey.300',
                                    borderRadius: 1,
                                    overflow: 'hidden',
                                }}
                            >
                                <Box
                                    sx={{
                                        width: `${recordingProgress}%`,
                                        height: '100%',
                                        bgcolor: theme.palette.primary.main,
                                        transition: 'width 0.3s',
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
        </TreeItem>
    );
};
