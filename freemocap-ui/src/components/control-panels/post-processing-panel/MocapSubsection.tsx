import React, {useCallback, useEffect, useMemo, useState} from "react";
import {
    Accordion,
    AccordionDetails,
    AccordionSummary,
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
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import DirectionsRunIcon from "@mui/icons-material/DirectionsRun";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import StopIcon from "@mui/icons-material/Stop";
import FolderOpenIcon from "@mui/icons-material/FolderOpen";
import ClearIcon from "@mui/icons-material/Clear";
import RefreshIcon from "@mui/icons-material/Refresh";
import {DirectoryStatusPanel} from "@/components/common/DirectoryStatusPanel";
import {useMocap} from "@/hooks/useMocap";
import {useCalibration} from "@/hooks/useCalibration";
import {useDirectoryWatcher} from "@/hooks/useDirectoryWatcher";
import {useElectronIPC} from "@/services";
import {CalibrationTomlPicker} from "@/components/common/CalibrationTomlPicker";
import {RealtimePipelineConfigTree} from "@/components/control-panels/realtime-panel/RealtimePipelineConfigTree";
import {useServer} from "@/services/server/ServerContextProvider";

export const MocapSubsection: React.FC = () => {
    const theme = useTheme();
    const {setOverlayVisibility} = useServer();
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
        validateDirectory,
        calibrationTomlPath,
        setCalibrationTomlPath,
        clearCalibrationTomlPath,
        clearError,
    } = useMocap();

    const {
        directoryInfo: calibrationDirectoryInfo,
    } = useCalibration();

    // Auto-poll directory status
    const {triggerRefresh} = useDirectoryWatcher(
        mocapRecordingPath,
        validateDirectory,
        3000,
    );

    // Pipeline stage toggles (local state — posthoc pipeline stages)
    const [charucoEnabled, setCharucoEnabled] = useState(false);
    const [skeletonEnabled, setSkeletonEnabled] = useState(true);

    useEffect(() => {
        setOverlayVisibility(charucoEnabled, skeletonEnabled);
    }, [charucoEnabled, skeletonEnabled, setOverlayVisibility]);
    const [triangulateEnabled, setTriangulateEnabled] = useState(true);
    const [filterEnabled, setFilterEnabled] = useState(true);
    const [rigidBodyEnabled, setRigidBodyEnabled] = useState(true);

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

    const handlePathInputChange = async (
        e: React.ChangeEvent<HTMLInputElement>,
    ): Promise<void> => {
        const newPath: string = e.target.value;
        if (newPath.includes("~") && isElectron && api) {
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

    const handleSelectCalibrationToml = async (): Promise<void> => {
        if (!isElectron || !api) return;
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

    const effectiveCalibrationTomlPath = useMemo(() => {
        if (calibrationTomlPath) return calibrationTomlPath;
        if (directoryInfo?.cameraMocapTomlPath) return directoryInfo.cameraMocapTomlPath;
        if (calibrationDirectoryInfo?.cameraCalibrationTomlPath) return calibrationDirectoryInfo.cameraCalibrationTomlPath;
        if (directoryInfo?.lastSuccessfulCalibrationTomlPath) return directoryInfo.lastSuccessfulCalibrationTomlPath;
        return null;
    }, [calibrationTomlPath, directoryInfo?.cameraMocapTomlPath, calibrationDirectoryInfo?.cameraCalibrationTomlPath, directoryInfo?.lastSuccessfulCalibrationTomlPath]);

    const tomlSource = useMemo(() => {
        if (calibrationTomlPath) return "manual" as const;
        if (directoryInfo?.cameraMocapTomlPath) return "auto" as const;
        if (calibrationDirectoryInfo?.cameraCalibrationTomlPath) return "calibration-panel" as const;
        if (directoryInfo?.lastSuccessfulCalibrationTomlPath) return "last-successful" as const;
        return "auto" as const;
    }, [calibrationTomlPath, directoryInfo?.cameraMocapTomlPath, calibrationDirectoryInfo?.cameraCalibrationTomlPath, directoryInfo?.lastSuccessfulCalibrationTomlPath]);

    const mocapStatus: "ok" | "none" | "bad" = useMemo(() => {
        if (effectiveCalibrationTomlPath) return "ok";
        if (!mocapRecordingPath || !directoryInfo) return "none";
        return "bad";
    }, [effectiveCalibrationTomlPath, mocapRecordingPath, directoryInfo]);

    const displayError = error || localError || directoryInfo?.errorMessage;

    // Derive recording ID from path (last folder name)
    const recordingId = useMemo(() => {
        if (!mocapRecordingPath) return null;
        const parts = mocapRecordingPath.replace(/[/\\]+$/, "").split(/[/\\]/);
        return parts[parts.length - 1] || null;
    }, [mocapRecordingPath]);

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

    return (
        <Accordion defaultExpanded={false} disableGutters>
            <AccordionSummary
                expandIcon={<ExpandMoreIcon />}
                sx={{
                    minHeight: 40,
                    "& .MuiAccordionSummary-content": {
                        alignItems: "center",
                        gap: 1,
                        my: 0.5,
                    },
                }}
            >
                <DirectionsRunIcon fontSize="small" sx={{color: theme.palette.text.secondary}} />
                <Typography variant="subtitle2">Motion Capture</Typography>
                <Chip
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
                />
            </AccordionSummary>
            <AccordionDetails sx={{p: 2}}>
                <Stack spacing={2}>
                    {/* Process button at TOP per requirements */}
                    <Button
                        variant="contained"
                        color="secondary"
                        onClick={dispatchProcessMocapRecording}
                        disabled={!canProcessMocapRecording || isLoading}
                        fullWidth
                    >
                        Process Selected Recording
                    </Button>

                    {displayError && (
                        <Alert severity="error" onClose={handleClearError}>
                            {displayError}
                        </Alert>
                    )}

                    {/* Recording ID — prominent at top level */}
                    {recordingId && (
                        <Box sx={{
                            p: 1,
                            borderRadius: 1,
                            bgcolor: theme.palette.action.hover,
                        }}>
                            <Typography variant="caption" color="text.secondary">
                                Recording ID
                            </Typography>
                            <Typography variant="body2" sx={{fontFamily: "monospace", fontWeight: 600}}>
                                {recordingId}
                            </Typography>
                        </Box>
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
                        helperText={isUsingManualPath ? "Using custom path" : "Using default recording directory"}
                        InputProps={{
                            endAdornment: (
                                <InputAdornment position="end">
                                    {isUsingManualPath && (
                                        <Tooltip title="Clear manual path (revert to default)">
                                            <IconButton onClick={clearManualRecordingPath} edge="end" size="small">
                                                <ClearIcon fontSize="small" />
                                            </IconButton>
                                        </Tooltip>
                                    )}
                                    <Tooltip title="Re-check folder">
                                        <span>
                                            <IconButton
                                                onClick={triggerRefresh}
                                                edge="end"
                                                size="small"
                                                disabled={!mocapRecordingPath || isLoading}
                                            >
                                                <RefreshIcon fontSize="small" />
                                            </IconButton>
                                        </span>
                                    </Tooltip>
                                    <Tooltip title="Select directory">
                                        <IconButton onClick={handleSelectDirectory} edge="end" disabled={!isElectron}>
                                            <FolderOpenIcon />
                                        </IconButton>
                                    </Tooltip>
                                </InputAdornment>
                            ),
                        }}
                    />

                    {/* Directory Status (auto-refreshing) */}
                    <DirectoryStatusPanel
                        title="Mocap Folder Status"
                        tomlLabel="Has calibration TOML"
                        directoryInfo={directoryInfo ? {
                            ...directoryInfo,
                            tomlPath: directoryInfo.cameraMocapTomlPath,
                        } : null}
                        status={mocapStatus}
                        onRefresh={triggerRefresh}
                        refreshDisabled={!mocapRecordingPath || isLoading}
                        isRefreshing={false}
                    />

                    {/* Calibration TOML — redesigned compact picker */}
                    <CalibrationTomlPicker
                        tomlPath={effectiveCalibrationTomlPath}
                        source={tomlSource}
                        onSelect={handleSelectCalibrationToml}
                        onUseAutoDetected={clearCalibrationTomlPath}
                        disabled={!isElectron}
                    />

                    {/* Recording Progress */}
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

                    {/* Hierarchical pipeline config (replaces flat MediapipeConfigPanel + SkeletonFilterConfigPanel) */}
                    <RealtimePipelineConfigTree
                        context="posthoc"
                        charucoEnabled={charucoEnabled}
                        onCharucoToggle={setCharucoEnabled}
                        skeletonEnabled={skeletonEnabled}
                        onSkeletonToggle={setSkeletonEnabled}
                        triangulateEnabled={triangulateEnabled}
                        onTriangulateToggle={setTriangulateEnabled}
                        filterEnabled={filterEnabled}
                        onFilterToggle={setFilterEnabled}
                        rigidBodyEnabled={rigidBodyEnabled}
                        onRigidBodyToggle={setRigidBodyEnabled}
                    />
                </Stack>
            </AccordionDetails>
        </Accordion>
    );
};
