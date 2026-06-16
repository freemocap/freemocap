import React, {useEffect, useState} from 'react';
import {Box, Typography} from '@mui/material';
import {TreeItem} from '@mui/x-tree-view/TreeItem';
import {
    FullRecordingPathPreview
} from "@/components/control-panels/recording-info-panel/recording-subcomponents/FullRecordingPathPreview";
import {RecordingControlsSection} from "@/components/control-panels/recording-info-panel/RecordingControlsTreeSection";
import {getTimestampString} from "@/components/control-panels/recording-info-panel/getTimestampString";

interface RecordingPathTreeItemProps {
    recordingDirectory: string;
    countdown: number | null;
    recordingTag: string;
    useDelayStart: boolean;
    delaySeconds: number;
    useTimestamp: boolean;
    baseName: string;
    recordingTypePreset: string;
    useIncrement: boolean;
    currentIncrement: number;
    createSubfolder: boolean;
    customSubfolderName: string;
    isRecording: boolean;
    onDelayToggle: (value: boolean) => void;
    onDelayChange: (value: number) => void;
    onTagChange: (value: string) => void;
    onUseTimestampChange: (value: boolean) => void;
    onBaseNameChange: (value: string) => void;
    onUseIncrementChange: (value: boolean) => void;
    onIncrementChange: (value: number) => void;
    onCreateSubfolderChange: (value: boolean) => void;
    onCustomSubfolderNameChange: (value: string) => void;
}

export const RecordingPathTreeItem: React.FC<RecordingPathTreeItemProps> = ({
                                                                                recordingDirectory,
                                                                                countdown,
                                                                                recordingTag,
                                                                                useDelayStart,
                                                                                delaySeconds,
                                                                                useTimestamp,
                                                                                baseName,
                                                                                recordingTypePreset,
                                                                                useIncrement,
                                                                                currentIncrement,
                                                                                createSubfolder,
                                                                                customSubfolderName,
                                                                                isRecording,
                                                                                onDelayToggle,
                                                                                onDelayChange,
                                                                                onTagChange,
                                                                                onUseTimestampChange,
                                                                                onBaseNameChange,
                                                                                onUseIncrementChange,
                                                                                onIncrementChange,
                                                                                onCreateSubfolderChange,
                                                                                onCustomSubfolderNameChange
                                                                            }) => {
    // Tick once per second while not recording so the name preview stays current.
    // Isolated here so only this subtree re-renders, not the entire panel.
    const [previewTimestamp, setPreviewTimestamp] = useState<string>(() => getTimestampString());
    useEffect(() => {
        if (isRecording) return;
        const id = setInterval(() => setPreviewTimestamp(getTimestampString()), 1000);
        return () => clearInterval(id);
    }, [isRecording]);

    const nameParts: string[] = [];
    if (useTimestamp) {
        nameParts.push(previewTimestamp);
    } else {
        nameParts.push(baseName);
    }
    if (recordingTypePreset !== "none") nameParts.push(recordingTypePreset);
    if (recordingTag) nameParts.push(recordingTag);
    const recordingName = nameParts.join("_");
    const subfolder = createSubfolder ? customSubfolderName || previewTimestamp : undefined;

    return (
        <TreeItem
            itemId="recording-path"
            label={
                <Box sx={{display: 'flex', alignItems: 'center', gap: 1}}>
                    <FullRecordingPathPreview
                        directory={recordingDirectory}
                        filename={recordingName}
                        subfolder={subfolder}
                    />
                </Box>
            }
        >
            <Box
                onKeyDown={(e) => e.stopPropagation()}
                sx={{pl: 2, pt: 1, display: 'flex', flexDirection: 'column', gap: 2}}
            >
                {countdown !== null && (
                    <Typography variant="h4" align="center" color="secondary">
                        Starting in {countdown}...
                    </Typography>
                )}

                <RecordingControlsSection
                    recordingDirectory={recordingDirectory}
                    recordingName={recordingName}
                    recordingTag={recordingTag}
                    useDelayStart={useDelayStart}
                    delaySeconds={delaySeconds}
                    useTimestamp={useTimestamp}
                    baseName={baseName}
                    useIncrement={useIncrement}
                    currentIncrement={currentIncrement}
                    createSubfolder={createSubfolder}
                    customSubfolderName={customSubfolderName}
                    isRecording={isRecording}
                    onDelayToggle={onDelayToggle}
                    onDelayChange={onDelayChange}
                    onTagChange={onTagChange}
                    onUseTimestampChange={onUseTimestampChange}
                    onBaseNameChange={onBaseNameChange}
                    onUseIncrementChange={onUseIncrementChange}
                    onIncrementChange={onIncrementChange}
                    onCreateSubfolderChange={onCreateSubfolderChange}
                    onCustomSubfolderNameChange={onCustomSubfolderNameChange}
                />
            </Box>
        </TreeItem>
    );
};
