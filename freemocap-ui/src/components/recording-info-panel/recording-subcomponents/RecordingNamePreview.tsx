import React from 'react';
import { useTranslation } from 'react-i18next';
import {TextField, Typography} from '@mui/material';

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
            <Typography variant="body2" sx={{mb: 1}}>
                {t('recordingName', { name })}
            </Typography>
            {!isRecording && (
                <TextField
                    label={t("recordingTag")}
                    value={tag}
                    onChange={(e) => onTagChange(e.target.value)}
                    onKeyDown={(e) => {
                        // Stop the TreeView from intercepting keyboard navigation
                        e.stopPropagation();}}
                    size="small"
                    fullWidth
                    placeholder={t("recordingTagPlaceholder")}
                />
            )}
        </>
    );
};
