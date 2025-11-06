import React, { useState } from "react";
import { Box, Typography, useTheme } from "@mui/material";
import { SimpleTreeView } from "@mui/x-tree-view/SimpleTreeView";
import { TreeItem } from "@mui/x-tree-view/TreeItem";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import ChevronRightIcon from "@mui/icons-material/ChevronRight";
import LanIcon from '@mui/icons-material/Lan';
import PipelineConnectionStatus from "@/components/processing-pipeline-panel/PipelineConnectionStatus";
import {CalibrationTaskTreeItem} from "@/components/calibration-task/CalibrationTaskTreeItem";
import {MocapTaskTreeItem} from "@/components/processing-pipeline-panel/MocapTaskTreeItem";
import {RecordingControlsSection} from "@/components/recording-info-panel/RecordingControlsTreeSection";
import {RecordingInfoPanel} from "@/components/recording-info-panel/RecordingInfoPanel";

export const ProcessingPipelinePanel: React.FC = () => {
    const theme = useTheme();
    const [expandedItems, setExpandedItems] = useState<string[]>([
        'pipeline-main',
        'calibration-intrinsic',
        'calibration-extrinsic',
        'mocap-task'
    ]);

    const handleExpandedItemsChange = (
        event: React.SyntheticEvent,
        itemIds: string[]
    ): void => {
        setExpandedItems(itemIds);
    };

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
                expandedItems={expandedItems}
                onExpandedItemsChange={handleExpandedItemsChange}
                slots={{
                    collapseIcon: ExpandMoreIcon,
                    expandIcon: ChevronRightIcon,
                }}
                sx={{ flexGrow: 1 }}
            >
                <TreeItem
                    itemId="pipeline-main"
                    label={
                        <Box
                            sx={{
                                display: "flex",
                                alignItems: "center",
                                width: "100%",
                                py: 1,
                            }}
                        >
                            <LanIcon sx={{ transform: 'scaleY(-1.05) scaleX(1)' }} />

                            <Typography sx={{ pl: 1, flexGrow: 1 }} variant="h6" component="div">
                                Data Processing Pipeline
                            </Typography>
                            <PipelineConnectionStatus />
                        </Box>
                    }
                >
                    <RecordingInfoPanel/>
                    <CalibrationTaskTreeItem />
                    <MocapTaskTreeItem />
                </TreeItem>
            </SimpleTreeView>
        </Box>
    );
};
