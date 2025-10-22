import React from 'react';
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
    return (
        <>
            <Typography variant="body2" sx={{mb: 1}}>
                Recording Name: {name}
            </Typography>
            {!isRecording && (
                <TextField
                    label="Recording Tag"
                    value={tag}
                    onChange={(e) => onTagChange(e.target.value)}
                    onKeyDown={(e) => {
                        // Stop the TreeView from intercepting keyboard navigation
                        e.stopPropagation();}}
                    size="small"
                    fullWidth
                    placeholder="Optional tag"
                />
            )}
        </>
    );
};
