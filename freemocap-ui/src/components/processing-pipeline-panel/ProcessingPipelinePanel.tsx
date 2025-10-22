import React from "react";
import {Box, Button, Typography, useTheme} from "@mui/material";
import {SimpleTreeView} from "@mui/x-tree-view/SimpleTreeView";
import {TreeItem} from "@mui/x-tree-view/TreeItem";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import ChevronRightIcon from "@mui/icons-material/ChevronRight";
import LanIcon from '@mui/icons-material/Lan';
import PipelineConnectionStatus from "@/components/processing-pipeline-panel/PipelineConnectionStatus";

export const ProcessingPipelinePanel: React.FC = () => {
    const theme = useTheme();

    return (
        <Box
            sx={{
                color: "text.primary",
                backgroundColor: theme.palette.primary.main,
                borderRadius: 1,
                mb: 2,
            }}
        >
            <SimpleTreeView
                slots={{
                    collapseIcon: ExpandMoreIcon,
                    expandIcon: ChevronRightIcon,
                }}
                sx={{flexGrow: 1}}
            >
                <TreeItem
                    itemId="calibration-pipeline-main"
                    label={
                        <Box
                            sx={{
                                display: "flex",
                                alignItems: "center",
                                width: "100%",
                                r: 2,
                            }}
                        >
                            <LanIcon sx={{transform: 'scaleY(-1.05) scaleX(1)'}}/>

                            <Typography sx={{pl: 1, flexGrow: 1}} variant="h6" component="div">
                                Data Processing
                            </Typography>
                            <PipelineConnectionStatus/>
                        </Box>
                    }
                >
                    <Box sx={{display: 'flex', alignItems: 'center', gap: 1}}>
                        tree stuff
                    </Box>
                </TreeItem>
            </SimpleTreeView>
        </Box>
    );
};
