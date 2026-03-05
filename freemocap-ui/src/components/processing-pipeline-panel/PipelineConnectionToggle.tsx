import React from "react";
import {CircularProgress, IconButton, Tooltip, useTheme} from "@mui/material";
import PowerSettingsNewIcon from "@mui/icons-material/PowerSettingsNew";
import {useAppDispatch, useAppSelector} from "@/store/hooks";
import {
    closePipeline,
    connectRealtimePipeline,
    selectCanConnectPipeline,
    selectCanDisconnectPipeline,
    selectIsPipelineConnected,
    selectIsPipelineLoading,
} from "@/store/slices/pipeline";

export const PipelineConnectionToggle: React.FC = () => {
    const theme = useTheme();
    const dispatch = useAppDispatch();

    const isConnected = useAppSelector(selectIsPipelineConnected);
    const isLoading = useAppSelector(selectIsPipelineLoading);
    const canConnect = useAppSelector(selectCanConnectPipeline);
    const canDisconnect = useAppSelector(selectCanDisconnectPipeline);

    const isClickable = canConnect || canDisconnect;

    const handleToggle = async (e: React.MouseEvent): Promise<void> => {
        e.stopPropagation();
        if (isLoading) return;

        if (isConnected) {
            await dispatch(closePipeline());
        } else {
            await dispatch(connectRealtimePipeline(undefined));
        }
    };

    const tooltipText = isConnected
        ? "Disconnect pipeline"
        : canConnect
            ? "Connect pipeline"
            : "Select cameras first";

    return (
        <Tooltip title={tooltipText}>
            <span>
                <IconButton
                    size="small"
                    onClick={handleToggle}
                    disabled={!isClickable || isLoading}
                    sx={{
                        color: "inherit",
                        border: "1.5px solid",
                        borderColor: isConnected
                            ? theme.palette.success.light
                            : "rgba(255,255,255,0.25)",
                        borderRadius: 1,
                        p: 0.5,
                        backgroundColor: isConnected
                            ? "rgba(76, 175, 80, 0.2)"
                            : "transparent",
                        "&:hover": {
                            backgroundColor: isConnected
                                ? "rgba(76, 175, 80, 0.3)"
                                : "rgba(255,255,255,0.1)",
                        },
                        "&.Mui-disabled": {
                            color: "rgba(255,255,255,0.3)",
                            borderColor: "rgba(255,255,255,0.1)",
                        },
                    }}
                >
                    {isLoading ? (
                        <CircularProgress size={18} sx={{color: "inherit"}} />
                    ) : (
                        <PowerSettingsNewIcon fontSize="small" />
                    )}
                </IconButton>
            </span>
        </Tooltip>
    );
};
