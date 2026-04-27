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
import LaunchIcon from "@mui/icons-material/Launch";
import ClearIcon from "@mui/icons-material/Clear";
import RefreshIcon from "@mui/icons-material/Refresh";
import {useMocap} from "@/hooks/useMocap";
import {useCalibration} from "@/hooks/useCalibration";
import {useDirectoryWatcher} from "@/hooks/useDirectoryWatcher";
import {useElectronIPC} from "@/services";
import {CalibrationTomlPicker} from "@/components/common/CalibrationTomlPicker";
import {RealtimePipelineConfigTree} from "@/components/control-panels/realtime-panel/RealtimePipelineConfigTree";
import {useServer} from "@/services/server/ServerContextProvider";
import SquareFootIcon from "@mui/icons-material/SquareFoot";
import {CollapsibleSidebarSection} from "@/components/common/CollapsibleSidebarSection";
import {BlenderSection} from "@/components/control-panels/mocap-control-panel/BlenderSection";
import {RecordingStatusPanel} from "@/components/common/RecordingStatusPanel";
import {useRecordingStatus} from "@/hooks/useRecordingStatus";
import {selectPlannedRecordingName, selectPlannedRecordingDirectory} from "@/store/slices/recording";
import {selectEffectiveRecordingPath} from "@/store/slices/active-recording/active-recording-slice";
import {useAppSelector} from "@/store";

export const MocapPanel: React.FC = () => {
    const theme = useTheme();
    const {setOverlayVisibility} = useServer();
    const [localError, setLocalError] = useState<string | null>(null);
    const {api, isElectron} = useElectronIPC();

    const {
        error,
        isLoading,
        isRecording,
        recordingProgress,
        processingProgress,
        processingPhase,
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

    // Planned recording info (potential recording when no actual recording exists)
    const plannedName = useAppSelector(selectPlannedRecordingName);
    const plannedDirectory = useAppSelector(selectPlannedRecordingDirectory);

    // Effective path: actual activeRecording if any, otherwise the planned path
    const effectiveMocapPath = useAppSelector(selectEffectiveRecordingPath);

    // Determine if we're showing a pending (not yet created) recording
    const isPendingRecording = !mocapRecordingPath && !!plannedName;

    // Derive recording ID from path (last folder name) - works for both actual and planned
    const recordingId = useMemo(() => {
        if (mocapRecordingPath) {
            const parts = mocapRecordingPath.replace(/[/\\]+$/, "").split(/[/\\]/);
            return parts[parts.length - 1] || null;
        }
        // Fall back to planned name if no actual recording
        return plannedName || null;
    }, [mocapRecordingPath, plannedName]);

    // Derive parent directory so the backend can resolve non-default recording roots
    const recordingParentDirectory = useMemo(() => {
        if (mocapRecordingPath) {
            const trimmed = mocapRecordingPath.replace(/[/\\]+$/, "");
            const idx = Math.max(trimmed.lastIndexOf("/"), trimmed.lastIndexOf("\\"));
            return idx > 0 ? trimmed.slice(0, idx) : null;
        }
        // Fall back to planned directory
        return plannedDirectory || null;
    }, [mocapRecordingPath, plannedDirectory]);

    // Blender export is driven by the backend aggregator via config flags
    // (state.blender.*), which mocap-thunks.ts folds into the process request.
    // The standalone "Process Recording with Blender" button inside
    // BlenderSection remains available for manual re-exports.

    // Auto-poll directory status
    const {triggerRefresh} = useDirectoryWatcher(
        mocapRecordingPath,
        validateDirectory,
        3000,
    );

    // Pipeline stage toggles (local state — posthoc pipeline stages)
    const [charucoEnabled, setCharucoEnabled] = useState(true);
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

    const handleOpenFolder = async (): Promise<void> => {
        if (!isElectron || !api || !effectiveMocapPath) return;
        try {
            await api.fileSystem.openFolder.mutate({path: effectiveMocapPath});
        } catch (err) {
            console.error("Failed to open folder:", err);
            setLocalError("Failed to open folder in file explorer");
        }
    };

    const handlePathInputChange = async (
        e: React.ChangeEvent<HTMLInputElement>,
    ): Promise<void> => {
        const newPath: string = e.target.value;
        if (newPath.includes("~") && isElectron && api) {
            try {
                const home: string = await api.fileSystem.getHomeDirectory.query();
                const expanded: string = newPath.replace(/^~([/\\])?/, home ? home + '$1' : "");
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

    // Only auto-fetch if the folder exists on disk — otherwise recordingId
    // may tick every second (default path embeds a timestamp) and we'd spam
    // the backend with 404s for folders that don't exist yet.
    const directoryExists = directoryInfo?.exists ?? false;
    const {
        status: recordingStatus,
        isLoading: recordingStatusLoading,
        error: recordingStatusError,
        refresh: refreshRecordingStatus,
    } = useRecordingStatus(recordingId, {
        recordingParentDirectory,
        autoFetch: directoryExists,
    });

    const formatPhase = (phase: string): string => {
        const labels: Record<string, string> = {
            detecting_frames: "Detecting",
            collecting_frames: "Collecting",
            all_frames_collected: "Collected",
            running_task: "Processing",
            complete: "Done",
            failed: "Failed",
        };
        return labels[phase] ?? "Processing";
    };

    const statusLabel = isRecording
        ? "Recording " + recordingProgress.toFixed(0) + "%"
        : isLoading
            ? formatPhase(processingPhase) + " " + processingProgress + "%"
            : isPendingRecording
                ? "Pending"
                : effectiveCalibrationTomlPath
                    ? "Ready"
                    : "Idle";

    const statusColor = isRecording
        ? theme.palette.error.main
        : isLoading
            ? theme.palette.warning.main
            : isPendingRecording
                ? theme.palette.grey[500]
                : effectiveCalibrationTomlPath
                    ? theme.palette.success.main
                    : theme.palette.grey[600];

    return (
        <CollapsibleSidebarSection
            icon={<DirectionsRunIcon sx={{color: "inherit"}}/>}
            title="Motion Capture"
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
                            <Stack direction="row" spacing={1} alignItems="center">
                                <Typography variant="caption" color="text.secondary">
                                    Recording ID
                                </Typography>
                                {isPendingRecording && (
                                    <Chip
                                        label="Pending capture"
                                        size="small"
                                        variant="outlined"
                                        sx={{height: 18, fontSize: '0.65rem', borderStyle: 'dashed', opacity: 0.7}}
                                    />
                                )}
                            </Stack>
                            <Typography variant="body2" sx={{fontFamily: "monospace", fontWeight: 600}}>
                                {recordingId}
                            </Typography>
                        </Box>
                    )}

                    {/*/!* Recording Controls *!/*/}
                    {/* TODO - Wire up these recording buttons to the EXACT same workflow as the recording panel  - current wiring has slop*/}
                    {/*<Stack direction="row" spacing={2}>*/}
                    {/*    <Button*/}
                    {/*        variant="contained"*/}
                    {/*        color="primary"*/}
                    {/*        startIcon={<PlayArrowIcon />}*/}
                    {/*        onClick={dispatchStartMocapRecording}*/}
                    {/*        // disabled={!canStartRecording || isLoading}*/}
                    {/*        disabled={isLoading}*/}
                    {/*        fullWidth*/}
                    {/*    >*/}
                    {/*        Start Mocap Recording*/}
                    {/*    </Button>*/}
                    {/*    {isRecording && (*/}
                    {/*        <Button*/}
                    {/*            variant="contained"*/}
                    {/*            color="error"*/}
                    {/*            startIcon={<StopIcon />}*/}
                    {/*            onClick={dispatchStopMocapRecording}*/}
                    {/*            disabled={isLoading}*/}
                    {/*            fullWidth*/}
                    {/*        >*/}
                    {/*            Stop Recording*/}
                    {/*        </Button>*/}
                    {/*    )}*/}
                    {/*</Stack>*/}

                    {/* Recording Path Input */}
                    <TextField
                        label="Mocap Recording Path"
                        value={effectiveMocapPath || ''}
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
                                                <ClearIcon fontSize="small" />
                                            </IconButton>
                                        </Tooltip>
                                    )}
                                    <Tooltip title="Re-check folder">
                                        <span>
                                            <IconButton
                                                onClick={() => {
                                                    triggerRefresh();
                                                    refreshRecordingStatus();
                                                }}
                                                edge="end"
                                                size="small"
                                                disabled={!mocapRecordingPath || isLoading}
                                            >
                                                <RefreshIcon fontSize="small" />
                                            </IconButton>
                                        </span>
                                    </Tooltip>
                                    <Tooltip title="Open folder in file explorer">
                                        <span>
                                            <IconButton
                                                onClick={handleOpenFolder}
                                                edge="end"
                                                size="small"
                                                disabled={!isElectron || !effectiveMocapPath}
                                            >
                                                <LaunchIcon fontSize="small" />
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

                    {/* Recording folder status (collapsed by default) */}
                    {recordingId && !isPendingRecording && (
                        <RecordingStatusPanel
                            status={recordingStatus}
                            isLoading={recordingStatusLoading}
                            error={recordingStatusError}
                            onRefresh={() => {
                                triggerRefresh();
                                refreshRecordingStatus();
                            }}
                            activeCalibrationTomlPath={effectiveCalibrationTomlPath}
                            folderExists={directoryExists}
                            recordingFolderPath={mocapRecordingPath}
                        />
                    )}

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
                                        width: recordingProgress + "%",
                                        height: "100%",
                                        bgcolor: theme.palette.primary.main,
                                        transition: "width 0.3s",
                                    }}
                                />
                            </Box>
                        </Box>
                    )}

                    {/* Processing Progress */}
                    {isLoading && !isRecording && processingProgress > 0 && (
                        <Box sx={{width: "100%"}}>
                            <Typography variant="caption" color="text.secondary" gutterBottom>
                                {formatPhase(processingPhase)}: {processingProgress}%
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
                                        width: processingProgress + "%",
                                        height: "100%",
                                        bgcolor: theme.palette.warning.main,
                                        transition: "width 0.4s",
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

                    <BlenderSection
                        recordingFolderPath={mocapRecordingPath}
                        disabled={isLoading}
                        hasBlendFile={recordingStatus?.has_blend_file}
                    />
                </Stack>
            </Box>
        </CollapsibleSidebarSection>
    );
};
