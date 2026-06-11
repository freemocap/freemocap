import React, {useCallback} from "react";
import {RealtimePipelineStageTreeItem} from "./RealtimePipelineStageTreeItem";
import {MediapipeConfigPanel} from "@/components/control-panels/mocap-control-panel/MediapipeConfigPanel";
import {SkeletonFilterConfigPanel} from "@/components/control-panels/mocap-control-panel/SkeletonFilterConfigPanel";
import {useMocap} from "@/hooks/useMocap";
import {useRealtimePipelineSync} from "@/hooks/useRealtimePipelineSync";
import {MediapipeDetectorConfig, RealtimeFilterConfig} from "@/store/slices/mocap";

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
    const {
        updateDetectorConfigLocalOnly,
        replaceDetectorConfigLocalOnly,
        updateSkeletonFilterConfigLocalOnly,
        replaceSkeletonFilterConfigLocalOnly,
    } = useMocap();
    const {triggerRealtimeApply} = useRealtimePipelineSync();

    const handleUpdateDetectorConfig = useCallback(
        (updates: Partial<MediapipeDetectorConfig>) => {
            updateDetectorConfigLocalOnly(updates);
            if (context === "realtime") triggerRealtimeApply();
        },
        [updateDetectorConfigLocalOnly, context, triggerRealtimeApply]
    );

    const handleReplaceDetectorConfig = useCallback(
        (config: MediapipeDetectorConfig) => {
            replaceDetectorConfigLocalOnly(config);
            if (context === "realtime") triggerRealtimeApply();
        },
        [replaceDetectorConfigLocalOnly, context, triggerRealtimeApply]
    );

    const handleUpdateSkeletonFilterConfig = useCallback(
        (updates: Partial<RealtimeFilterConfig>) => {
            updateSkeletonFilterConfigLocalOnly(updates);
            if (context === "realtime") triggerRealtimeApply();
        },
        [updateSkeletonFilterConfigLocalOnly, context, triggerRealtimeApply]
    );

    const handleReplaceSkeletonFilterConfig = useCallback(
        (config: RealtimeFilterConfig) => {
            replaceSkeletonFilterConfigLocalOnly(config);
            if (context === "realtime") triggerRealtimeApply();
        },
        [replaceSkeletonFilterConfigLocalOnly, context, triggerRealtimeApply]
    );


    // ── 2D Tracking parent state ──────────────────────────────────────────────
    const tracking2dAllOn = charucoEnabled && skeletonEnabled;
    const tracking2dSomeOn = charucoEnabled || skeletonEnabled;
    const tracking2dIndeterminate = tracking2dSomeOn && !tracking2dAllOn;
    const tracking2dChecked = tracking2dAllOn;

    // ── 3D Reconstruction parent state ────────────────────────────────────────
    const recon3dAllOn = triangulateEnabled && filterEnabled && rigidBodyEnabled;
    const recon3dSomeOn = triangulateEnabled || filterEnabled || rigidBodyEnabled;
    const recon3dIndeterminate = recon3dSomeOn && !recon3dAllOn;
    const recon3dChecked = recon3dAllOn;

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
        <div className="flex flex-col">
            {/* ── 2D Tracking ── */}
            <RealtimePipelineStageTreeItem
                itemId="2d-tracking"
                label="2D Tracking"
                checked={tracking2dChecked}
                indeterminate={tracking2dIndeterminate}
                onToggle={handleToggle2dTracking}
                
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
                    
                >
                    <div className="p-1 pl-4">
                        <p className="text sm text-gray">
                            Settings from `Post Processing::Capture Volume Calibration` section
                        </p>
                    </div>
                </RealtimePipelineStageTreeItem>

                {/* Skeleton (MediaPipe) */}
                <RealtimePipelineStageTreeItem
                    itemId="2d-skeleton"
                    label="Skeleton"
                    checked={skeletonEnabled}
                    onToggle={onSkeletonToggle}
                    
                    summaryWhenCollapsed={context === "realtime" ? "Realtime preset" : "Posthoc preset"}
                >
                    <div className="p-1 border-1 border-mid-black pl-4" style={{borderLeft: '2px solid var(--color-border-secondary)'}}>
                        <MediapipeConfigPanel
                            updateDetectorConfig={handleUpdateDetectorConfig}
                            replaceDetectorConfig={handleReplaceDetectorConfig}
                        />
                    </div>
                </RealtimePipelineStageTreeItem>
            </RealtimePipelineStageTreeItem>

            {/* ── 3D Reconstruction ── */}
            <RealtimePipelineStageTreeItem
                itemId="3d-reconstruction"
                label="3D Reconstruction"
                checked={recon3dChecked}
                indeterminate={recon3dIndeterminate}
                onToggle={handleToggle3dReconstruction}
                
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
                    
                >
                    <div className="p-1 pl-4">
                        <p className="text sm text-gray">
                            Triangulation settings — calibration TOML picker and parameters (placeholder)
                        </p>
                    </div>
                </RealtimePipelineStageTreeItem>

                {/* Filter */}
                <RealtimePipelineStageTreeItem
                    itemId="3d-filter"
                    label="Filter"
                    checked={filterEnabled}
                    onToggle={onFilterToggle}
                    
                    summaryWhenCollapsed="One Euro, FABRIK"
                >
                    <div className="p-1 pl-4" style={{borderLeft: '2px solid var(--color-border-secondary)'}}>
                        <SkeletonFilterConfigPanel
                            updateSkeletonFilterConfig={handleUpdateSkeletonFilterConfig}
                            replaceSkeletonFilterConfig={handleReplaceSkeletonFilterConfig}
                        />
                    </div>
                </RealtimePipelineStageTreeItem>

                {/* Skeleton (rigid body) */}
                <RealtimePipelineStageTreeItem
                    itemId="3d-skeleton"
                    label="Skeleton"
                    checked={rigidBodyEnabled}
                    onToggle={onRigidBodyToggle}
                    
                >
                    <div className="p-1 pl-4">
                        <p className="text sm text-gray">
                            Rigid body and skeleton reconstruction parameters (placeholder)
                        </p>
                    </div>
                </RealtimePipelineStageTreeItem>
            </RealtimePipelineStageTreeItem>
        </div>
    );
};
