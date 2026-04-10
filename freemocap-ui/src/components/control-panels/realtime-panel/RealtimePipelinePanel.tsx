import React from "react";
import {Box} from "@mui/material";
import LanIcon from "@mui/icons-material/Lan";
import {CollapsibleSidebarSection} from "@/components/common/CollapsibleSidebarSection";
import {useAppDispatch, useAppSelector} from "@/store/hooks";
import {RealtimePipelineSummary} from "@/components/control-panels/realtime-panel/RealtimePipelineSummary";
import {RealtimePipelineConnectionToggle} from "@/components/control-panels/realtime-panel/RealtimePipelineConnectionToggle";
import {RealtimePipelineConfigTree} from "@/components/control-panels/realtime-panel/RealtimePipelineConfigTree";
import {
    applyRealtimePipeline,
    pipelineConfigUpdated,
    selectAggregatorConfig,
    selectCameraNodeConfig,
    selectIsPipelineConnected,
    selectPipelineConfig,
} from "@/store/slices/realtime";
import {RealtimePipelineConfig} from "@/store/slices/realtime/realtime-types";

export const RealtimePipelinePanel: React.FC = () => {
    const dispatch = useAppDispatch();

    const isConnected = useAppSelector(selectIsPipelineConnected);
    const pipelineConfig = useAppSelector(selectPipelineConfig);
    const cameraNodeConfig = useAppSelector(selectCameraNodeConfig);
    const aggregatorConfig = useAppSelector(selectAggregatorConfig);

    const handleConfigChange = (newConfig: RealtimePipelineConfig) => {
        if (isConnected) {
            dispatch(applyRealtimePipeline(newConfig));
        } else {
            dispatch(pipelineConfigUpdated(newConfig));
        }
    };

    const handleCharucoToggle = (value: boolean) =>
        handleConfigChange({
            ...pipelineConfig,
            camera_node_config: {...cameraNodeConfig, charuco_tracking_enabled: value},
        });

    const handleSkeletonToggle = (value: boolean) =>
        handleConfigChange({
            ...pipelineConfig,
            camera_node_config: {...cameraNodeConfig, skeleton_tracking_enabled: value},
        });

    const handleTriangulateToggle = (value: boolean) =>
        handleConfigChange({
            ...pipelineConfig,
            aggregator_config: {...aggregatorConfig, triangulation_enabled: value},
        });

    const handleFilterToggle = (value: boolean) =>
        handleConfigChange({
            ...pipelineConfig,
            aggregator_config: {...aggregatorConfig, filter_enabled: value},
        });

    const handleRigidBodyToggle = (value: boolean) =>
        handleConfigChange({
            ...pipelineConfig,
            aggregator_config: {...aggregatorConfig, skeleton_enabled: value},
        });

    return (
        <CollapsibleSidebarSection
            icon={<LanIcon sx={{transform: "scaleY(-1.05)", color: "inherit"}} />}
            title="Realtime Pipeline"
            summaryContent={<RealtimePipelineSummary />}
            primaryControl={<RealtimePipelineConnectionToggle />}
            defaultExpanded={false}
        >
            <Box sx={{p: 2}}>
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
            </Box>
        </CollapsibleSidebarSection>
    );
};
