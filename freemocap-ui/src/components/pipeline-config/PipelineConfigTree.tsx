import React, {useState} from "react";
import {Box, Typography, useTheme} from "@mui/material";
import {SimpleTreeView} from "@mui/x-tree-view/SimpleTreeView";
import ExpandMore from "@mui/icons-material/ExpandMore";
import ChevronRight from "@mui/icons-material/ChevronRight";

import {PipelineStageTreeItem} from "./PipelineStageTreeItem";
import {MediapipeConfigPanel} from "@/components/mocap-control-panel/MediapipeConfigPanel";
import {SkeletonFilterConfigPanel} from "@/components/mocap-control-panel/SkeletonFilterConfigPanel";

export type PipelineContext = "realtime" | "posthoc";

interface PipelineConfigTreeProps {
    context: PipelineContext;
    // 2D Tracking stage toggles
    charucoEnabled: boolean;
    onCharucoToggle: (checked: boolean) => void;
    skeletonEnabled: boolean;
    onSkeletonToggle: (checked: boolean) => void;
    // 3D Reconstruction stage toggles
    triangulateEnabled: boolean;
    onTriangulateToggle: (checked: boolean) => void;
    filterEnabled: boolean;
    onFilterToggle: (checked: boolean) => void;
    rigidBodyEnabled: boolean;
    onRigidBodyToggle: (checked: boolean) => void;
    // Disable all controls (e.g. pipeline not connected)
    disabled?: boolean;
    disabledReason?: string;
}

export const PipelineConfigTree: React.FC<PipelineConfigTreeProps> = ({
    context,
    charucoEnabled,
    onCharucoToggle,
    skeletonEnabled,
    onSkeletonToggle,
    triangulateEnabled,
    onTriangulateToggle,
    filterEnabled,
    onFilterToggle,
    rigidBodyEnabled,
    onRigidBodyToggle,
    disabled = false,
    disabledReason,
}) => {
    const theme = useTheme();
    const [expandedItems, setExpandedItems] = useState<string[]>([]);

    const isExpanded = (id: string) => expandedItems.includes(id);

    // Derive parent-level checked state
    const tracking2dEnabled = charucoEnabled || skeletonEnabled;
    const reconstruction3dEnabled = triangulateEnabled || filterEnabled || rigidBodyEnabled;

    const handleToggle2dTracking = (checked: boolean) => {
        onCharucoToggle(checked);
        onSkeletonToggle(checked);
    };

    const handleToggle3dReconstruction = (checked: boolean) => {
        onTriangulateToggle(checked);
        onFilterToggle(checked);
        onRigidBodyToggle(checked);
    };

    return (
        <SimpleTreeView
            expandedItems={expandedItems}
            onExpandedItemsChange={(_, items) => setExpandedItems(items)}
            slots={{
                collapseIcon: ExpandMore,
                expandIcon: ChevronRight,
            }}
        >
            {/* ── 2D Tracking ── */}
            <PipelineStageTreeItem
                itemId="2d-tracking"
                label="2D Tracking"
                checked={tracking2dEnabled}
                onToggle={handleToggle2dTracking}
                disabled={disabled}
                disabledReason={disabledReason}
                isExpanded={isExpanded("2d-tracking")}
                summaryWhenCollapsed={
                    [charucoEnabled && "Charuco", skeletonEnabled && "Skeleton"]
                        .filter(Boolean)
                        .join(" + ") || "Off"
                }
            >
                {/* Charuco */}
                <PipelineStageTreeItem
                    itemId="2d-charuco"
                    label="Charuco"
                    checked={charucoEnabled}
                    onToggle={onCharucoToggle}
                    disabled={disabled}
                    disabledReason={disabledReason}
                    isExpanded={isExpanded("2d-charuco")}
                >
                    <Box sx={{p: 1, pl: 2}}>
                        <Typography variant="caption" color="text.secondary">
                            Charuco board detection settings (uses calibration config)
                        </Typography>
                    </Box>
                </PipelineStageTreeItem>

                {/* Skeleton (MediaPipe) */}
                <PipelineStageTreeItem
                    itemId="2d-skeleton"
                    label="Skeleton"
                    checked={skeletonEnabled}
                    onToggle={onSkeletonToggle}
                    disabled={disabled}
                    disabledReason={disabledReason}
                    isExpanded={isExpanded("2d-skeleton")}
                    summaryWhenCollapsed={context === "realtime" ? "Realtime preset" : "Posthoc preset"}
                >
                    <Box sx={{p: 1, pl: 2, borderLeft: `2px solid ${theme.palette.divider}`}}>
                        <MediapipeConfigPanel />
                    </Box>
                </PipelineStageTreeItem>
            </PipelineStageTreeItem>

            {/* ── 3D Reconstruction ── */}
            <PipelineStageTreeItem
                itemId="3d-reconstruction"
                label="3D Reconstruction"
                checked={reconstruction3dEnabled}
                onToggle={handleToggle3dReconstruction}
                disabled={disabled}
                disabledReason={disabledReason}
                isExpanded={isExpanded("3d-reconstruction")}
                summaryWhenCollapsed={
                    [triangulateEnabled && "Triangulate", filterEnabled && "Filter", rigidBodyEnabled && "Skeleton"]
                        .filter(Boolean)
                        .join(" + ") || "Off"
                }
            >
                {/* Triangulate */}
                <PipelineStageTreeItem
                    itemId="3d-triangulate"
                    label="Triangulate"
                    checked={triangulateEnabled}
                    onToggle={onTriangulateToggle}
                    disabled={disabled}
                    disabledReason={disabledReason}
                    isExpanded={isExpanded("3d-triangulate")}
                >
                    <Box sx={{p: 1, pl: 2}}>
                        <Typography variant="caption" color="text.secondary">
                            Triangulation settings — calibration TOML picker and parameters (placeholder)
                        </Typography>
                    </Box>
                </PipelineStageTreeItem>

                {/* Filter */}
                <PipelineStageTreeItem
                    itemId="3d-filter"
                    label="Filter"
                    checked={filterEnabled}
                    onToggle={onFilterToggle}
                    disabled={disabled}
                    disabledReason={disabledReason}
                    isExpanded={isExpanded("3d-filter")}
                    summaryWhenCollapsed="One Euro, FABRIK"
                >
                    <Box sx={{p: 1, pl: 2, borderLeft: `2px solid ${theme.palette.divider}`}}>
                        <SkeletonFilterConfigPanel />
                    </Box>
                </PipelineStageTreeItem>

                {/* Skeleton (rigid body) */}
                <PipelineStageTreeItem
                    itemId="3d-skeleton"
                    label="Skeleton"
                    checked={rigidBodyEnabled}
                    onToggle={onRigidBodyToggle}
                    disabled={disabled}
                    disabledReason={disabledReason}
                    isExpanded={isExpanded("3d-skeleton")}
                >
                    <Box sx={{p: 1, pl: 2}}>
                        <Typography variant="caption" color="text.secondary">
                            Rigid body and skeleton reconstruction parameters (placeholder)
                        </Typography>
                    </Box>
                </PipelineStageTreeItem>
            </PipelineStageTreeItem>
        </SimpleTreeView>
    );
};
