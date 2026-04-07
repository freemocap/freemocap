import React from "react";
import {Box} from "@mui/material";
import BuildIcon from "@mui/icons-material/Build";
import {CollapsibleSidebarSection} from "@/components/common/CollapsibleSidebarSection";
import {CalibrationSubsection} from "@/components/post-processing-panel/CalibrationSubsection";
import {MocapSubsection} from "@/components/post-processing-panel/MocapSubsection";

export const PostProcessingPanel: React.FC = () => {
    return (
        <CollapsibleSidebarSection
            icon={<BuildIcon sx={{color: "inherit"}} />}
            title="Post Processing"
            defaultExpanded={false}
        >
            <Box sx={{p: 1}}>
                <CalibrationSubsection />
                <MocapSubsection />
            </Box>
        </CollapsibleSidebarSection>
    );
};
