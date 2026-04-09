import React from "react";
import {Box, Checkbox, Chip, Tooltip, Typography, useTheme} from "@mui/material";
import {TreeItem} from "@mui/x-tree-view/TreeItem";

interface PipelineStageTreeItemProps {
    itemId: string;
    label: string;
    checked: boolean;
    indeterminate?: boolean; // NEW: partial-child-selected state
    onToggle: (newValue: boolean) => void;
    disabled?: boolean;
    disabledReason?: string;
    summaryWhenCollapsed?: string;
    isExpanded?: boolean;
    children?: React.ReactNode;
}

export const RealtimePipelineStageTreeItem: React.FC<PipelineStageTreeItemProps> = ({
                                                                                        itemId,
                                                                                        label,
                                                                                        checked,
                                                                                        indeterminate = false,
                                                                                        onToggle,
                                                                                        disabled = false,
                                                                                        disabledReason,
                                                                                        summaryWhenCollapsed,
                                                                                        isExpanded = false,
                                                                                        children,
                                                                                    }) => {
    const theme = useTheme();

    const handleCheckboxClick = (e: React.MouseEvent) => {
        e.stopPropagation();
        if (!disabled) {
            // When indeterminate, clicking should turn everything ON (not toggle)
            onToggle(indeterminate ? true : !checked);
        }
    };

    const checkbox = (
        <Checkbox
            size="small"
            checked={checked}
            indeterminate={indeterminate}
            disabled={disabled}
            onClick={handleCheckboxClick}
            sx={{p: 0.5, flexShrink: 0}}
        />
    );

    const labelContent = (
        <Box
            sx={{
                display: "flex",
                alignItems: "center",
                py: 0.25,
                minHeight: 32,
                gap: 0.5,
            }}
        >
            {disabled && disabledReason ? (
                <Tooltip title={disabledReason} arrow>
                    <span>{checkbox}</span>
                </Tooltip>
            ) : (
                checkbox
            )}

            <Typography
                variant="body2"
                sx={{
                    flexShrink: 0,
                    color: disabled
                        ? theme.palette.text.disabled
                        : theme.palette.text.primary,
                }}
            >
                {label}
            </Typography>

            {!isExpanded && summaryWhenCollapsed && (
                <Chip
                    label={summaryWhenCollapsed}
                    size="small"
                    variant="outlined"
                    sx={{
                        ml: 0.5,
                        height: 18,
                        fontSize: 10,
                        "& .MuiChip-label": {px: 0.75},
                        borderColor: theme.palette.divider,
                        color: theme.palette.text.secondary,
                    }}
                />
            )}
        </Box>
    );

    return (
        <TreeItem itemId={itemId} label={labelContent}>
            {children}
        </TreeItem>
    );
};
