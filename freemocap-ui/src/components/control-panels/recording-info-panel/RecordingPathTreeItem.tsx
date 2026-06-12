import React, {useEffect, useState} from 'react';
import {RecordingControlsSection} from "@/components/control-panels/recording-info-panel/RecordingControlsTreeSection";
import {getTimestampString} from "@/components/control-panels/recording-info-panel/getTimestampString";
import SubactionHeader from '@/components/ui-components/SubactionHeader';
import TextSelector from '@/components/ui-components/TextSelector';
import {useAppDispatch} from '@/store';
import {recordingDirectoryChanged} from '@/store/slices/recording/recording-slice';
import {useElectronIPC} from '@/services';
import IconButton from '@/components/ui-components/IconButton';

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
    onNameChange: (value: string) => void;
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
    onNameChange,
    onUseTimestampChange,
    onBaseNameChange,
    onUseIncrementChange,
    onIncrementChange,
    onCreateSubfolderChange,
    onCustomSubfolderNameChange,
}) => {
    const dispatch = useAppDispatch();
    const {api, isElectron} = useElectronIPC();
    const [previewTimestamp, setPreviewTimestamp] = useState<string>(() => getTimestampString());

    useEffect(() => {
        if (isRecording) return;
        const id = setInterval(() => setPreviewTimestamp(getTimestampString()), 1000);
        return () => clearInterval(id);
    }, [isRecording]);

    const handleSelectDirectory = async (): Promise<void> => {
        if (!isElectron || !api) return;
        try {
            const result: string | null = await api.fileSystem.selectDirectory.mutate();
            if (result) dispatch(recordingDirectoryChanged(result));
        } catch (error) {
            console.error('Failed to select directory:', error);
        }
    };

    const nameParts: string[] = [];
    if (useTimestamp) nameParts.push(previewTimestamp);
    else nameParts.push(baseName);
    if (recordingTypePreset !== "none") nameParts.push(recordingTypePreset);
    if (recordingTag) nameParts.push(recordingTag);
    const recordingName = nameParts.join("_");

    return (
        <div className="file-directory-settings-item flex flex-col gap-1" onKeyDown={(e) => e.stopPropagation()}>
            <SubactionHeader text="Recording Folder" />

            {/* Base folder row */}
            <div className="flex items-center gap-1">
                <button
                    className="select-path button sm bg-middark br-1 border-1 border-black flex items-center gap-1 text-left flex-1"
                    onClick={handleSelectDirectory}
                    title="Click to select recording folder"
                    disabled={!isElectron}
                >
                    <span className="icon subfolder-icon icon-size-20" />
                    <p className="recording-path-preview flex text-wrap flex-1 text md">
                        {recordingDirectory}
                    </p>
                </button>

                <IconButton
                    icon="addsubfolder-icon"
                    className={`icon-size-25 ${createSubfolder ? 'invisible' : ''}`}
                    onClick={() => {
                        onCreateSubfolderChange(true);
                        onCustomSubfolderNameChange('NewSubfolder');
                    }}
                    title="Add subfolder"
                />
            </div>

            {/* Subfolder row */}
            {createSubfolder && (
                <div className="flex items-center gap-1 pl-2">
                    <span className="icon icon-size-20 subcat-icon" />
                    <TextSelector
                        value={customSubfolderName}
                        onChange={onCustomSubfolderNameChange}
                        placeholder="subfolder name"
                        popupClassName="directory-input-popup"
                    />
                    <IconButton
                        icon="minus-icon"
                        onClick={() => {
                            onCreateSubfolderChange(false);
                            onCustomSubfolderNameChange('');
                        }}
                        title="Remove subfolder"
                    />
                </div>
            )}

            {countdown !== null && (
                <p className="recording-countdown">{`Starting in ${countdown}...`}</p>
            )}

            <RecordingControlsSection
                recordingName={recordingName}
                recordingTag={recordingTag}
                useDelayStart={useDelayStart}
                delaySeconds={delaySeconds}
                useTimestamp={useTimestamp}
                baseName={baseName}
                useIncrement={useIncrement}
                currentIncrement={currentIncrement}
                isRecording={isRecording}
                onDelayToggle={onDelayToggle}
                onDelayChange={onDelayChange}
                onTagChange={onTagChange}
                onNameChange={onNameChange}
                onUseTimestampChange={onUseTimestampChange}
                onBaseNameChange={onBaseNameChange}
                onUseIncrementChange={onUseIncrementChange}
                onIncrementChange={onIncrementChange}
            />
        </div>
    );
};
