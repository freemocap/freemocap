// components/CalibrationTaskTreeItem.tsx
import React, { useCallback, useState } from 'react';
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
} from '@mui/material';
import { TreeItem } from '@mui/x-tree-view/TreeItem';
import CameraAltIcon from '@mui/icons-material/CameraAlt';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import StopIcon from '@mui/icons-material/Stop';
import FolderOpenIcon from '@mui/icons-material/FolderOpen';
import { useCalibration } from '@/hooks/useCalibration';
import { useFileSystem } from '@/hooks/useFileSystem';
import { CharucoBoardSettings } from './CharucoBoardSettings';

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

    const handleClearError = useCallback((): void => {
        clearError();
        setLocalError(null);
    }, [clearError]);

    const handleSelectDirectory = useCallback(async (): Promise<void> => {
        try {
            const result = await selectDirectory();
            if (result) {
                updateCalibrationConfig({ calibrationRecordingPath: result });
            }
        } catch (err) {
            setLocalError(`Failed to select directory: ${err instanceof Error ? err.message : String(err)}`);
        }
    }, [selectDirectory, updateCalibrationConfig]);

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
                                sx ={{ '&.Mui-checked': { color: theme.palette.text.primary } }}
                            />
                        }
                        label="Enable realtime tracker"
                    />

                    {/* Board Settings */}
                    <CharucoBoardSettings
                        config={config}
                        disabled={isLoading}
                        onConfigUpdate={updateCalibrationConfig}
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
                            Start Recording
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
                                checked={config.autoProcess}
                                onChange={(e) => updateCalibrationConfig({ autoProcess: e.target.checked })}
                                disabled={isLoading}
                            />
                        }
                        label="Auto-process recording"
                    />

                    {/* Path Selector */}
                    <TextField
                        label="Calibration Recording Path"
                        value={config.calibrationRecordingPath}
                        onChange={(e) => updateCalibrationConfig({ calibrationRecordingPath: e.target.value })}
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
