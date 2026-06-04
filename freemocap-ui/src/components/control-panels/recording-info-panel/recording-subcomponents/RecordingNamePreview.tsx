import React from 'react';
import {useTranslation} from 'react-i18next';

interface RecordingNamePreviewProps {
    name: string;
    tag: string;
    isRecording: boolean;
    onTagChange: (tag: string) => void;
}

export const RecordingNamePreview: React.FC<RecordingNamePreviewProps> = ({
    name,
    tag,
    isRecording,
    onTagChange
}) => {
    const { t } = useTranslation();
    return (
        <>
            <p className="text sm text-gray" style={{marginBottom: 8}}>
                {t('recordingName', { name })}
            </p>
            {!isRecording && (
                <div className="input-with-string w-full">
                    <input
                        className="input-field text md w-full"
                        value={tag}
                        onChange={(e) => onTagChange(e.target.value)}
                        onKeyDown={(e) => {
                            // Stop the TreeView from intercepting keyboard navigation
                            e.stopPropagation();
                        }}
                        placeholder={t("recordingTagPlaceholder")}
                    />
                </div>
            )}
        </>
    );
};
