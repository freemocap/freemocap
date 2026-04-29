import React, {useEffect, useState} from "react";
import {Box, Checkbox, FormControlLabel, useTheme} from "@mui/material";
import {SimpleTreeView} from "@mui/x-tree-view/SimpleTreeView";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import ChevronRightIcon from "@mui/icons-material/ChevronRight";
import FiberManualRecordIcon from '@mui/icons-material/FiberManualRecord';
import {recordingInfoUpdated, startRecording, stopRecording, useAppDispatch, useAppSelector} from "@/store";
import {
    autoProcessToggled,
    baseNameChanged,
    countdownSet,
    createSubfolderToggled,
    currentIncrementChanged,
    currentIncrementIncremented,
    customSubfolderNameChanged,
    delaySecondsChanged,
    micDeviceIndexChanged,
    pendingOperationSet,
    recordingTagChanged,
    recordingTypePresetChanged,
    useDelayStartToggled,
    useIncrementToggled,
    useTimestampToggled,
} from "@/store/slices/recording/recording-slice";
import type {RecordingTypePreset} from "@/store/slices/recording/recording-types";
import {calibrateRecording} from "@/store/slices/calibration/calibration-thunks";
import {processMocapRecording} from "@/store/slices/mocap/mocap-thunks";
import {PresetPicker} from "@/components/common/PresetPicker";

import {
    MicrophoneSelector
} from "@/components/control-panels/recording-info-panel/recording-subcomponents/MicrophoneSelector";
import {RecordingPathTreeItem} from "@/components/control-panels/recording-info-panel/RecordingPathTreeItem";
import {useElectronIPC} from "@/services/electron-ipc/electron-ipc";
import {useServer} from "@/services/server/ServerContextProvider";
import {getTimestampString} from "@/components/control-panels/recording-info-panel/getTimestampString";
import {CollapsibleSidebarSection} from "@/components/common/CollapsibleSidebarSection";
import {RecordingSummary} from "./RecordingSummary";
import {RecordingHeaderButton} from "./RecordingHeaderButton";

export type {RecordingTypePreset};

export const RECORDING_TYPE_OPTIONS: { value: RecordingTypePreset; label: string }[] = [
    {value: "none", label: "None"},
    {value: "calibration", label: "Calibration"},
    {value: "mocap", label: "Mocap"},
];

const formatDuration = (startedAt: string | null): string => {
    if (!startedAt) return "";
    const seconds = Math.floor((Date.now() - new Date(startedAt).getTime()) / 1000);
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    const parts: string[] = [];
    if (hours > 0) parts.push(hours.toString().padStart(2, '0'));
    parts.push(minutes.toString().padStart(2, '0'));
    parts.push(secs.toString().padStart(2, '0'));
    return parts.join(':');
};

export const RecordingInfoPanel: React.FC = () => {
    const theme = useTheme();
    const dispatch = useAppDispatch();
    const recordingInfo = useAppSelector((state) => state.recording);
    const {config, pendingOperation, countdown} = recordingInfo;
    const {
        createSubfolder,
        useDelayStart,
        delaySeconds,
        useTimestamp,
        useIncrement,
        currentIncrement,
        baseName,
        customSubfolderName,
        recordingTag,
        micDeviceIndex,
        recordingTypePreset,
        autoProcess,
    } = config;

    const {isElectron, api} = useElectronIPC();
    const {connectedCameraIds} = useServer();
    const noCamerasConnected = connectedCameraIds.length === 0;

    // Duration display is derived from shared startedAt so all panel
    // instances show the same ticking value.
    const [recordingDuration, setRecordingDuration] = useState<string>("");

    // Local wall-clock tick for the name preview — avoids Redux state changes and cascading re-renders
    const [previewTimestamp, setPreviewTimestamp] = useState<string>(() => getTimestampString());
    useEffect(() => {
        if (recordingInfo.isRecording) return;
        const id = setInterval(() => setPreviewTimestamp(getTimestampString()), 1000);
        return () => clearInterval(id);
    }, [recordingInfo.isRecording]);

    // Timeout fallback - clear pending after 5 seconds if thunk hasn't responded
    useEffect(() => {
        if (!pendingOperation) return;
        const timeoutMs = 5000;
        const elapsed = Date.now() - pendingOperation.timestamp;
        const remaining = Math.max(0, timeoutMs - elapsed);
        const timer = setTimeout(() => {
            console.error("Recording " + pendingOperation.type + " operation timed out after " + timeoutMs + "ms");
            dispatch(pendingOperationSet(null));
        }, remaining);
        return () => clearTimeout(timer);
    }, [dispatch, pendingOperation]);

    // Update duration display from shared startedAt
    useEffect(() => {
        if (!recordingInfo.isRecording || !recordingInfo.startedAt) {
            setRecordingDuration("");
            return;
        }
        setRecordingDuration(formatDuration(recordingInfo.startedAt));
        const id = setInterval(() => {
            setRecordingDuration(formatDuration(recordingInfo.startedAt));
        }, 1000);
        return () => clearInterval(id);
    }, [recordingInfo.isRecording, recordingInfo.startedAt]);

    // replace ~ with user's home directory
    useEffect(() => {
        if (recordingInfo?.recordingDirectory?.startsWith("~") && isElectron && api) {
            api.fileSystem.getHomeDirectory.query()
                .then((homePath: string) => {
                    const updatedDirectory = recordingInfo.recordingDirectory.replace(
                        "~",
                        homePath
                    ).replace(/\\/g, "/");
                    dispatch(recordingInfoUpdated({recordingDirectory: updatedDirectory}));
                })
                .catch((error: unknown) => {
                    console.error("Failed to get home directory:", error);
                    throw error; // Fail loudly as per preferences
                });
        }
    }, [recordingInfo.recordingDirectory, isElectron, api, dispatch]);

    // Handle countdown timer
    useEffect(() => {
        if (countdown === null) return;
        if (countdown > 0) {
            const timer = setTimeout(() => dispatch(countdownSet(countdown - 1)), 1000);
            return () => clearTimeout(timer);
        }
        // countdown === 0
        dispatch(countdownSet(null));
        handleStartRecording();
    }, [countdown]);

    const buildRecordingName = (timestampOverride?: string): string => {
        const parts: string[] = [];

        if (useTimestamp) {
            parts.push(timestampOverride ?? getTimestampString());
        } else {
            parts.push(baseName);
        }

        if (recordingTypePreset !== "none") {
            parts.push(recordingTypePreset);
        }

        if (recordingTag) {
            parts.push(recordingTag);
        }

        return parts.join("_");
    };

    const handleStartRecording = async (): Promise<void> => {
        console.log("Starting recording...");

        const recordingName = buildRecordingName();
        const subfolderName = createSubfolder
            ? customSubfolderName || getTimestampString()
            : "";
        const recordingPath = createSubfolder
            ? recordingInfo.recordingDirectory + "/" + subfolderName
            : recordingInfo.recordingDirectory;

        console.log("Recording path:", recordingPath);
        console.log("Recording name:", recordingName);

        if (useIncrement) {
            dispatch(currentIncrementIncremented());
        }

        dispatch(pendingOperationSet({type: 'start', timestamp: Date.now()}));

        try {
            await dispatch(
                startRecording({
                    recordingName,
                    recordingDirectory: recordingPath,
                    micDeviceIndex,
                })
            ).unwrap();
        } catch (error) {
            console.error("Failed to start recording:", error);
            dispatch(pendingOperationSet(null));
            throw error; // Fail loudly as per preferences
        }
    };

    const handleRecordButtonClick = async (): Promise<void> => {
        if (pendingOperation) {
            return;
        }

        if (recordingInfo.isRecording) {
            console.log("Stopping recording...");
            dispatch(pendingOperationSet({type: 'stop', timestamp: Date.now()}));

            try {
                const result = await dispatch(stopRecording()).unwrap();
                if (result && autoProcess && recordingTypePreset === "calibration") {
                    dispatch(calibrateRecording());
                } else if (result && autoProcess && recordingTypePreset === "mocap") {
                    dispatch(processMocapRecording());
                }
            } catch (error) {
                console.error("Failed to stop recording:", error);
                dispatch(pendingOperationSet(null));
                throw error; // Fail loudly as per preferences
            }
        } else if (useDelayStart) {
            console.log("Starting countdown from " + delaySeconds + " seconds");
            dispatch(countdownSet(delaySeconds));
        } else {
            await handleStartRecording();
        }
    };

    const recordingName = buildRecordingName(previewTimestamp);
    const subfolderName = createSubfolder
        ? customSubfolderName || previewTimestamp
        : undefined;

    return (
        <CollapsibleSidebarSection
            icon={<FiberManualRecordIcon sx={{color: "inherit"}}/>}
            title={"Recording"}
            summaryContent={
                <RecordingSummary
                    isRecording={recordingInfo.isRecording}
                    recordingDuration={recordingDuration}
                />
            }
            primaryControl={
                <RecordingHeaderButton
                    isRecording={recordingInfo.isRecording}
                    isPending={pendingOperation !== null}
                    disabled={noCamerasConnected && !recordingInfo.isRecording}
                    onClick={handleRecordButtonClick}
                />
            }
            secondaryControls={
                <Box sx={{display: 'flex', alignItems: 'center', gap: 0.5}}>
                    <PresetPicker
                        value={recordingTypePreset}
                        options={RECORDING_TYPE_OPTIONS}
                        onChange={(v) => dispatch(recordingTypePresetChanged(v))}
                        disabled={recordingInfo.isRecording}
                        size="small"
                        minWidth={70}
                        sx={{
                            '& .MuiSelect-select': {py: 0.25, fontSize: 11, color: 'inherit'},
                            '& .MuiOutlinedInput-notchedOutline': {borderColor: 'rgba(255,255,255,0.3)'},
                            '& .MuiSvgIcon-root': {color: 'inherit', fontSize: 14},
                        }}
                    />
                    <FormControlLabel
                        control={
                            <Checkbox
                                checked={autoProcess}
                                onChange={(e) => dispatch(autoProcessToggled(e.target.checked))}
                                disabled={recordingTypePreset === "none" || recordingInfo.isRecording}
                                size="small"
                                sx={{py: 0, '& .MuiSvgIcon-root': {fontSize: 14}}}
                            />
                        }
                        label="Auto Process"
                        sx={{
                            ml: 0,
                            mr: 0,
                            '& .MuiFormControlLabel-label': {
                                fontSize: 10,
                                opacity: recordingTypePreset === "none" ? 0.5 : 1,
                            },
                        }}
                    />
                </Box>
            }
            defaultExpanded={false}
        >
            <Box
                sx={{
                    color: "text.primary",
                    backgroundColor: theme.palette.background.paper,
                    borderRadius: 1,
                    mx: 1,
                    my: 0.5,
                }}
            >
                <SimpleTreeView
                    defaultExpandedItems={["recording-settings"]}
                    slots={{
                        collapseIcon: ExpandMoreIcon,
                        expandIcon: ChevronRightIcon,
                    }}
                    sx={{
                        flexGrow: 1,
                        '& .MuiTreeItem-content': {
                            padding: '2px 4px',
                            margin: '1px 0',
                        },
                        '& .MuiTreeItem-label': {
                            fontSize: 13,
                            padding: '1px 0',
                        },
                    }}
                >
                    <Box sx={{px: 1, py: 1}}>
                        <MicrophoneSelector
                            selectedMicIndex={micDeviceIndex}
                            onMicSelected={(idx) => dispatch(micDeviceIndexChanged(idx))}
                            disabled={recordingInfo.isRecording}
                        />
                    </Box>

                    <RecordingPathTreeItem
                        recordingDirectory={recordingInfo.recordingDirectory}
                        recordingName={recordingName}
                        subfolder={subfolderName}
                        countdown={countdown}
                        recordingTag={recordingTag}
                        useDelayStart={useDelayStart}
                        delaySeconds={delaySeconds}
                        useTimestamp={useTimestamp}
                        baseName={baseName}
                        useIncrement={useIncrement}
                        currentIncrement={currentIncrement}
                        createSubfolder={createSubfolder}
                        customSubfolderName={customSubfolderName}
                        isRecording={recordingInfo.isRecording}
                        onDelayToggle={(v) => dispatch(useDelayStartToggled(v))}
                        onDelayChange={(v) => dispatch(delaySecondsChanged(v))}
                        onTagChange={(v) => dispatch(recordingTagChanged(v))}
                        onUseTimestampChange={(v) => dispatch(useTimestampToggled(v))}
                        onBaseNameChange={(v) => dispatch(baseNameChanged(v))}
                        onUseIncrementChange={(v) => dispatch(useIncrementToggled(v))}
                        onIncrementChange={(v) => dispatch(currentIncrementChanged(v))}
                        onCreateSubfolderChange={(v) => dispatch(createSubfolderToggled(v))}
                        onCustomSubfolderNameChange={(v) => dispatch(customSubfolderNameChanged(v))}
                    />
                </SimpleTreeView>
            </Box>
        </CollapsibleSidebarSection>
    );
};
