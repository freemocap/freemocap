import React from "react";
import {Chip, Typography, useTheme} from "@mui/material";
import {useAppSelector} from "@/store/hooks";
import {selectIsPipelineConnected, selectPipelineError, selectPipelineId,} from "@/store/slices/realtime";

export const RealtimePipelineSummary: React.FC = () => {
    const theme = useTheme();

    const isConnected = useAppSelector(selectIsPipelineConnected);
    const pipelineId = useAppSelector(selectPipelineId);
    const error = useAppSelector(selectPipelineError);

    if (error) {
        return (
            <Typography
                variant="caption"
                sx={{
                    color: theme.palette.error.light,
                    fontWeight: 500,
                    whiteSpace: "nowrap",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                }}
            >
                Error
            </Typography>
        );
    }

    const statusColor = isConnected
        ? theme.palette.success.main
        : theme.palette.grey[600];

    return (
        <Chip
            label={isConnected ? `Active (${pipelineId})` : "Inactive"}
            size="small"
            sx={{
                height: 20,
                fontSize: 11,
                fontWeight: 600,
                backgroundColor: statusColor,
                color: theme.palette.getContrastText(statusColor),
                maxWidth: 160,
                "& .MuiChip-label": {
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                },
            }}
        />
    );
};
