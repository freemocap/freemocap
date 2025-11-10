import React, { useState, useEffect } from "react";
import {
    Box,
    Button,
    Typography,
    useTheme,
    Chip,
    Select,
    MenuItem,
    FormControl,
    InputLabel,
    Switch,
    FormControlLabel,
    Stack,
    Divider,
    SelectChangeEvent
} from "@mui/material";
import { TreeItem } from "@mui/x-tree-view/TreeItem";
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import StopIcon from '@mui/icons-material/Stop';
import PersonIcon from '@mui/icons-material/Person';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import PendingIcon from '@mui/icons-material/Pending';

type MocapStatus = 'idle' | 'recording' | 'processing' | 'completed' | 'error';

export const MocapTaskTreeItem: React.FC = () => {
    const theme = useTheme();
    const [status, setStatus] = useState<MocapStatus>('idle');
    const [recordingTime, setRecordingTime] = useState(0);
    const [modelType, setModelType] = useState('full-body');
    const [outputFormat, setOutputFormat] = useState('bvh');
    const [smoothing, setSmoothing] = useState(0.5);
    const [useGpu, setUseGpu] = useState(true);

    useEffect(() => {
        let interval: NodeJS.Timeout | undefined;
        if (status === 'recording') {
            interval = setInterval(() => {
                setRecordingTime(prev => prev + 0.1);
            }, 100);
        }
        return () => {
            if (interval) {
                clearInterval(interval);
            }
        };
    }, [status]);

    const getStatusIcon = (): React.ReactElement => {
        switch (status) {
            case 'recording':
                return <PendingIcon sx={{ color: theme.palette.error.main }} />;
            case 'processing':
                return <PendingIcon sx={{ color: theme.palette.warning.main }} />;
            case 'completed':
                return <CheckCircleIcon sx={{ color: theme.palette.success.main }} />;
            case 'error':
                return <ErrorIcon sx={{ color: theme.palette.error.main }} />;
            default:
                return <PersonIcon sx={{ color: theme.palette.info.main }} />;
        }
    };

    const handleStartRecording = (e: React.MouseEvent): void => {
        e.stopPropagation();
        setStatus('recording');
    };

    const handleStopRecording = (e: React.MouseEvent): void => {
        e.stopPropagation();
        setStatus('processing');
        setTimeout(() => setStatus('completed'), 2000);
    };

    const handleReset = (e: React.MouseEvent): void => {
        e.stopPropagation();
        setRecordingTime(0);
        setStatus('idle');
    };

    const handleModelTypeChange = (e: SelectChangeEvent<string>): void => {
        setModelType(e.target.value);
    };

    const handleOutputFormatChange = (e: SelectChangeEvent<string>): void => {
        setOutputFormat(e.target.value);
    };

    const handleSmoothingChange = (e: React.ChangeEvent<HTMLInputElement>): void => {
        setSmoothing(parseFloat(e.target.value));
    };

    const getStatusColor = (): string => {
        switch (status) {
            case 'recording':
                return theme.palette.error.main;
            case 'processing':
                return theme.palette.warning.main;
            case 'completed':
                return theme.palette.success.main;
            case 'error':
                return theme.palette.error.main;
            default:
                return theme.palette.grey[600];
        }
    };

    return (
        <TreeItem
            itemId="mocap-task"
            label={
                <Box
                    sx={{
                        display: "flex",
                        alignItems: "center",
                        py: 1,
                        pr: 1,
                    }}
                >
                    <PersonIcon sx={{ mr: 1, color: theme.palette.secondary.main }} />
                    <Typography variant="subtitle1" sx={{ flexGrow: 1 }}>
                        Motion Capture Task
                    </Typography>
                    {getStatusIcon()}
                    <Chip
                        label={status.toUpperCase()}
                        size="small"
                        sx={{
                            ml: 1,
                            backgroundColor: getStatusColor(),
                            color: 'white',
                            fontSize: 10,
                            height: 20,
                        }}
                    />
                </Box>
            }
        >
            <Box sx={{ p: 2, bgcolor: 'background.paper' }}>
                <Stack spacing={2}>
                    {/* Recording Status */}
                    {/*<Box>*/}
                    {/*    <Typography variant="caption" color="text.secondary">*/}
                    {/*        Recording Time*/}
                    {/*    </Typography>*/}
                    {/*    <Typography*/}
                    {/*        variant="h5"*/}
                    {/*        sx={{*/}
                    {/*            color: status === 'recording' ? 'error.main' : 'text.primary'*/}
                    {/*        }}*/}
                    {/*    >*/}
                    {/*        {recordingTime.toFixed(1)}s*/}
                    {/*    </Typography>*/}
                    {/*</Box>*/}

                    {/*<Divider />*/}

                    {/*/!* Model Configuration *!/*/}
                    {/*<Box>*/}
                    {/*    <Typography variant="subtitle2" gutterBottom>*/}
                    {/*        Model Configuration*/}
                    {/*    </Typography>*/}
                    {/*    <Stack spacing={2}>*/}
                    {/*        <FormControl size="small" fullWidth>*/}
                    {/*            <InputLabel>Model Type</InputLabel>*/}
                    {/*            <Select*/}
                    {/*                value={modelType}*/}
                    {/*                label="Model Type"*/}
                    {/*                onChange={handleModelTypeChange}*/}
                    {/*            >*/}
                    {/*                <MenuItem value="full-body">Full Body (26 points)</MenuItem>*/}
                    {/*                <MenuItem value="upper-body">Upper Body (13 points)</MenuItem>*/}
                    {/*                <MenuItem value="hands">Hands Only (21 points each)</MenuItem>*/}
                    {/*                <MenuItem value="face">Face (468 landmarks)</MenuItem>*/}
                    {/*            </Select>*/}
                    {/*        </FormControl>*/}

                    {/*        <FormControl size="small" fullWidth>*/}
                    {/*            <InputLabel>Output Format</InputLabel>*/}
                    {/*            <Select*/}
                    {/*                value={outputFormat}*/}
                    {/*                label="Output Format"*/}
                    {/*                onChange={handleOutputFormatChange}*/}
                    {/*            >*/}
                    {/*                <MenuItem value="bvh">BVH</MenuItem>*/}
                    {/*                <MenuItem value="fbx">FBX</MenuItem>*/}
                    {/*                <MenuItem value="json">JSON</MenuItem>*/}
                    {/*                <MenuItem value="csv">CSV</MenuItem>*/}
                    {/*            </Select>*/}
                    {/*        </FormControl>*/}
                    {/*    </Stack>*/}
                    {/*</Box>*/}

                    {/*/!* Processing Settings *!/*/}
                    {/*<Box>*/}
                    {/*    <Typography variant="subtitle2" gutterBottom>*/}
                    {/*        Processing Settings*/}
                    {/*    </Typography>*/}
                    {/*    <Stack spacing={2}>*/}
                    {/*        <Box>*/}
                    {/*            <Typography variant="caption" gutterBottom>*/}
                    {/*                Smoothing: {smoothing.toFixed(2)}*/}
                    {/*            </Typography>*/}
                    {/*            <input*/}
                    {/*                type="range"*/}
                    {/*                min="0"*/}
                    {/*                max="1"*/}
                    {/*                step="0.01"*/}
                    {/*                value={smoothing}*/}
                    {/*                onChange={handleSmoothingChange}*/}
                    {/*                style={{ width: '100%' }}*/}
                    {/*            />*/}
                    {/*        </Box>*/}
                    {/*        <FormControlLabel*/}
                    {/*            control={*/}
                    {/*                <Switch*/}
                    {/*                    checked={useGpu}*/}
                    {/*                    onChange={(e) => setUseGpu(e.target.checked)}*/}
                    {/*                />*/}
                    {/*            }*/}
                    {/*            label="Use GPU Acceleration"*/}
                    {/*        />*/}
                    {/*    </Stack>*/}
                    {/*</Box>*/}

                    {/*<Divider />*/}

                    {/* Action Buttons */}
                    <Stack direction="row" spacing={1}>
                        {status !== 'recording' ? (
                            <Button
                                variant="contained"
                                color="error"
                                startIcon={<PlayArrowIcon />}
                                onClick={handleStartRecording}
                                disabled={status === 'processing'}
                            >
                                Start Recording
                            </Button>
                        ) : (
                            <Button
                                variant="contained"
                                color="warning"
                                startIcon={<StopIcon />}
                                onClick={handleStopRecording}
                            >
                                Stop Recording
                            </Button>
                        )}
                        <Button
                            variant="outlined"
                            onClick={handleReset}
                            disabled={status === 'recording' || status === 'processing'}
                            sx={{color: theme.palette.text.primary,
                            borderColor: theme.palette.text.primary}}
                        >
                            Reset
                        </Button>
                    </Stack>
                </Stack>
            </Box>
        </TreeItem>
    );
};
