import React from 'react';
import { RecordingControlsSection } from "@/components/recording-info-panel/RecordingControlsTreeSection";
import SubactionHeader from "@/components/ui-components/SubactionHeader";
import TextSelector from "@/components/ui-components/TextSelector";
import { useAppDispatch } from '@/store';
import { recordingDirectoryChanged } from '@/store/slices/recording/recording-slice';
import { useElectronIPC } from '@/services';

interface RecordingPathTreeItemProps {
    recordingDirectory: string;
    recordingName: string;
    subfolder?: string;
    countdown: number | null;
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
    onNameChange: (value: string) => void;
    onUseTimestampChange: (value: boolean) => void;
    onBaseNameChange: (value: string) => void;
    onUseIncrementChange: (value: boolean) => void;
    onIncrementChange: (value: number) => void;
    onCreateSubfolderChange: (value: boolean) => void;
    onCustomSubfolderNameChange: (value: string) => void;
}

export const RecordingPathTreeItem: React.FC<RecordingPathTreeItemProps> = ({
    recordingDirectory, recordingName, subfolder, countdown, ...controlProps
}) => {
    const dispatch = useAppDispatch();
    const { api, isElectron } = useElectronIPC();

    const handleSelectDirectory = async (): Promise<void> => {
        if (!isElectron || !api) return;
        try {
            const result: string | null = await api.fileSystem.selectDirectory.mutate();
            if (result) dispatch(recordingDirectoryChanged(result));
        } catch (error) {
            console.error('Failed to select directory:', error);
        }
    };

    const {
        createSubfolder, customSubfolderName, onCreateSubfolderChange, onCustomSubfolderNameChange,
        ...sectionProps
    } = controlProps;

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
                <p className="recording-path-preview text-wrap flex-1 text md">
                    {recordingDirectory}
                </p>
            </button>

            {/* Add Subfolder Button */}
            <button
                className={`button icon-button ${createSubfolder ? 'invisible' : ''}`}
                onClick={() => {
                    onCreateSubfolderChange(true);
                    onCustomSubfolderNameChange('NewSubfolder');
                }}
                title="Add subfolder"
            >
                <span className="icon addsubfolder-icon icon-size-20" />
            </button>
        </div>

        {/* Subfolder row */}
        {createSubfolder && (
            <div className="flex items-center gap-1 pl-2">
                <span className="icon icon-size-20 subcat-icon"></span>

                <TextSelector
                    value={customSubfolderName}
                    onChange={onCustomSubfolderNameChange}
                    placeholder="subfolder name"
                    popupClassName="directory-input-popup"
                />

                <button
                    className="button icon-button"
                    onClick={() => {
                        onCreateSubfolderChange(false);
                        onCustomSubfolderNameChange('');
                    }}
                    title="Remove subfolder"
                >
                    <span className="icon minus-icon icon-size-20" />
                </button>
            </div>
        )}

        {countdown !== null && (
            <p className="recording-countdown">{`Starting in ${countdown}...`}</p>
        )}

        <RecordingControlsSection
            recordingName={recordingName}
            {...sectionProps}
        />
    </div>
);
};
