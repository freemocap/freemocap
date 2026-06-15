import React from 'react';
import {
    RecordingNamePreview
} from "@/components/control-panels/recording-info-panel/recording-subcomponents/RecordingNamePreview";
import {
    RecordingSettingsSection
} from "@/components/control-panels/recording-info-panel/recording-subcomponents/RecordingSettingsSection";

interface RecordingControlsSectionProps {
    recordingName: string;
    recordingTag: string;
    useTimestamp: boolean;
    baseName: string;
    useIncrement: boolean;
    currentIncrement: number;
    isRecording: boolean;
    onTagChange: (value: string) => void;
    onNameChange: (value: string) => void;
    onUseTimestampChange: (value: boolean) => void;
    onBaseNameChange: (value: string) => void;
    onUseIncrementChange: (value: boolean) => void;
    onIncrementChange: (value: number) => void;
}

export const RecordingControlsSection: React.FC<RecordingControlsSectionProps> = ({
    recordingName, recordingTag,
    useTimestamp, baseName,
    useIncrement, currentIncrement,
    isRecording, onTagChange, onNameChange,
    onUseTimestampChange, onBaseNameChange, onUseIncrementChange, onIncrementChange,
}) => {
    return (
        <div className="file-directory-secondary-group flex flex-col gap-2">
            <RecordingNamePreview
                name={recordingName}
                tag={recordingTag}
                isRecording={isRecording}
                onTagChange={onTagChange}
                onNameChange={onNameChange}
            />
            <RecordingSettingsSection
                useTimestamp={useTimestamp}
                baseName={baseName}
                useIncrement={useIncrement}
                currentIncrement={currentIncrement}
                onUseTimestampChange={onUseTimestampChange}
                onBaseNameChange={onBaseNameChange}
                onUseIncrementChange={onUseIncrementChange}
                onIncrementChange={onIncrementChange}
            />
        </div>
    );
};
