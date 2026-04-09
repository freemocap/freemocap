import React, {useState} from "react";
import {Box, Typography, useTheme} from "@mui/material";
import {SimpleTreeView} from "@mui/x-tree-view/SimpleTreeView";
import ExpandMore from "@mui/icons-material/ExpandMore";
import ChevronRight from "@mui/icons-material/ChevronRight";

import {RealtimePipelineStageTreeItem} from "./RealtimePipelineStageTreeItem";
import {MediapipeConfigPanel} from "@/components/control-panels/mocap-control-panel/MediapipeConfigPanel";
import {SkeletonFilterConfigPanel} from "@/components/control-panels/mocap-control-panel/SkeletonFilterConfigPanel";

export type PipelineContext = "realtime" | "posthoc";

interface PipelineConfigTreeProps {
    context: PipelineContext;
    // 2D Tracking stage toggles
    charucoEnabled: boolean;
    onCharucoToggle: (newValue: boolean) => void;
    skeletonEnabled: boolean;
    onSkeletonToggle: (newValue: boolean) => void;
    // 3D Reconstruction stage toggles
    triangulateEnabled: boolean;
    onTriangulateToggle: (newValue: boolean) => void;
    filterEnabled: boolean;
    onFilterToggle: (newValue: boolean) => void;
    rigidBodyEnabled: boolean;
    onRigidBodyToggle: (newValue: boolean) => void;
}

export const RealtimePipelineConfigTree: React.FC<PipelineConfigTreeProps> = ({
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
                                                                              }) => {
    const theme = useTheme();
    const [expandedItems, setExpandedItems] = useState<string[]>([]);

    const isExpanded = (id: string) => expandedItems.includes(id);

    // ── 2D Tracking parent state ──────────────────────────────────────────────
    // all on → checked; some on → indeterminate; none on → unchecked
    const tracking2dAllOn = charucoEnabled && skeletonEnabled;
    const tracking2dSomeOn = charucoEnabled || skeletonEnabled;
    const tracking2dIndeterminate = tracking2dSomeOn && !tracking2dAllOn;
    const tracking2dChecked = tracking2dAllOn;

    // ── 3D Reconstruction parent state ────────────────────────────────────────
    const recon3dAllOn = triangulateEnabled && filterEnabled && rigidBodyEnabled;
    const recon3dSomeOn = triangulateEnabled || filterEnabled || rigidBodyEnabled;
    const recon3dIndeterminate = recon3dSomeOn && !recon3dAllOn;
    const recon3dChecked = recon3dAllOn;

    // Parent handlers receive the resolved newValue from the child
    // (child already handles indeterminate → true logic before calling up)
    const handleToggle2dTracking = (newValue: boolean) => {
        onCharucoToggle(newValue);
        onSkeletonToggle(newValue);
    };

    const handleToggle3dReconstruction = (newValue: boolean) => {
        onTriangulateToggle(newValue);
        onFilterToggle(newValue);
        onRigidBodyToggle(newValue);
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
            <RealtimePipelineStageTreeItem
                itemId="2d-tracking"
                label="2D Tracking"
                checked={tracking2dChecked}
                indeterminate={tracking2dIndeterminate}
                onToggle={handleToggle2dTracking}
                isExpanded={isExpanded("2d-tracking")}
                summaryWhenCollapsed={
                    [charucoEnabled && "Charuco", skeletonEnabled && "Skeleton"]
                        .filter(Boolean)
                        .join(" + ") || "Off"
                }
            >
                {/* Charuco */}
                <RealtimePipelineStageTreeItem
                    itemId="2d-charuco"
                    label="Charuco"
                    checked={charucoEnabled}
                    onToggle={onCharucoToggle}
                    isExpanded={isExpanded("2d-charuco")}
                >
                    <Box sx={{p: 1, pl: 2}}>
                        <Typography variant="caption" color="text.secondary">
                            Settings from `Post Processing::Capture Volume Calibration` section
                        </Typography>
                    </Box>
                </RealtimePipelineStageTreeItem>

                {/* Skeleton (MediaPipe) */}
                <RealtimePipelineStageTreeItem
                    itemId="2d-skeleton"
                    label="Skeleton"
                    checked={skeletonEnabled}
                    onToggle={onSkeletonToggle}
                    isExpanded={isExpanded("2d-skeleton")}
                    summaryWhenCollapsed={context === "realtime" ? "Realtime preset" : "Posthoc preset"}
                >
                    <Box sx={{p: 1, pl: 2, borderLeft: `2px solid ${theme.palette.divider}`}}>
                        <MediapipeConfigPanel/>
                    </Box>
                </RealtimePipelineStageTreeItem>
            </RealtimePipelineStageTreeItem>

            {/* ── 3D Reconstruction ── */}
            <RealtimePipelineStageTreeItem
                itemId="3d-reconstruction"
                label="3D Reconstruction"
                checked={recon3dChecked}
                indeterminate={recon3dIndeterminate}
                onToggle={handleToggle3dReconstruction}
                isExpanded={isExpanded("3d-reconstruction")}
                summaryWhenCollapsed={
                    [triangulateEnabled && "Triangulate", filterEnabled && "Filter", rigidBodyEnabled && "Skeleton"]
                        .filter(Boolean)
                        .join(" + ") || "Off"
                }
            >
                {/* Triangulate */}
                <RealtimePipelineStageTreeItem
                    itemId="3d-triangulate"
                    label="Triangulate"
                    checked={triangulateEnabled}
                    onToggle={onTriangulateToggle}
                    isExpanded={isExpanded("3d-triangulate")}
                >
                    <Box sx={{p: 1, pl: 2}}>
                        <Typography variant="caption" color="text.secondary">
                            Triangulation settings — calibration TOML picker and parameters (placeholder)
                        </Typography>
                    </Box>
                </RealtimePipelineStageTreeItem>

                {/* Filter */}
                <RealtimePipelineStageTreeItem
                    itemId="3d-filter"
                    label="Filter"
                    checked={filterEnabled}
                    onToggle={onFilterToggle}
                    isExpanded={isExpanded("3d-filter")}
                    summaryWhenCollapsed="One Euro, FABRIK"
                >
                    <Box sx={{p: 1, pl: 2, borderLeft: `2px solid ${theme.palette.divider}`}}>
                        <SkeletonFilterConfigPanel/>
                    </Box>
                </RealtimePipelineStageTreeItem>

                {/* Skeleton (rigid body) */}
                <RealtimePipelineStageTreeItem
                    itemId="3d-skeleton"
                    label="Skeleton"
                    checked={rigidBodyEnabled}
                    onToggle={onRigidBodyToggle}
                    isExpanded={isExpanded("3d-skeleton")}
                >
                    <Box sx={{p: 1, pl: 2}}>
                        <Typography variant="caption" color="text.secondary">
                            Rigid body and skeleton reconstruction parameters (placeholder)
                        </Typography>
                    </Box>
                </RealtimePipelineStageTreeItem>
            </RealtimePipelineStageTreeItem>
        </SimpleTreeView>
    );
};
