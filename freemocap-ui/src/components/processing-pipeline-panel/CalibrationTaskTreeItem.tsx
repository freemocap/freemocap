import React, { useCallback, useState } from "react";
import {
    Box,
    Button,
    Typography,
    TextField,
    Stack,
    FormControlLabel,
    Checkbox,
    Select,
    MenuItem,
    FormControl,
    InputLabel,
    IconButton,
    InputAdornment,
    useTheme,
    SelectChangeEvent,
    Alert,
} from "@mui/material";
import { TreeItem } from "@mui/x-tree-view/TreeItem";
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import StopIcon from '@mui/icons-material/Stop';
import CameraAltIcon from '@mui/icons-material/CameraAlt';
import FolderOpenIcon from '@mui/icons-material/FolderOpen';
import { useElectronIPC } from '@/services';
import { BoardType, CalibrationConfig, getBoardSizeForType } from "@/store/slices/calibration";
import { useCalibration } from "@/hooks/useCalibration";

export const CalibrationTaskTreeItem: React.FC = () => {
    const theme = useTheme();
    const { api, isElectron } = useElectronIPC();
    const calibration = useCalibration();
    const [localError, setLocalError] = useState<string | null>(null);

    const handleBoardTypeChange = useCallback((event: SelectChangeEvent<BoardType>): void => {
        const boardType = event.target.value as BoardType;
        const updates: Partial<CalibrationConfig> = { boardType };

        if (boardType !== 'custom') {
            updates.boardSize = getBoardSizeForType(boardType);
        }

        calibration.updateConfig(updates);
    }, [calibration]);

    const handleSelectCalibrationPath = useCallback(async (): Promise<void> => {
        setLocalError(null);

        if (!isElectron) {
            setLocalError('Directory selection is only available in the desktop app');
            return;
        }

        if (!api) {
            setLocalError('Electron API is not initialized');
            return;
        }

        try {
            const result: string | null = await api.fileSystem.selectDirectory.mutate();
            if (result) {
                calibration.updateConfig({ calibrationPath: result });
            }
        } catch (error) {
            setLocalError(`Failed to select directory: ${error instanceof Error ? error.message : String(error)}`);
        }
    }, [isElectron, api, calibration]);

    const handleCalibrationPathChange = useCallback(async (e: React.ChangeEvent<HTMLInputElement>): Promise<void> => {
        const newPath: string = e.target.value;

        if (newPath.includes('~') && isElectron && api) {
            try {
                const home: string = await api.fileSystem.getHomeDirectory.query();
                const expanded: string = newPath.replace(/^~(\/|\\)?/, home ? `${home}$1` : '');
                calibration.updateConfig({ calibrationPath: expanded });
            } catch (error) {
                setLocalError(`Failed to expand home directory: ${error instanceof Error ? error.message : String(error)}`);
            }
        } else {
            calibration.updateConfig({ calibrationPath: newPath });
        }
    }, [isElectron, api, calibration]);

    const handleBoardSizeChange = useCallback((field: 'rows' | 'cols', value: string): void => {
        const numValue = parseInt(value, 10);
        if (isNaN(numValue) || numValue < 1) return;

        calibration.updateConfig({
            boardSize: {
                ...calibration.config.boardSize,
                [field]: numValue,
            },
        });
    }, [calibration]);

    const handleSquareSizeChange = useCallback((value: string): void => {
        const numValue = parseInt(value, 10);
        if (isNaN(numValue) || numValue < 1) return;

        calibration.updateConfig({ squareSize: numValue });
    }, [calibration]);

    const handleMinSharedViewsChange = useCallback((value: string): void => {
        const numValue = parseInt(value, 10);
        if (isNaN(numValue) || numValue < 1) return;

        calibration.updateConfig({ minSharedViews: numValue });
    }, [calibration]);

    const isCustomBoard = calibration.config.boardType === 'custom';
    const displayError = calibration.error || localError;

    return (
        <TreeItem
            itemId="calibration-task"
            label={
                <Box
                    sx={{
                        display: "flex",
                        alignItems: "center",
                        py: 1,
                        pr: 1,
                    }}
                >
                    <CameraAltIcon sx={{ mr: 1, color: theme.palette.secondary.main }} />
                    <Typography variant="subtitle1" sx={{ flexGrow: 1 }}>
                        Capture Volume Calibration
                    </Typography>
                </Box>
            }
        >
            <Box sx={{ p: 2, bgcolor: 'background.paper' }}>
                {/* Realtime Tracker Toggle */}
                <FormControlLabel
                    control={
                        <Checkbox
                            checked={calibration.config.realtimeTracker}
                            onChange={(e) => calibration.updateConfig({
                                realtimeTracker: e.target.checked
                            })}
                            disabled={calibration.isLoading}
                            sx={{
                                m:2,
                                color: theme.palette.text.primary,
                                '&.Mui-checked': {
                                    color: theme.palette.text.primary,
                                },
                            }}
                        />
                    }
                    label="Enable realtime tracker"
                />
                <Stack spacing={2}>
                    {/* Error Display */}
                    {displayError && (
                        <Alert
                            severity="error"
                            onClose={() => {
                                calibration.clearError();
                                setLocalError(null);
                            }}
                        >
                            {displayError}
                        </Alert>
                    )}

                    {/* Board Type Selection */}
                    <FormControl fullWidth size="small">
                        <InputLabel>Board Type</InputLabel>
                        <Select
                            value={calibration.config.boardType}
                            label="Board Type"
                            onChange={handleBoardTypeChange}
                            disabled={calibration.isLoading}
                        >
                            <MenuItem value="5x3">5x3 Board</MenuItem>
                            <MenuItem value="7x5">7x5 Board</MenuItem>
                            <MenuItem value="custom">Custom</MenuItem>
                        </Select>
                    </FormControl>

                    {/* Custom Board Size */}
                    {isCustomBoard && (
                        <Stack direction="row" spacing={2}>
                            <TextField
                                label="Rows"
                                type="number"
                                size="small"
                                value={calibration.config.boardSize.rows}
                                onChange={(e) => handleBoardSizeChange('rows', e.target.value)}
                                disabled={calibration.isLoading}
                                inputProps={{ min: 1 }}
                                fullWidth
                            />
                            <TextField
                                label="Columns"
                                type="number"
                                size="small"
                                value={calibration.config.boardSize.cols}
                                onChange={(e) => handleBoardSizeChange('cols', e.target.value)}
                                disabled={calibration.isLoading}
                                inputProps={{ min: 1 }}
                                fullWidth
                            />
                        </Stack>
                    )}

                    {/* Square Size */}
                    <TextField
                        label="Square Size (mm)"
                        type="number"
                        size="small"
                        value={calibration.config.squareSize}
                        onChange={(e) => handleSquareSizeChange(e.target.value)}
                        disabled={calibration.isLoading}
                        inputProps={{ min: 1 }}
                        fullWidth
                    />

                    {/* Min Shared Views */}
                    <TextField
                        label="Min Shared Views per Camera"
                        type="number"
                        size="small"
                        value={calibration.config.minSharedViews}
                        onChange={(e) => handleMinSharedViewsChange(e.target.value)}
                        disabled={calibration.isLoading}
                        inputProps={{ min: 1 }}
                        fullWidth
                    />

                    {/* Recording Control Buttons */}
                    <Stack direction="row" spacing={2}>
                        <Button
                            variant="contained"
                            color="primary"
                            startIcon={<PlayArrowIcon />}
                            onClick={calibration.startCalibrationRecording()}
                            disabled={!calibration.canStartCalibrationRecording || calibration.isLoading}
                            fullWidth
                        >
                            Start Recording
                        </Button>
                        {calibration.isRecording && (
                            <Button
                                variant="contained"
                                color="error"
                                startIcon={<StopIcon />}
                                onClick={calibration.stopCalibrationRecording}
                                disabled={calibration.isLoading}
                                fullWidth
                            >
                                Stop Recording
                            </Button>
                        )}
                    </Stack>

                    {/* Auto-process Recording Checkbox */}
                    <FormControlLabel
                        control={
                            <Checkbox
                                checked={calibration.config.autoProcess}
                                onChange={(e) => calibration.updateConfig({
                                    autoProcess: e.target.checked
                                })}
                                disabled={calibration.isLoading}
                                sx={{
                                    color: theme.palette.text.primary,
                                    '&.Mui-checked': {
                                        color: theme.palette.text.primary,
                                    },
                                }}
                            />
                        }
                        label="Auto-process recording"
                    />



                    {/* Calibrate Recording Path */}
                    <TextField
                        label="Calibration Recording Path"
                        value={calibration.config.calibrationPath}
                        onChange={handleCalibrationPathChange}
                        disabled={calibration.isLoading}
                        fullWidth
                        size="small"
                        InputProps={{
                            endAdornment: (
                                <InputAdornment position="end">
                                    <IconButton
                                        onClick={handleSelectCalibrationPath}
                                        edge="end"
                                        disabled={!isElectron || calibration.isLoading}
                                    >
                                        <FolderOpenIcon />
                                    </IconButton>
                                </InputAdornment>
                            ),
                        }}
                    />

                    {/* Calibrate Recording Button */}
                    <Button
                        variant="contained"
                        color="secondary"
                        onClick={calibration.calibrateRecording}
                        disabled={!calibration.canCalibrateRecording || calibration.isLoading}
                        fullWidth
                    >
                        Calibrate Recording
                    </Button>

                    {/* Progress Bar */}
                    {calibration.isRecording && (
                        <Box sx={{ width: '100%', mt: 1 }}>
                            <Typography variant="caption" color="text.secondary" gutterBottom>
                                Recording in Progress: {calibration.recordingProgress.toFixed(0)}%
                            </Typography>
                            <Box
                                sx={{
                                    width: '100%',
                                    height: 8,
                                    bgcolor: 'grey.300',
                                    borderRadius: 1,
                                    overflow: 'hidden'
                                }}
                            >
                                <Box
                                    sx={{
                                        width: `${calibration.recordingProgress}%`,
                                        height: '100%',
                                        bgcolor: theme.palette.primary.main,
                                        transition: 'width 0.3s'
                                    }}
                                />
                            </Box>
                        </Box>
                    )}
                </Stack>
            </Box>
        </TreeItem>
    );
};
