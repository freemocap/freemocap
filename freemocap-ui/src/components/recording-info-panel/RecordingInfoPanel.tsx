import React, { useEffect, useState, useCallback } from "react";
import { Box, Typography, useTheme } from "@mui/material";
import { SimpleTreeView } from "@mui/x-tree-view/SimpleTreeView";
import { TreeItem } from "@mui/x-tree-view/TreeItem";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import ChevronRightIcon from "@mui/icons-material/ChevronRight";
import VideocamIcon from "@mui/icons-material/Videocam";
import {
    recordingInfoUpdated,
    startRecording,
    stopRecording,
    useAppDispatch,
    useAppSelector,
    useDelayStartToggled,
    delaySecondsChanged,
    useTimestampToggled,
    useIncrementToggled,
    currentIncrementChanged,
    currentIncrementIncremented,
    baseNameChanged,
    recordingTagChanged,
    createSubfolderToggled,
    customSubfolderNameChanged,
    pathRecomputed,
} from "@/store";
import {
    StartStopRecordingButton
} from "@/components/recording-info-panel/recording-subcomponents/StartStopRecordingButton";
import { RecordingPathTreeItem } from "@/components/recording-info-panel/RecordingPathTreeItem";
import { useElectronIPC } from "@/services/electron-ipc/electron-ipc";

export const RecordingInfoPanel: React.FC = () => {
    const theme = useTheme();
    const dispatch = useAppDispatch();
    const recordingInfo = useAppSelector((state) => state.recording);
    const { config, computed } = recordingInfo;

    // Only keep countdown as local UI state (ephemeral)
    const [countdown, setCountdown] = useState<number | null>(null);
    const { isElectron, api } = useElectronIPC();

    // Replace ~ with user's home directory
    useEffect(() => {
        if (recordingInfo.recordingDirectory.startsWith("~") && isElectron && api) {
            api.fileSystem.getHomeDirectory.query()
                .then((homePath: string) => {
                    const updatedDirectory = recordingInfo.recordingDirectory.replace("~", homePath);
                    dispatch(recordingInfoUpdated({ recordingDirectory: updatedDirectory }));
                })
                .catch((error: unknown) => {
                    console.error("Failed to get home directory:", error);
                });
        }
    }, [recordingInfo.recordingDirectory, isElectron, api, dispatch]);

    const handleStartRecording = useCallback((): void => {
        console.log("Starting recording...");
        console.log("Recording path:", computed.fullRecordingPath);
        console.log("Recording name:", computed.recordingName);

        if (config.useIncrement) {
            dispatch(currentIncrementIncremented());
        }

        dispatch(
            startRecording({
                recordingName: computed.recordingName,
                recordingDirectory: computed.fullRecordingPath,
            })
        );
    }, [computed.fullRecordingPath, computed.recordingName, config.useIncrement, dispatch]);

    // Handle countdown timer
    useEffect(() => {
        if (countdown !== null && countdown > 0) {
            const timer = setTimeout(() => setCountdown(countdown - 1), 1000);
            return () => clearTimeout(timer);
        } else if (countdown === 0) {
            handleStartRecording();
            setCountdown(null);
        }
    }, [countdown, handleStartRecording]);

    // Update timestamp every second when timestamps are being used
    useEffect(() => {
        const shouldUpdateTimestamp =
            config.useTimestamp ||
            (config.createSubfolder && !config.customSubfolderName);

        if (shouldUpdateTimestamp && !recordingInfo.isRecording) {
            const interval = setInterval(() => {
                dispatch(pathRecomputed());
            }, 1000);

            return () => clearInterval(interval);
        }
    }, [config.useTimestamp, config.createSubfolder, config.customSubfolderName, recordingInfo.isRecording, dispatch]);

    const handleRecordButtonClick = (): void => {
        if (recordingInfo.isRecording) {
            console.log("Stopping recording...");
            dispatch(stopRecording());
        } else if (config.useDelayStart) {
            console.log(`Starting countdown from ${config.delaySeconds} seconds`);
            setCountdown(config.delaySeconds);
        } else {
            handleStartRecording();
        }
    };

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
                            <VideocamIcon sx={{ mr: 1, color: theme.palette.secondary.main }} />
                            <Typography sx={{ flexGrow: 1, fontSize: 13, fontWeight: 500 }}>
                                Record
                            </Typography>

                            <StartStopRecordingButton
                                isRecording={recordingInfo.isRecording}
                                countdown={countdown}
                                onClick={handleRecordButtonClick}
                            />
                        </Box>
                    }
                >
                    <RecordingPathTreeItem
                        countdown={countdown}
                        recordingTag={config.recordingTag}
                        useDelayStart={config.useDelayStart}
                        delaySeconds={config.delaySeconds}
                        useTimestamp={config.useTimestamp}
                        baseName={config.baseName}
                        useIncrement={config.useIncrement}
                        currentIncrement={config.currentIncrement}
                        createSubfolder={config.createSubfolder}
                        customSubfolderName={config.customSubfolderName}
                        isRecording={recordingInfo.isRecording}
                        onDelayToggle={(value: boolean) => dispatch(useDelayStartToggled(value))}
                        onDelayChange={(value: number) => dispatch(delaySecondsChanged(value))}
                        onTagChange={(value: string) => dispatch(recordingTagChanged(value))}
                        onUseTimestampChange={(value: boolean) => dispatch(useTimestampToggled(value))}
                        onBaseNameChange={(value: string) => dispatch(baseNameChanged(value))}
                        onUseIncrementChange={(value: boolean) => dispatch(useIncrementToggled(value))}
                        onIncrementChange={(value: number) => dispatch(currentIncrementChanged(value))}
                        onCreateSubfolderChange={(value: boolean) => dispatch(createSubfolderToggled(value))}
                        onCustomSubfolderNameChange={(value: string) => dispatch(customSubfolderNameChanged(value))}
                    />
                </TreeItem>
            </SimpleTreeView>
        </Box>
    );
};
