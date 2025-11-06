import React, { useEffect, useState } from "react";
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
    const { config } = recordingInfo;

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

        return `${partMap.year}-${partMap.month}-${partMap.day}_${partMap.hour}-${partMap.minute}-${partMap.second}_${partMap.timeZoneName.replace(":", "")}`;
    };

    const buildRecordingName = (): string => {
        const parts: string[] = [];

        if (config.useTimestamp) {
            parts.push(getTimestampString());
        } else {
            parts.push(config.baseName);
        }

        if (config.recordingTag) {
            parts.push(config.recordingTag);
        }

        return parts.join("_");
    };

    const handleStartRecording = (): void => {
        console.log("Starting recording...");

        const recordingName = buildRecordingName();
        const subfolderName = config.createSubfolder
            ? config.customSubfolderName || getTimestampString()
            : "";
        const recordingPath = config.createSubfolder
            ? `${recordingInfo.recordingDirectory}/${subfolderName}`
            : recordingInfo.recordingDirectory;

        console.log("Recording path:", recordingPath);
        console.log("Recording name:", recordingName);

        if (config.useIncrement) {
            dispatch(currentIncrementIncremented());
        }

        dispatch(
            startRecording({
                recordingName,
                recordingDirectory: recordingPath,
            })
        );
    };

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

    const recordingName = buildRecordingName();
    const subfolderName = config.createSubfolder
        ? config.customSubfolderName || getTimestampString()
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
                        recordingDirectory={recordingInfo.recordingDirectory}
                        recordingName={recordingName}
                        subfolder={subfolderName}
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
