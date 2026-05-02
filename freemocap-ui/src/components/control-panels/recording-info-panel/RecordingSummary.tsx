import React, {useEffect, useState} from "react";
import {Chip, Typography, useTheme} from "@mui/material";
import FiberManualRecordIcon from "@mui/icons-material/FiberManualRecord";

function formatDuration(startedAt: string): string {
    const seconds = Math.floor((Date.now() - new Date(startedAt).getTime()) / 1000);
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    const parts: string[] = [];
    if (hours > 0) parts.push(hours.toString().padStart(2, '0'));
    parts.push(minutes.toString().padStart(2, '0'));
    parts.push(secs.toString().padStart(2, '0'));
    return parts.join(':');
}

interface RecordingSummaryProps {
    isRecording: boolean;
    startedAt: string | null;
}

export const RecordingSummary: React.FC<RecordingSummaryProps> = ({
    isRecording,
    startedAt,
}) => {
    const [recordingDuration, setRecordingDuration] = useState<string>("");

    useEffect(() => {
        if (!isRecording || !startedAt) {
            setRecordingDuration("");
            return;
        }
        setRecordingDuration(formatDuration(startedAt));
        const id = setInterval(() => setRecordingDuration(formatDuration(startedAt)), 1000);
        return () => clearInterval(id);
    }, [isRecording, startedAt]);
    const theme = useTheme();

    if (!isRecording) {
        return (
            <Typography
                variant="caption"
                sx={{
                    color: theme.palette.grey[400],
                    fontWeight: 500,
                    whiteSpace: "nowrap",
                }}
            >
                Ready
            </Typography>
        );
    }

    return (
        <Chip
            icon={<FiberManualRecordIcon sx={{ fontSize: 10 }} />}
            label={recordingDuration || "Recording..."}
            size="small"
            sx={{
                height: 20,
                fontSize: 11,
                fontWeight: 600,
                backgroundColor: theme.palette.error.main,
                color: theme.palette.error.contrastText,
                animation: 'pulse-record 2s infinite ease-in-out',
                '@keyframes pulse-record': {
                    '0%, 100%': { opacity: 1 },
                    '50%': { opacity: 0.7 },
                },
                "& .MuiChip-icon": {
                    color: "inherit",
                    animation: 'pulse-dot 1s infinite ease-in-out',
                    '@keyframes pulse-dot': {
                        '0%, 100%': { opacity: 1 },
                        '50%': { opacity: 0.4 },
                    },
                },
            }}
        />
    );
};
