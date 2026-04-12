import React, {useEffect, useState} from "react";
import {Box, useTheme} from "@mui/material";
import {SimpleTreeView} from "@mui/x-tree-view/SimpleTreeView";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import ChevronRightIcon from "@mui/icons-material/ChevronRight";
import FiberManualRecordIcon from '@mui/icons-material/FiberManualRecord';
import {recordingInfoUpdated, startRecording, stopRecording, useAppDispatch, useAppSelector} from "@/store";
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

interface RecordingOperation {
    type: 'start' | 'stop';
    timestamp: number;
}

export const RecordingInfoPanel: React.FC = () => {
    const theme = useTheme();
    const dispatch = useAppDispatch();
    const recordingInfo = useAppSelector(
        (state) => state.recording
    );

    // Local UI state
    const [createSubfolder, setCreateSubfolder] = useState<boolean>(false);
    const [useDelayStart, setUseDelayStart] = useState<boolean>(false);
    const [delaySeconds, setDelaySeconds] = useState<number>(3);
    const [countdown, setCountdown] = useState<number | null>(null);

    // Track pending operation and recording start time
    const [pendingOperation, setPendingOperation] = useState<RecordingOperation | null>(null);
    const [recordingStartTime, setRecordingStartTime] = useState<number | null>(null);

    // Local recording naming
    const [useTimestamp, setUseTimestamp] = useState<boolean>(true);
    const [useIncrement, setUseIncrement] = useState<boolean>(false);
    const [currentIncrement, setCurrentIncrement] = useState<number>(1);
    const [baseName, setBaseName] = useState<string>("recording");
    const [customSubfolderName, setCustomSubfolderName] = useState<string>("");
    const [recordingTag, setRecordingTag] = useState<string>("");
    const [micDeviceIndex, setMicDeviceIndex] = useState<number>(-1);
    const {isElectron, api} = useElectronIPC();
    const {connectedCameraIds} = useServer();
    const noCamerasConnected = connectedCameraIds.length === 0;

    // Recording duration for summary
    const [recordingDuration, setRecordingDuration] = useState<string>("");

    // Track when recording state changes to clear pending state
    useEffect(() => {
        if (pendingOperation) {
            const isNowRecording = recordingInfo.isRecording;
            const wasStarting = pendingOperation.type === 'start';
            const wasStopping = pendingOperation.type === 'stop';

            // Clear pending if state changed as expected
            if ((wasStarting && isNowRecording) || (wasStopping && !isNowRecording)) {
                setPendingOperation(null);

                // Set or clear recording start time
                if (wasStarting && isNowRecording) {
                    setRecordingStartTime(Date.now());
                } else if (wasStopping && !isNowRecording) {
                    setRecordingStartTime(null);
                    setRecordingDuration("");
                }
            }

            // Timeout fallback - clear pending after 5 seconds if thunk hasn't responded
            const timeoutMs = 5000;
            const elapsed = Date.now() - pendingOperation.timestamp;
            if (elapsed > timeoutMs) {
                console.error(`Recording ${pendingOperation.type} operation timed out after ${timeoutMs}ms`);
                setPendingOperation(null);
            }
        }
    }, [recordingInfo.isRecording, pendingOperation]);

    // Set initial recording start time if already recording on mount
    useEffect(() => {
        if (recordingInfo.isRecording && !recordingStartTime) {
            setRecordingStartTime(Date.now());
        }
    }, []);

    // Update recording duration display
    useEffect(() => {
        if (!recordingInfo.isRecording || !recordingStartTime) {
            setRecordingDuration("");
            return;
        }

        const updateDuration = (): void => {
            const now = Date.now();
            const seconds = Math.floor((now - recordingStartTime) / 1000);
            const hours = Math.floor(seconds / 3600);
            const minutes = Math.floor((seconds % 3600) / 60);
            const secs = seconds % 60;
            
            const parts: string[] = [];
            if (hours > 0) {
                parts.push(hours.toString().padStart(2, '0'));
            }
            parts.push(minutes.toString().padStart(2, '0'));
            parts.push(secs.toString().padStart(2, '0'));
            setRecordingDuration(parts.join(':'));
        };

        updateDuration();
        const interval = setInterval(updateDuration, 1000);
        return () => clearInterval(interval);
    }, [recordingInfo.isRecording, recordingStartTime]);

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
        if (countdown !== null && countdown > 0) {
            const timer = setTimeout(() => setCountdown(countdown - 1), 1000);
            return () => clearTimeout(timer);
        } else if (countdown === 0) {
            handleStartRecording();
            setCountdown(null);
        }
    }, [countdown]);

    const handleRecordingTagChange = (tag: string): void => {
        setRecordingTag(tag);
    };

    const buildRecordingName = (): string => {
        const parts: string[] = [];

        if (useTimestamp) {
            parts.push(getTimestampString());
        } else {
            parts.push(baseName);
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
            ? `${recordingInfo.recordingDirectory}/${subfolderName}`
            : recordingInfo.recordingDirectory;

        console.log("Recording path:", recordingPath);
        console.log("Recording name:", recordingName);

        if (useIncrement) {
            setCurrentIncrement((prev) => prev + 1);
        }

        // Set pending state before dispatching
        setPendingOperation({type: 'start', timestamp: Date.now()});

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
            setPendingOperation(null);
            throw error; // Fail loudly as per preferences
        }
    };

    const handleRecordButtonClick = async (): Promise<void> => {
        // Don't allow clicking while pending
        if (pendingOperation) {
            return;
        }

        if (recordingInfo.isRecording) {
            console.log("Stopping recording...");
            setPendingOperation({type: 'stop', timestamp: Date.now()});

            try {
                await dispatch(stopRecording()).unwrap();
            } catch (error) {
                console.error("Failed to stop recording:", error);
                setPendingOperation(null);
                throw error; // Fail loudly as per preferences
            }
        } else if (useDelayStart) {
            console.log(`Starting countdown from ${delaySeconds} seconds`);
            setCountdown(delaySeconds);
        } else {
            await handleStartRecording();
        }
    };

    const recordingName = buildRecordingName();
    const subfolderName = createSubfolder
        ? customSubfolderName || getTimestampString()
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
                    {/* Full recording button in expanded content */}
                    <Box sx={{ px: 1, py: 1 }}>
                        {/* Microphone selector */}
                        <MicrophoneSelector
                            selectedMicIndex={micDeviceIndex}
                            onMicSelected={setMicDeviceIndex}
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
                        onDelayToggle={setUseDelayStart}
                        onDelayChange={setDelaySeconds}
                        onTagChange={handleRecordingTagChange}
                        onUseTimestampChange={setUseTimestamp}
                        onBaseNameChange={setBaseName}
                        onUseIncrementChange={setUseIncrement}
                        onIncrementChange={setCurrentIncrement}
                        onCreateSubfolderChange={setCreateSubfolder}
                        onCustomSubfolderNameChange={setCustomSubfolderName}
                    />
                </SimpleTreeView>
            </Box>
        </CollapsibleSidebarSection>
    );
};
