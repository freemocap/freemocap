import React from "react";
import {CircularProgress, IconButton, Tooltip} from "@mui/material";
import FiberManualRecordIcon from "@mui/icons-material/FiberManualRecord";
import StopIcon from "@mui/icons-material/Stop";

interface RecordingHeaderButtonProps {
    isRecording: boolean;
    isPending: boolean;
    disabled: boolean;
    onClick: () => void;
}

export const RecordingHeaderButton: React.FC<RecordingHeaderButtonProps> = ({
    isRecording,
    isPending,
    disabled,
    onClick,
}) => {
    const handleClick = (e: React.MouseEvent): void => {
        e.stopPropagation();
        onClick();
    };

    return (
        <Tooltip title={isRecording ? "Stop Recording" : "Start Recording"}>
            <span>
                <IconButton
                    size="small"
                    onClick={handleClick}
                    disabled={disabled || isPending}
                    sx={{
                        padding: "4px",
                        color: isRecording ? "error.main" : "inherit",
                        opacity: disabled && !isRecording ? 0.4 : 1,
                        transition: "color 0.2s ease",
                        "&:hover": {
                            color: isRecording ? "error.light" : "primary.main",
                        },
                        ...(isRecording && {
                            animation: 'pulse-record 2s infinite ease-in-out',
                            '@keyframes pulse-record': {
                                '0%, 100%': { color: 'error.main' },
                                '50%': { color: 'error.dark' },
                            },
                        }),
                    }}
                >
                    {isPending ? (
                        <CircularProgress size={20} sx={{ color: "inherit" }} />
                    ) : isRecording ? (
                        <StopIcon sx={{ fontSize: 24 }} />
                    ) : (
                        <FiberManualRecordIcon sx={{ fontSize: 24 }} />
                    )}
                </IconButton>
            </span>
        </Tooltip>
    );
};
