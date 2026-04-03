import React from "react";
import {Chip, Typography, useTheme} from "@mui/material";
import FiberManualRecordIcon from "@mui/icons-material/FiberManualRecord";

interface RecordingSummaryProps {
    isRecording: boolean;
    recordingDuration?: string;
}

export const RecordingSummary: React.FC<RecordingSummaryProps> = ({
    isRecording,
    recordingDuration,
}) => {
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
