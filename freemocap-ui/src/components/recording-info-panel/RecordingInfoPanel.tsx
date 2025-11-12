import React, {useEffect, useState} from "react";
import {Box, Typography, useTheme} from "@mui/material";
import {SimpleTreeView} from "@mui/x-tree-view/SimpleTreeView";
import {TreeItem} from "@mui/x-tree-view/TreeItem";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import ChevronRightIcon from "@mui/icons-material/ChevronRight";
import VideocamIcon from "@mui/icons-material/Videocam";
import {
    recordingInfoUpdated,
    startRecording,
    stopRecording,
    useAppDispatch,
    useAppSelector
} from "../../../../../skellycam/skellycam-ui/src/store";
import {
    StartStopRecordingButton
} from "../../../../../skellycam/skellycam-ui/src/components/recording-info-panel/recording-subcomponents/StartStopRecordingButton";
import {
    RecordingPathTreeItem
} from "../../../../../skellycam/skellycam-ui/src/components/recording-info-panel/RecordingPathTreeItem";
import {useElectronIPC} from "../../../../../skellycam/skellycam-ui/src/services/electron-ipc/electron-ipc";

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
    const {isElectron, api} = useElectronIPC();

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

    // replace ~ with user's home directory
    useEffect(() => {
        if (recordingInfo?.recordingDirectory?.startsWith("~") && isElectron && api) {
            api.fileSystem.getHomeDirectory.query()
                .then((homePath: string) => {
                    const updatedDirectory = recordingInfo.recordingDirectory.replace(
                        "~",
                        homePath
                    );
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

    const getTimestampString = (): string => {
        const now = new Date();

        const dateOptions: Intl.DateTimeFormatOptions = {
            year: "numeric",
            month: "2-digit",
            day: "2-digit",
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit",
            hour12: false,
            timeZoneName: "shortOffset",
        };

        const formatter = new Intl.DateTimeFormat("en-US", dateOptions);
        const parts = formatter.formatToParts(now);

        const partMap: Record<string, string> = {};
        parts.forEach((part) => {
            partMap[part.type] = part.value;
        });

        return `${partMap.year}-${partMap.month}-${partMap.day}_${
            partMap.hour
        }-${partMap.minute}-${partMap.second}_${partMap.timeZoneName.replace(
            ":",
            ""
        )}`;
    };

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
        setPendingOperation({ type: 'start', timestamp: Date.now() });

        try {
            await dispatch(
                startRecording({
                    recordingName,
                    recordingDirectory: recordingPath,
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
            setPendingOperation({ type: 'stop', timestamp: Date.now() });

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
        <Box
            sx={{
                color: "text.primary",
                backgroundColor: theme.palette.primary.main,
                borderRadius: 1,
                mx: 1,
                my: 0.5,
            }}
        >
            <SimpleTreeView
                defaultExpandedItems={["recording-main"]}
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
                <TreeItem
                    itemId="recording-main"
                    label={
                        <Box
                            sx={{
                                display: "flex",
                                alignItems: "center",
                                width: "100%",
                                py: 0.25,
                            }}
                        >
                            <VideocamIcon sx={{ fontSize: 16, mr: 0.5 }} />
                            <Typography sx={{ flexGrow: 1, fontSize: 13, fontWeight: 500 }}>
                                Record
                            </Typography>

                            <StartStopRecordingButton
                                isRecording={recordingInfo.isRecording}
                                isPending={pendingOperation !== null}
                                countdown={countdown}
                                recordingStartTime={recordingStartTime}
                                onClick={handleRecordButtonClick}
                            />
                        </Box>
                    }
                >
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
                </TreeItem>
            </SimpleTreeView>
        </Box>
    );
};
