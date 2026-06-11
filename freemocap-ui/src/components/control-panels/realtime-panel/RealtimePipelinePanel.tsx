import React from "react";
import {CollapsibleSidebarSection} from "@/components/common/CollapsibleSidebarSection";
import {RealtimePipelineSummary} from "@/components/control-panels/realtime-panel/RealtimePipelineSummary";
import {RealtimePipelineConnectionToggle} from "@/components/control-panels/realtime-panel/RealtimePipelineConnectionToggle";
import {RealtimePipelineConfigTree} from "@/components/control-panels/realtime-panel/RealtimePipelineConfigTree";
import {useRealtimePipelineSync} from "@/hooks/useRealtimePipelineSync";

export const RealtimePipelinePanel: React.FC = () => {
    const {pipelineConfig, cameraNodeConfig, aggregatorConfig, applyOrUpdatePipelineConfig} = useRealtimePipelineSync();

    const handleCharucoToggle = (value: boolean) =>
        applyOrUpdatePipelineConfig({
            ...pipelineConfig,
            camera_node_config: {...cameraNodeConfig, charuco_tracking_enabled: value},
        });

    const handleSkeletonToggle = (value: boolean) =>
        applyOrUpdatePipelineConfig({
            ...pipelineConfig,
            camera_node_config: {...cameraNodeConfig, skeleton_tracking_enabled: value},
        });

    const handleTriangulateToggle = (value: boolean) =>
        applyOrUpdatePipelineConfig({
            ...pipelineConfig,
            aggregator_config: {...aggregatorConfig, triangulation_enabled: value},
        });

    const handleFilterToggle = (value: boolean) =>
        applyOrUpdatePipelineConfig({
            ...pipelineConfig,
            aggregator_config: {...aggregatorConfig, filter_enabled: value},
        });

    const handleRigidBodyToggle = (value: boolean) =>
        applyOrUpdatePipelineConfig({
            ...pipelineConfig,
            aggregator_config: {...aggregatorConfig, skeleton_enabled: value},
        });

    return (
        <CollapsibleSidebarSection
            icon={<span className="icon streaming-icon icon-size-20" />}
            title="Realtime Pipeline"
            summaryContent={<RealtimePipelineSummary />}
            primaryControl={<RealtimePipelineConnectionToggle />}
            defaultExpanded={false}
        >
            <div className="p-2">
                <RealtimePipelineConfigTree
                    context="realtime"
                    charucoEnabled={cameraNodeConfig.charuco_tracking_enabled}
                    onCharucoToggle={handleCharucoToggle}
                    skeletonEnabled={cameraNodeConfig.skeleton_tracking_enabled}
                    onSkeletonToggle={handleSkeletonToggle}
                    triangulateEnabled={aggregatorConfig.triangulation_enabled}
                    onTriangulateToggle={handleTriangulateToggle}
                    filterEnabled={aggregatorConfig.filter_enabled}
                    onFilterToggle={handleFilterToggle}
                    rigidBodyEnabled={aggregatorConfig.skeleton_enabled}
                    onRigidBodyToggle={handleRigidBodyToggle}
                />
            </div>
        </CollapsibleSidebarSection>
    );
};
