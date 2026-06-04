import React from 'react';
import { useTranslation } from 'react-i18next';
import TextSelector from '@/components/ui-components/TextSelector';
import SubactionHeader from '@/components/ui-components/SubactionHeader';

interface RecordingNamePreviewProps {
    name: string;
    tag: string;
    isRecording: boolean;
    onTagChange: (tag: string) => void;
    onNameChange: (name: string) => void;
}

export const RecordingNamePreview: React.FC<RecordingNamePreviewProps> = ({
    name, tag, isRecording, onTagChange, onNameChange,
}) => {
    const { t } = useTranslation();
    return (
        <div className="flex flex-col gap-1">
            <SubactionHeader text="Recording Name" />
            {!isRecording ? (
                <TextSelector
                    value={name}
                    onChange={onNameChange}
                    placeholder={t("recordingName")}
                    popupClassName="directory-input-popup"
                />
            ) : (
                <p className="text sm text-gray recording-path-preview">{name}</p>
            )}
            {!isRecording && (
                <TextSelector
                    value={tag}
                    onChange={onTagChange}
                    placeholder={t("recordingTagPlaceholder")}
                />
            )}
        </div>
    );
};
