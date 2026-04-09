import React from "react";
import {Chip, Typography, useTheme} from "@mui/material";
import VideocamIcon from "@mui/icons-material/Videocam";

interface CameraSummaryProps {
    cameraCount: number;
    connectedCount: number;
}

export const CameraSummary: React.FC<CameraSummaryProps> = ({
    cameraCount,
    connectedCount,
}) => {
    const theme = useTheme();

    if (cameraCount === 0) {
        return (
            <Typography
                variant="caption"
                sx={{
                    color: theme.palette.grey[400],
                    fontWeight: 500,
                    whiteSpace: "nowrap",
                }}
            >
                No cameras
            </Typography>
        );
    }

    const statusColor = connectedCount > 0
        ? theme.palette.success.main
        : theme.palette.grey[600];

    return (
        <Chip
            icon={<VideocamIcon sx={{ fontSize: 14 }} />}
            label={connectedCount > 0 ? `${connectedCount} connected` : `${cameraCount} available`}
            size="small"
            sx={{
                height: 20,
                fontSize: 11,
                fontWeight: 600,
                backgroundColor: statusColor,
                color: theme.palette.getContrastText(statusColor),
                "& .MuiChip-icon": {
                    color: "inherit",
                },
            }}
        />
    );
};
