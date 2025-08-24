import React, {useEffect, useState} from "react";
import {Box, Typography, useTheme} from "@mui/material";
import {SimpleTreeView} from "@mui/x-tree-view/SimpleTreeView";
import {TreeItem} from "@mui/x-tree-view/TreeItem";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import ChevronRightIcon from "@mui/icons-material/ChevronRight";
import VideocamIcon from "@mui/icons-material/Videocam";
import {useAppDispatch, useAppSelector} from "@/store/AppStateStore";
import {
    StartStopRecordingButton
} from "@/components/recording-info-panel/recording-subcomponents/StartStopRecordingButton";
import {startRecording, stopRecording,} from "@/store/thunks/start-stop-recording-thunks";
import {setRecordingInfo} from "@/store/slices/recordingInfoSlice";
import {RecordingPathTreeItem} from "@/components/recording-info-panel/RecordingPathTreeItem";
import {FullRecordingPathPreview} from "./recording-subcomponents/FullRecordingPathPreview";

export const RecordingInfoPanel: React.FC = () => {
    const theme = useTheme();
    const dispatch = useAppDispatch();
    const recordingInfo = useAppSelector(
        (state) => state.recordingStatus.currentRecordingInfo
    );

    // Local UI state
    const [createSubfolder, setCreateSubfolder] = useState(false);
    const [useDelayStart, setUseDelayStart] = useState(false);
    const [delaySeconds, setDelaySeconds] = useState(3);
    const [countdown, setCountdown] = useState<number | null>(null);

    // Local recording naming
    const [useTimestamp, setUseTimestamp] = useState(true);
    const [useIncrement, setUseIncrement] = useState(false);
    const [currentIncrement, setCurrentIncrement] = useState(1);
    const [baseName, setBaseName] = useState("recording");
    const [customSubfolderName, setCustomSubfolderName] = useState("");
    const [recordingTag, setRecordingTag] = useState("");

    // replace ~ with user's home directory
    useEffect(() => {
        if (recordingInfo?.recordingDirectory?.startsWith("~")) {
            window.electronAPI.getHomeDirectory().then((homePath: string) => {
                const updatedDirectory = recordingInfo.recordingDirectory.replace(
                    "~",
                    homePath
                );
                dispatch(setRecordingInfo({recordingDirectory: updatedDirectory}));
            });
        }
    }, [recordingInfo, dispatch]);

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

        // Format date in local time with timezone info
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

        // Get formatted parts
        const formatter = new Intl.DateTimeFormat("en-US", dateOptions);
        const parts = formatter.formatToParts(now);

        // Create a map of the parts for easy access
        const partMap: Record<string, string> = {};
        parts.forEach((part) => {
            partMap[part.type] = part.value;
        });

        // Build the timestamp string in a filename-friendly format
        const timestamp = `${partMap.year}-${partMap.month}-${partMap.day}_${
            partMap.hour
        }-${partMap.minute}-${partMap.second}_${partMap.timeZoneName.replace(
            ":",
            ""
        )}`;

        return timestamp;
    };
    const handleRecordingTagChange = (tag: string) => {
        setRecordingTag(tag);
    };
    const buildRecordingName = (): string => {
        const parts: string[] = [];

        // Base name component
        if (useTimestamp) {
            parts.push(getTimestampString());
        } else {
            parts.push(baseName);
        }

        // Add tag if present
        if (recordingTag) {
            parts.push(recordingTag);
        }

        return parts.join("_");
    };

    const handleStartRecording = () => {
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

        dispatch(
            startRecording({
                recordingName,
                recordingDirectory: recordingPath,
            })
        );
    };

    const handleRecordButtonClick = () => {
        if (recordingInfo.isRecording) {
            console.log("Stopping recording...");
            dispatch(stopRecording());
        } else if (useDelayStart) {
            console.log(`Starting countdown from ${delaySeconds} seconds`);
            setCountdown(delaySeconds);
        } else {
            handleStartRecording();
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
                mb: 2,
            }}
        >
            <SimpleTreeView
                defaultExpandedItems={["recording-main"]}
                slots={{
                    collapseIcon: ExpandMoreIcon,
                    expandIcon: ChevronRightIcon,
                }}
                sx={{flexGrow: 1}}
            >
                <TreeItem
                    itemId="recording-main"
                    label={
                        <Box
                            sx={{
                                display: "flex",
                                alignItems: "center",
                                // justifyContent: "space-between",
                                width: "100%",
                                r: 2,
                            }}
                        >
                            <VideocamIcon/>
                            <Typography sx={{pl: 1, flexGrow: 1}} variant="h6" component="div">
                                Record Videos
                            </Typography>


                            <Box sx={{display: "flex", flexGrow:1, pl: 2, alignItems: "left"}}>
                                <StartStopRecordingButton
                                    isRecording={recordingInfo.isRecording}
                                    countdown={countdown}
                                    onClick={handleRecordButtonClick}
                                />
                            </Box>


                        </Box>
                    }

                >
                    <RecordingPathTreeItem
                        recordingDirectory={recordingInfo.recordingDirectory}
                        recordingName={recordingName}
                        subfolder={subfolderName}
                        countdown={countdown}
                        // Pass down all the control props
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
