// components/CalibrationTaskTreeItem.tsx
import React, { useCallback, useState, useMemo } from 'react';
import {
    Box,
    Typography,
    Stack,
    TextField,
    Button,
    FormControlLabel,
    Checkbox,
    Alert,
    IconButton,
    InputAdornment,
    useTheme,
    Select,
    MenuItem,
    FormControl,
    InputLabel,
} from '@mui/material';
import { TreeItem } from '@mui/x-tree-view/TreeItem';
import CameraAltIcon from '@mui/icons-material/CameraAlt';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import StopIcon from '@mui/icons-material/Stop';
import FolderOpenIcon from '@mui/icons-material/FolderOpen';
import { useCalibration } from '@/hooks/useCalibration';
import { useFileSystem } from '@/hooks/useFileSystem';

type BoardPreset = '5x3' | '7x5' ;

interface BoardPresetConfig {
    xSquares: number;
    ySquares: number;
}

const BOARD_PRESETS: Record<Exclude<BoardPreset, 'custom'>, BoardPresetConfig> = {
    '5x3': { xSquares: 5, ySquares: 3 },
    '7x5': { xSquares: 7, ySquares: 5 },
};

export const CalibrationTaskTreeItem: React.FC = () => {
    const theme = useTheme();
    const [localError, setLocalError] = useState<string | null>(null);
    const { isElectron, selectDirectory } = useFileSystem();

    const {
        config,
        error,
        isLoading,
        isRecording,
        recordingProgress,
        canStartRecording,
        canCalibrate,
        updateCalibrationConfig,
        startRecording,
        stopRecording,
        calibrate,
        clearError,
    } = useCalibration();

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
        throw new Error('Current board size does not match any preset');
    }, [config.charucoBoardXSquares, config.charucoBoardYSquares]);

    const handleClearError = useCallback((): void => {
        clearError();
        setLocalError(null);
    }, [clearError]);

    const handleSelectDirectory = useCallback(async (): Promise<void> => {
        try {
            const result = await selectDirectory();
            if (result) {
                // updateCalibrationConfig({ calibrationRecordingInfo: result });
            }
        } catch (err) {
            setLocalError(`Failed to select directory: ${err instanceof Error ? err.message : String(err)}`);
        }
    }, [selectDirectory]);

    const handlePresetChange = useCallback((preset: BoardPreset): void => {
            const presetConfig = BOARD_PRESETS[preset];
            updateCalibrationConfig({
                charucoBoardXSquares: presetConfig.xSquares,
                charucoBoardYSquares: presetConfig.ySquares,
            });
    }, [updateCalibrationConfig]);

    const displayError = error || localError;

    return (
        <TreeItem
            itemId="calibration-task"
            label={
                <Box sx={{ display: 'flex', alignItems: 'center', py: 1, pr: 1 }}>
                    <CameraAltIcon sx={{ mr: 1, color: theme.palette.secondary.main }} />
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
                            <MenuItem value="5x3">5×3 Charuco </MenuItem>
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

                    {/* Recording Controls */}
                    <Stack direction="row" spacing={2}>
                        <Button
                            variant="contained"
                            color="primary"
                            startIcon={<PlayArrowIcon />}
                            onClick={startRecording}
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
                                onClick={stopRecording}
                                disabled={isLoading}
                                fullWidth
                            >
                                Stop Recording
                            </Button>
                        )}
                    </Stack>

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

                    {/* Auto-process Toggle */}
                    <FormControlLabel
                        control={
                            <Checkbox
                                checked={config.autoProcessRecording}
                                onChange={(e) => updateCalibrationConfig({ autoProcessRecording: e.target.checked })}
                                disabled={isLoading}
                            />
                        }
                        label="Auto-process recording"
                    />

                    {/* Path Selector */}
                    <TextField
                        label="Calibration Recording Path"
                        value={config.calibrationRecordingPath}
                        onChange={(e) => updateCalibrationConfig({ calibrationRecordingFolder: e.target.value })}
                        disabled={isLoading}
                        fullWidth
                        size="small"
                        InputProps={{
                            endAdornment: (
                                <InputAdornment position="end">
                                    <IconButton
                                        onClick={handleSelectDirectory}
                                        edge="end"
                                        disabled={!isElectron || isLoading}
                                    >
                                        <FolderOpenIcon />
                                    </IconButton>
                                </InputAdornment>
                            ),
                        }}
                    />

                    {/* Calibrate Button */}
                    <Button
                        variant="contained"
                        color="secondary"
                        onClick={calibrate}
                        disabled={!canCalibrate || isLoading}
                        fullWidth
                    >
                        Calibrate Recording
                    </Button>
                </Stack>
            </Box>
        </TreeItem>
    );
};
