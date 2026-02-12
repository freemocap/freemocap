import React from "react";
import {Box, Typography} from "@mui/material";
import LanIcon from "@mui/icons-material/Lan";
import {CollapsibleSidebarSection} from "@/components/common/CollapsibleSidebarSection";
import {PipelineConnectionToggle} from "@/components/processing-pipeline-panel/PipelineConnectionToggle";
import {PipelineSummary} from "@/components/processing-pipeline-panel/PipelineSummary";

export const ProcessingPipelinePanel: React.FC = () => {
    return (
        <CollapsibleSidebarSection
            icon={<LanIcon sx={{transform: "scaleY(-1.05)", color: "inherit"}} />}
            title="Realtime Pipeline"
            summaryContent={<PipelineSummary />}
            primaryControl={<PipelineConnectionToggle />}
            defaultExpanded={false}
        >
            {/* Future: tracker selection (MediaPipe/Truco), per-tracker settings,
                aggregation toggles (triangulation, one-euro, IK),
                visualization layer toggles */}
            <Box sx={{p: 2}}>
                <Typography variant="body2" color="text.secondary">
                    Pipeline settings will appear here — tracker selection, aggregation stages, visualization toggles.
                </Typography>
            </Box>
        </CollapsibleSidebarSection>
    );
};
