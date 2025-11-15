import React from 'react';
import {Box} from '@mui/material';
import {
    DelayRecordingStartControl
} from "@/components/recording-info-panel/recording-subcomponents/DelayRecordingStartControl";
import {
    BaseRecordingDirectoryInput
} from "@/components/recording-info-panel/recording-subcomponents/BaseRecordingDirectoryInput";
import {RecordingNamePreview} from "@/components/recording-info-panel/recording-subcomponents/RecordingNamePreview";
import {
    RecordingSettingsSection
} from "@/components/recording-info-panel/recording-subcomponents/RecordingSettingsSection";

interface RecordingControlsSectionProps {
    recordingDirectory: string;
    recordingTag: string;
    useDelayStart: boolean;
    delaySeconds: number;
    useTimestamp: boolean;
    baseName: string;
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

export const RecordingControlsSection: React.FC<RecordingControlsSectionProps> = ({
                                                                                      recordingDirectory,
                                                                                      recordingTag,
                                                                                      useDelayStart,
                                                                                      delaySeconds,
                                                                                      useTimestamp,
                                                                                      baseName,
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
    return (
        <Box sx={{pl: 2, pt: 1, display: 'flex', flexDirection: 'column', gap: 2}}>
            <DelayRecordingStartControl
                useDelay={useDelayStart}
                delaySeconds={delaySeconds}
                onDelayToggle={onDelayToggle}
                onDelayChange={onDelayChange}
            />

            <BaseRecordingDirectoryInput
                baseRecordingFolder={recordingDirectory}
            />

            <RecordingNamePreview
                tag={recordingTag}
                isRecording={isRecording}
                onTagChange={onTagChange}
            />

            <RecordingSettingsSection
                useTimestamp={useTimestamp}
                baseName={baseName}
                useIncrement={useIncrement}
                currentIncrement={currentIncrement}
                createSubfolder={createSubfolder}
                customSubfolderName={customSubfolderName}
                onUseTimestampChange={onUseTimestampChange}
                onBaseNameChange={onBaseNameChange}
                onUseIncrementChange={onUseIncrementChange}
                onIncrementChange={onIncrementChange}
                onCreateSubfolderChange={onCreateSubfolderChange}
                onCustomSubfolderNameChange={onCustomSubfolderNameChange}
            />
        </Box>
    );
};
