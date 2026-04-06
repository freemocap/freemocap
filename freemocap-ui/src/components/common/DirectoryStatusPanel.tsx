import React from "react";
import {
    Box,
    Chip,
    CircularProgress,
    IconButton,
    Stack,
    Tooltip,
    Typography,
    useTheme,
} from "@mui/material";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import CloseIcon from "@mui/icons-material/Close";
import InfoIcon from "@mui/icons-material/Info";
import RefreshIcon from "@mui/icons-material/Refresh";

/**
 * Minimal directory‐info shape shared by both calibration and mocap hooks.
 * Extend as needed – the component only reads what it renders.
 */
export interface DirectoryStatus {
    exists: boolean;
    hasVideos: boolean;
    hasSynchronizedVideos: boolean;
    errorMessage?: string | null;
    /** Path to a relevant TOML / output file, if one exists. */
    tomlPath?: string | null;
}

export interface DirectoryStatusPanelProps {
    /** Section heading shown next to the info icon. */
    title: string;
    /** Label for the TOML chip, e.g. "Has calibration TOML" */
    tomlLabel: string;
    /** The directoryInfo object from the relevant hook. `null` hides the panel. */
    directoryInfo: DirectoryStatus | null;
    /** Called when the user clicks the refresh button. */
    onRefresh?: () => void;
    /** Disables the refresh button. */
    refreshDisabled?: boolean;
    /** Shows a spinner on the refresh button. */
    isRefreshing?: boolean;
    /** Visual accent for the border: "ok" | "bad" | "none". Defaults to "none". */
    status?: "ok" | "bad" | "none";
}

/** Reusable chip for a boolean check. */
const StatusChip: React.FC<{
    label: string;
    ok: boolean;
}> = ({label, ok}) => {
    const theme = useTheme();
    return (
        <Chip
            label={label}
            size="small"
            color={ok ? "success" : "default"}
            icon={ok ? <CheckCircleIcon /> : <CloseIcon />}
            variant={ok ? "filled" : "outlined"}
            sx={
                !ok
                    ? {
                          borderColor: theme.palette.grey[400],
                          "& .MuiChip-icon": {color: theme.palette.grey[600]},
                      }
                    : {}
            }
        />
    );
};

/**
 * Shows directory existence, video availability, sync status and TOML
 * presence as a row of status chips with an optional refresh button.
 *
 * Designed to drop into both CalibrationControlPanel and MocapTaskTreeItem,
 * replacing the ~140 lines of duplicated chip JSX in each.
 */
export const DirectoryStatusPanel: React.FC<DirectoryStatusPanelProps> = ({
    title,
    tomlLabel,
    directoryInfo,
    onRefresh,
    refreshDisabled = false,
    isRefreshing = false,
    status = "none",
}) => {
    const theme = useTheme();

    if (!directoryInfo) return null;

    const borderColor =
        status === "ok"
            ? "#00e5ff44"
            : status === "bad"
              ? `${theme.palette.error.main}44`
              : theme.palette.divider;

    return (
        <Box sx={{p: 1.5, borderRadius: 1, border: `2px solid ${borderColor}`}}>
            <Stack spacing={1}>
                {/* Header row */}
                <Box
                    sx={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                    }}
                >
                    <Box sx={{display: "flex", alignItems: "center", gap: 1}}>
                        <InfoIcon fontSize="small" color="info" />
                        <Typography variant="caption" fontWeight="medium">
                            {title}
                        </Typography>
                    </Box>

                    {onRefresh && (
                        <Tooltip title="Re-check folder">
                            <span>
                                <IconButton
                                    size="small"
                                    onClick={onRefresh}
                                    disabled={refreshDisabled}
                                    sx={{p: 0.25}}
                                >
                                    {isRefreshing ? (
                                        <CircularProgress size={14} color="inherit" />
                                    ) : (
                                        <RefreshIcon sx={{fontSize: 14}} />
                                    )}
                                </IconButton>
                            </span>
                        </Tooltip>
                    )}
                </Box>

                {/* Status chips */}
                <Box sx={{display: "flex", gap: 1, flexWrap: "wrap"}}>
                    <StatusChip
                        label={directoryInfo.exists ? "Directory exists" : "Directory will be created"}
                        ok={directoryInfo.exists}
                    />
                    <StatusChip label="Has videos" ok={directoryInfo.hasVideos} />
                    <StatusChip label="Has synchronized_videos" ok={directoryInfo.hasSynchronizedVideos} />
                    <StatusChip label={tomlLabel} ok={!!directoryInfo.tomlPath} />
                </Box>

                {/* TOML path display */}
                {directoryInfo.tomlPath && (
                    <Box sx={{mt: 1}}>
                        <Typography variant="caption" color="text.secondary">
                            Found calibration file:
                        </Typography>
                        <Typography
                            variant="caption"
                            sx={{
                                fontFamily: "monospace",
                                display: "block",
                                color: "success.main",
                                wordBreak: "break-all",
                            }}
                        >
                            {directoryInfo.tomlPath}
                        </Typography>
                    </Box>
                )}
            </Stack>
        </Box>
    );
};
