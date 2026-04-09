import React, {useState} from "react";
import {Box} from "@mui/material";
import LanIcon from "@mui/icons-material/Lan";
import {CollapsibleSidebarSection} from "@/components/common/CollapsibleSidebarSection";
import {useAppSelector} from "@/store/hooks";
import {selectBackendPipeline} from "@/store/slices/settings";
import {useServer} from "@/services";
import {RealtimePipelineSummary} from "@/components/control-panels/realtime-panel/RealtimePipelineSummary";
import {
    RealtimePipelineConnectionToggle
} from "@/components/control-panels/realtime-panel/RealtimePipelineConnectionToggle";
import {RealtimePipelineConfigTree} from "@/components/control-panels/realtime-panel/RealtimePipelineConfigTree";

export const RealtimePipelinePanel: React.FC = () => {
    const {sendWebsocketMessage, isConnected: serverConnected} = useServer();
    const backendPipeline = useAppSelector(selectBackendPipeline);
    const pipelineConfig = backendPipeline?.config;

    // ── 2D Tracking: optimistic local state ───────────────────────────────────
    // Local state is the source of truth for the UI. When the backend is
    // connected and echoes a value back via Redux, we sync local state to it.
    // When the backend is disconnected, clicks still work — send() is just a
    // no-op side effect.
    const [charucoEnabled, setCharucoEnabled] = useState(false);
    const [skeletonEnabled, setSkeletonEnabled] = useState(false);

    // Sync from backend when it comes online (or when config changes)
    React.useEffect(() => {
        if (pipelineConfig == null) return;
        setCharucoEnabled(pipelineConfig.calibration_detection_enabled ?? false);
        setSkeletonEnabled(pipelineConfig.mocap_detection_enabled ?? false);
    }, [pipelineConfig]);

    const handleCharucoToggle = (newValue: boolean) => {
        setCharucoEnabled(newValue); // update UI immediately
        if (serverConnected) {
            sendWebsocketMessage({
                message_type: "settings/patch",
                patch: {pipeline: {config: {calibration_detection_enabled: newValue}}},
            });
        }
    };

    const handleSkeletonToggle = (newValue: boolean) => {
        setSkeletonEnabled(newValue); // update UI immediately
        if (serverConnected) {
            sendWebsocketMessage({
                message_type: "settings/patch",
                patch: {pipeline: {config: {mocap_detection_enabled: newValue}}},
            });
        }
    };

    // ── 3D Reconstruction: local state (backend doesn't have these yet) ───────
    const [triangulateEnabled, setTriangulateEnabled] = useState(false);
    const [filterEnabled, setFilterEnabled] = useState(false);
    const [rigidBodyEnabled, setRigidBodyEnabled] = useState(false);

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
                    charucoEnabled={charucoEnabled}
                    onCharucoToggle={handleCharucoToggle}
                    skeletonEnabled={skeletonEnabled}
                    onSkeletonToggle={handleSkeletonToggle}
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
