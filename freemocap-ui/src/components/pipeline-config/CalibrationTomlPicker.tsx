import React from "react";
import {Box, Button, Chip, Tooltip, Typography, useTheme} from "@mui/material";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import ErrorIcon from "@mui/icons-material/Error";
import WarningAmberIcon from "@mui/icons-material/WarningAmber";
import FolderOpenIcon from "@mui/icons-material/FolderOpen";
import AutorenewIcon from "@mui/icons-material/Autorenew";

export type CalibrationTomlSource = "auto" | "calibration-panel" | "manual";

interface CalibrationTomlPickerProps {
    tomlPath: string | null;
    source: CalibrationTomlSource;
    onSelect: () => void;
    onUseAutoDetected: () => void;
    disabled?: boolean;
}

const SOURCE_LABELS: Record<CalibrationTomlSource, string> = {
    auto: "Auto-detected",
    "calibration-panel": "From calibration panel",
    manual: "Manually selected",
};

export const CalibrationTomlPicker: React.FC<CalibrationTomlPickerProps> = ({
    tomlPath,
    source,
    onSelect,
    onUseAutoDetected,
    disabled = false,
}) => {
    const theme = useTheme();

    const statusIcon = tomlPath ? (
        <CheckCircleIcon sx={{fontSize: 18, color: "#00e5ff"}} />
    ) : (
        <ErrorIcon sx={{fontSize: 18, color: theme.palette.error.main}} />
    );

    return (
        <Box
            sx={{
                display: "flex",
                alignItems: "center",
                gap: 1,
                p: 1,
                borderRadius: 1,
                border: `1px solid ${theme.palette.divider}`,
                minHeight: 36,
            }}
        >
            {statusIcon}

            <Box sx={{flex: 1, minWidth: 0}}>
                {tomlPath ? (
                    <>
                        <Chip
                            label={SOURCE_LABELS[source]}
                            size="small"
                            sx={{
                                height: 16,
                                fontSize: 9,
                                "& .MuiChip-label": {px: 0.5},
                                mb: 0.25,
                            }}
                        />
                        <Tooltip title={tomlPath} arrow>
                            <Typography
                                variant="caption"
                                sx={{
                                    fontFamily: "monospace",
                                    fontSize: 10,
                                    display: "block",
                                    color: "success.main",
                                    overflow: "hidden",
                                    textOverflow: "ellipsis",
                                    whiteSpace: "nowrap",
                                }}
                            >
                                {tomlPath}
                            </Typography>
                        </Tooltip>
                    </>
                ) : (
                    <Typography variant="caption" color="text.secondary">
                        No calibration TOML found
                    </Typography>
                )}
            </Box>

            {source !== "auto" && tomlPath && (
                <Tooltip title="Use auto-detected calibration" arrow>
                    <Button
                        size="small"
                        onClick={onUseAutoDetected}
                        disabled={disabled}
                        sx={{minWidth: 0, p: 0.5}}
                    >
                        <AutorenewIcon fontSize="small" />
                    </Button>
                </Tooltip>
            )}

            <Button
                size="small"
                variant="outlined"
                onClick={onSelect}
                disabled={disabled}
                startIcon={<FolderOpenIcon />}
                sx={{flexShrink: 0, textTransform: "none", fontSize: 11}}
            >
                Browse
            </Button>
        </Box>
    );
};
