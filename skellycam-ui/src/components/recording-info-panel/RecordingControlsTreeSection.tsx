import React from 'react';
import { DelayRecordingStartControl } from "@/components/recording-info-panel/recording-subcomponents/DelayRecordingStartControl";
import { RecordingNamePreview } from "@/components/recording-info-panel/recording-subcomponents/RecordingNamePreview";
import { RecordingSettingsSection } from "@/components/recording-info-panel/recording-subcomponents/RecordingSettingsSection";

interface RecordingControlsSectionProps {
    recordingName: string;
    recordingTag: string;
    useDelayStart: boolean;
    delaySeconds: number;
    useTimestamp: boolean;
    baseName: string;
    useIncrement: boolean;
    currentIncrement: number;
    isRecording: boolean;
    onDelayToggle: (value: boolean) => void;
    onDelayChange: (value: number) => void;
    onTagChange: (value: string) => void;
    onNameChange: (value: string) => void;
    onUseTimestampChange: (value: boolean) => void;
    onBaseNameChange: (value: string) => void;
    onUseIncrementChange: (value: boolean) => void;
    onIncrementChange: (value: number) => void;
}

export const RecordingControlsSection: React.FC<RecordingControlsSectionProps> = (props) => {
    const {
        recordingName, recordingTag,
        useDelayStart, delaySeconds, useTimestamp, baseName,
        useIncrement, currentIncrement,
        isRecording, onDelayToggle, onDelayChange, onTagChange, onNameChange,
        onUseTimestampChange, onBaseNameChange, onUseIncrementChange, onIncrementChange,
    } = props;

    return (
        <div className="file-directory-secondary-group flex flex-col gap-2">
            <RecordingNamePreview
                name={recordingName}
                tag={recordingTag}
                isRecording={isRecording}
                onTagChange={onTagChange}
                onNameChange={onNameChange}
            />
            <DelayRecordingStartControl
                useDelay={useDelayStart}
                delaySeconds={delaySeconds}
                onDelayToggle={onDelayToggle}
                onDelayChange={onDelayChange}
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
