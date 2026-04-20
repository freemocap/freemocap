import React from "react";
import {
    Accordion,
    AccordionDetails,
    AccordionSummary,
    Alert,
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
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import InfoIcon from "@mui/icons-material/Info";
import RefreshIcon from "@mui/icons-material/Refresh";
import {RecordingStatus} from "@/types/recording-status";

interface RecordingStatusPanelProps {
    status: RecordingStatus | null;
    isLoading?: boolean;
    error?: string | null;
    onRefresh?: () => void;
    defaultExpanded?: boolean;
    /** Path to the calibration TOML the user has currently selected (shown at top). */
    activeCalibrationTomlPath?: string | null;
    /** When false, the panel shows a "folder doesn't exist yet" notice instead of status. */
    folderExists?: boolean;
    /** Path shown in the "folder missing" notice for clarity. */
    recordingFolderPath?: string | null;
}

const humanizeBytes = (bytes: number | null): string => {
    if (bytes == null) return "—";
    if (bytes < 1024) return `${bytes} B`;
    const units = ["KB", "MB", "GB", "TB"];
    let value = bytes / 1024;
    let i = 0;
    while (value >= 1024 && i < units.length - 1) {
        value /= 1024;
        i++;
    }
    return `${value.toFixed(value >= 10 ? 0 : 1)} ${units[i]}`;
};

const formatTimestamp = (iso: string | null): string => {
    if (!iso) return "";
    try {
        const d = new Date(iso);
        if (Number.isNaN(d.getTime())) return iso;
        return d.toLocaleString();
    } catch {
        return iso;
    }
};

const StageChip: React.FC<{name: string; complete: boolean; present: number; total: number}> = ({
    name,
    complete,
    present,
    total,
}) => {
    const theme = useTheme();
    const label = total > 1 ? `${name} (${present}/${total})` : name;
    return (
        <Chip
            size="small"
            label={label}
            color={complete ? "success" : "default"}
            icon={complete ? <CheckCircleIcon/> : <CloseIcon/>}
            variant={complete ? "filled" : "outlined"}
            sx={
                !complete
                    ? {
                          borderColor: theme.palette.grey[400],
                          "& .MuiChip-icon": {color: theme.palette.grey[600]},
                      }
                    : {}
            }
        />
    );
};

export const RecordingStatusPanel: React.FC<RecordingStatusPanelProps> = ({
    status,
    isLoading = false,
    error = null,
    onRefresh,
    defaultExpanded = false,
    activeCalibrationTomlPath = null,
    folderExists = true,
    recordingFolderPath = null,
}) => {
    const theme = useTheme();

    const stagesComplete = status ? status.stages.filter((s) => s.complete).length : 0;
    const stagesTotal = status ? status.stages.length : 0;
    const allStagesComplete = stagesTotal > 0 && stagesComplete === stagesTotal;
    const hasBlend = !!status?.has_blend_file;
    const exportReady = !!status?.blender_export_ready;

    // Fully processed = every stage complete (including the blender scene).
    // Ready for Blender = inputs present but no .blend yet.
    const summaryLabel = !folderExists
        ? "Folder not created yet"
        : status
            ? allStagesComplete && hasBlend
                ? "Fully processed"
                : exportReady && !hasBlend
                    ? "Ready for Blender"
                    : `${stagesComplete}/${stagesTotal} stages complete`
            : isLoading
                ? "Checking…"
                : error
                    ? "Status unavailable"
                    : "No status";

    const summaryColor: "success" | "info" | "warning" | "default" = !folderExists
        ? "warning"
        : allStagesComplete && hasBlend
            ? "success"
            : exportReady && !hasBlend
                ? "info"
                : "default";
    const accentBorder =
        summaryColor === "success"
            ? "#00e5ff66"
            : summaryColor === "info"
                ? `${theme.palette.info.main}44`
                : summaryColor === "warning"
                    ? `${theme.palette.warning.main}55`
                    : theme.palette.divider;

    return (
        <Accordion
            defaultExpanded={defaultExpanded}
            disableGutters
            square
            sx={{
                "&:before": {display: "none"},
                borderRadius: 1,
                border: `2px solid ${accentBorder}`,
                bgcolor: "transparent",
                boxShadow: "none",
            }}
        >
            <AccordionSummary
                expandIcon={<ExpandMoreIcon/>}
                sx={{
                    minHeight: 40,
                    "& .MuiAccordionSummary-content": {
                        my: 0.5,
                        alignItems: "center",
                        gap: 1,
                        minWidth: 0,
                    },
                }}
            >
                <InfoIcon fontSize="small" color="info"/>
                <Typography
                    variant="caption"
                    fontWeight="medium"
                    noWrap
                    sx={{flex: "0 1 auto", minWidth: 0}}
                >
                    Recording folder
                </Typography>
                <Chip
                    size="small"
                    label={summaryLabel}
                    color={summaryColor === "default" ? "default" : summaryColor}
                    icon={summaryColor !== "default" ? <CheckCircleIcon/> : undefined}
                    variant={summaryColor !== "default" ? "filled" : "outlined"}
                    sx={{flexShrink: 0}}
                />
                <Box sx={{flex: 1}}/>
                {onRefresh && (
                    <Tooltip title="Re-check folder">
                        <span>
                            <IconButton
                                size="small"
                                onClick={(e) => {
                                    e.stopPropagation();
                                    onRefresh();
                                }}
                                disabled={isLoading}
                                sx={{p: 0.25, flexShrink: 0}}
                            >
                                {isLoading ? (
                                    <CircularProgress size={14} color="inherit"/>
                                ) : (
                                    <RefreshIcon sx={{fontSize: 14}}/>
                                )}
                            </IconButton>
                        </span>
                    </Tooltip>
                )}
            </AccordionSummary>

            <AccordionDetails sx={{pt: 0, pb: 1.5, px: 1.5}}>
                <Stack spacing={1}>
                    {error && <Alert severity="error" variant="outlined">{error}</Alert>}

                    {!folderExists && (
                        <Alert severity="warning" variant="outlined">
                            <Typography variant="caption" sx={{display: "block"}}>
                                Recording folder does not exist yet. It will be created when you start recording.
                            </Typography>
                            {recordingFolderPath && (
                                <Typography
                                    variant="caption"
                                    sx={{
                                        fontFamily: "monospace",
                                        display: "block",
                                        wordBreak: "break-all",
                                        mt: 0.5,
                                    }}
                                >
                                    {recordingFolderPath}
                                </Typography>
                            )}
                        </Alert>
                    )}

                    {activeCalibrationTomlPath && (
                        <Box>
                            <Typography variant="caption" color="text.secondary">
                                Active calibration TOML:
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
                                {activeCalibrationTomlPath}
                            </Typography>
                        </Box>
                    )}

                    {!status && !isLoading && !error && (
                        <Typography variant="caption" color="text.secondary">
                            No status loaded.
                        </Typography>
                    )}

                    {status && (
                        <>
                            <Box>
                                {status.stages.map((stage) => (
                                    <Accordion
                                        key={stage.name}
                                        defaultExpanded={false}
                                        disableGutters
                                        square
                                        sx={{
                                            "&:before": {display: "none"},
                                            bgcolor: "transparent",
                                            boxShadow: "none",
                                            border: `1px solid ${theme.palette.divider}`,
                                            mb: 0.5,
                                        }}
                                    >
                                        <AccordionSummary
                                            expandIcon={<ExpandMoreIcon/>}
                                            sx={{minHeight: 32, "& .MuiAccordionSummary-content": {my: 0.5}}}
                                        >
                                            <Stack direction="row" spacing={1} alignItems="center">
                                                {stage.complete ? (
                                                    <CheckCircleIcon
                                                        fontSize="small"
                                                        sx={{color: theme.palette.success.main}}
                                                    />
                                                ) : (
                                                    <CloseIcon
                                                        fontSize="small"
                                                        sx={{color: theme.palette.grey[500]}}
                                                    />
                                                )}
                                                <Typography variant="body2">{stage.name}</Typography>
                                                <Typography variant="caption" color="text.secondary">
                                                    {stage.present_count}/{stage.total_count}
                                                </Typography>
                                            </Stack>
                                        </AccordionSummary>
                                        <AccordionDetails sx={{pt: 0, pb: 1}}>
                                            {stage.files.length === 0 ? (
                                                <Typography variant="caption" color="text.secondary">
                                                    No files found.
                                                </Typography>
                                            ) : (
                                                <Stack spacing={0.25}>
                                                    {stage.files.map((f) => (
                                                        <Box
                                                            key={f.path ?? f.name}
                                                            sx={{
                                                                display: "flex",
                                                                alignItems: "center",
                                                                gap: 1,
                                                                fontFamily: "monospace",
                                                            }}
                                                        >
                                                            {f.exists ? (
                                                                <CheckCircleIcon
                                                                    sx={{
                                                                        fontSize: 14,
                                                                        color: theme.palette.success.main,
                                                                    }}
                                                                />
                                                            ) : (
                                                                <CloseIcon
                                                                    sx={{
                                                                        fontSize: 14,
                                                                        color: theme.palette.grey[500],
                                                                    }}
                                                                />
                                                            )}
                                                            <Typography
                                                                variant="caption"
                                                                sx={{
                                                                    fontFamily: "monospace",
                                                                    color: f.exists
                                                                        ? "text.primary"
                                                                        : "text.secondary",
                                                                    flex: 1,
                                                                    wordBreak: "break-all",
                                                                }}
                                                            >
                                                                {f.name}
                                                            </Typography>
                                                            {f.exists && (
                                                                <>
                                                                    <Typography variant="caption" color="text.secondary">
                                                                        {humanizeBytes(f.size_bytes)}
                                                                    </Typography>
                                                                    <Typography variant="caption" color="text.secondary">
                                                                        {formatTimestamp(f.modified_timestamp)}
                                                                    </Typography>
                                                                </>
                                                            )}
                                                        </Box>
                                                    ))}
                                                </Stack>
                                            )}
                                        </AccordionDetails>
                                    </Accordion>
                                ))}
                            </Box>
                        </>
                    )}
                </Stack>
            </AccordionDetails>
        </Accordion>
    );
};
