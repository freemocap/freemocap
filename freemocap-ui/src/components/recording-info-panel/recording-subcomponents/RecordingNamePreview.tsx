import React from 'react';
import {TextField, Typography} from '@mui/material';
import { useAppSelector } from '@/store';

interface RecordingNamePreviewProps {
    tag: string;
    isRecording: boolean;
    onTagChange: (tag: string) => void;
}

export const RecordingNamePreview: React.FC<RecordingNamePreviewProps> = ({
                                                                              tag,
                                                                              isRecording,
                                                                              onTagChange
                                                                          }) => {
    // Read computed recording name from store
    const recordingName = useAppSelector((state) => state.recording.computed.recordingName);

    return (
        <>
            <Typography variant="body2" sx={{mb: 1}}>
                Recording Name: {recordingName}
            </Typography>
            {!isRecording && (
                <TextField
                    label="Recording Tag"
                    value={tag}
                    onChange={(e) => onTagChange(e.target.value)}
                    onKeyDown={(e) => {
                        // Stop the TreeView from intercepting keyboard navigation
                        e.stopPropagation();
                    }}
                    size="small"
                    fullWidth
                    placeholder="Optional tag"
                />
            )}
        </>
    );
};
