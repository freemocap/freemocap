import React, {useState} from "react";
import {Box, Typography} from "@mui/material";
import LanIcon from "@mui/icons-material/Lan";
import {CollapsibleSidebarSection} from "@/components/common/CollapsibleSidebarSection";
import {PipelineConnectionToggle} from "@/components/processing-pipeline-panel/PipelineConnectionToggle";
import {PipelineSummary} from "@/components/processing-pipeline-panel/PipelineSummary";
import {useAppSelector} from "@/store/hooks";
import {selectBackendPipeline} from "@/store/slices/settings";
import {PipelineConfigTree} from "@/components/pipeline-config/PipelineConfigTree";
import {useServer} from "@/services";

export const ProcessingPipelinePanel: React.FC = () => {
    const {send, isConnected} = useServer();
    const backendPipeline = useAppSelector(selectBackendPipeline);

    const pipelineConfig = backendPipeline?.config;


    // 3D Reconstruction toggles — local state until backend support is added
    const [triangulateEnabled, setTriangulateEnabled] = useState(false);
    const [filterEnabled, setFilterEnabled] = useState(false);
    const [rigidBodyEnabled, setRigidBodyEnabled] = useState(false);

    const patchPipelineConfig = (patch: Record<string, unknown>) => {
        send({
            message_type: "settings/patch",
            patch: {pipeline: {config: patch}},
        });
    };

    return (
        <CollapsibleSidebarSection
            icon={<LanIcon sx={{transform: "scaleY(-1.05)", color: "inherit"}} />}
            title="Realtime Pipeline"
            summaryContent={<PipelineSummary />}
            primaryControl={<PipelineConnectionToggle />}
            defaultExpanded={false}
        >
            <Box sx={{p: 2}}>

                <PipelineConfigTree
                    context="realtime"
                    charucoEnabled={pipelineConfig?.calibration_detection_enabled ?? true}
                    onCharucoToggle={(v) => patchPipelineConfig({calibration_detection_enabled: v})}
                    skeletonEnabled={pipelineConfig?.mocap_detection_enabled ?? true}
                    onSkeletonToggle={(v) => patchPipelineConfig({mocap_detection_enabled: v})}
                    triangulateEnabled={triangulateEnabled}
                    onTriangulateToggle={setTriangulateEnabled}
                    filterEnabled={filterEnabled}
                    onFilterToggle={setFilterEnabled}
                    rigidBodyEnabled={rigidBodyEnabled}
                    onRigidBodyToggle={setRigidBodyEnabled}
                />
            </Box>
        </CollapsibleSidebarSection>
    );
};
