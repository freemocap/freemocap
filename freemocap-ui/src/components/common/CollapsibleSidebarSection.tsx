import React, {ReactNode, useCallback, useState} from "react";
import {Box, Collapse, Paper, Typography, useTheme} from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import ChevronRightIcon from "@mui/icons-material/ChevronRight";
import DragIndicatorIcon from "@mui/icons-material/DragIndicator";
import {useDragHandle} from "@/components/common/DragHandleContext";

interface CollapsibleSidebarSectionProps {
    icon: ReactNode;
    title: string;
    primaryControl: ReactNode;
    summaryContent: ReactNode;
    children: ReactNode;
    defaultExpanded: boolean;
}

export const CollapsibleSidebarSection: React.FC<CollapsibleSidebarSectionProps> = ({
                                                                                        icon,
                                                                                        title,
                                                                                        primaryControl,
                                                                                        summaryContent,
                                                                                        children,
                                                                                        defaultExpanded,
                                                                                    }) => {
    const theme = useTheme();
    const [expanded, setExpanded] = useState(defaultExpanded);
    const dragHandle = useDragHandle();

    const handleToggle = useCallback(() => {
        setExpanded((prev) => !prev);
    }, []);

    const handlePrimaryControlClick = useCallback((e: React.MouseEvent) => {
        e.stopPropagation();
    }, []);

    return (
        <Paper
            elevation={1}
            sx={{
                borderRadius: 1,
                overflow: "hidden",
            }}
        >
            {/* Header row — always visible, identical whether expanded or collapsed */}
            <Box
                onClick={handleToggle}
                sx={{
                    display: "flex",
                    alignItems: "center",
                    cursor: "pointer",
                    py: 0.75,
                    px: dragHandle ? 0.5 : 1.5,
                    minHeight: 44,
                    backgroundColor: theme.palette.primary.main,
                    color: theme.palette.primary.contrastText,
                    userSelect: "none",
                    transition: "background-color 0.15s ease",
                    "&:hover": {
                        backgroundColor: theme.palette.primary.dark,
                    },
                }}
            >
                {/* Drag handle — only rendered when inside a sortable context */}
                {dragHandle && (
                    <Box
                        {...dragHandle.attributes}
                        {...dragHandle.listeners}
                        onClick={(e: React.MouseEvent) => e.stopPropagation()}
                        sx={{
                            display: "flex",
                            alignItems: "center",
                            cursor: "grab",
                            px: 0.25,
                            mr: 0.25,
                            flexShrink: 0,
                            opacity: 0.35,
                            borderRadius: 0.5,
                            transition: "opacity 0.15s ease, background-color 0.15s ease",
                            "&:hover": {
                                opacity: 0.9,
                                backgroundColor: "rgba(255,255,255,0.1)",
                            },
                            "&:active": {
                                cursor: "grabbing",
                            },
                        }}
                    >
                        <DragIndicatorIcon sx={{fontSize: 18}} />
                    </Box>
                )}

                {/* Expand/collapse chevron */}
                <Box
                    sx={{
                        display: "flex",
                        alignItems: "center",
                        mr: 0.5,
                        flexShrink: 0,
                    }}
                >
                    {expanded ? (
                        <ExpandMoreIcon fontSize="small" />
                    ) : (
                        <ChevronRightIcon fontSize="small" />
                    )}
                </Box>

                {/* Section icon */}
                <Box
                    sx={{
                        display: "flex",
                        alignItems: "center",
                        mr: 1,
                        flexShrink: 0,
                    }}
                >
                    {icon}
                </Box>

                {/* Title */}
                <Typography
                    variant="subtitle1"
                    sx={{
                        fontWeight: 600,
                        flexShrink: 0,
                        lineHeight: 1.3,
                    }}
                >
                    {title}
                </Typography>

                {/* Summary — fills remaining horizontal space */}
                <Box
                    sx={{
                        flexGrow: 1,
                        mx: 1.5,
                        overflow: "hidden",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "flex-end",
                    }}
                >
                    {summaryContent}
                </Box>

                {/* Primary control — click is isolated from expand/collapse */}
                <Box
                    onClick={handlePrimaryControlClick}
                    sx={{
                        flexShrink: 0,
                        display: "flex",
                        alignItems: "center",
                        pr: 0.5,
                    }}
                >
                    {primaryControl}
                </Box>
            </Box>

            {/* Detail panel — only visible when expanded */}
            <Collapse in={expanded} timeout="auto" unmountOnExit>
                <Box
                    sx={{
                        backgroundColor: theme.palette.background.paper,
                    }}
                >
                    {children}
                </Box>
            </Collapse>
        </Paper>
    );
};
