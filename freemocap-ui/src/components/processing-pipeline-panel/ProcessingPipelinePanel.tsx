import React from "react";
import {Box, Button, Typography, useTheme} from "@mui/material";
import {SimpleTreeView} from "@mui/x-tree-view/SimpleTreeView";
import {TreeItem} from "@mui/x-tree-view/TreeItem";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import ChevronRightIcon from "@mui/icons-material/ChevronRight";
import {useAppDispatch} from "@/store/AppStateStore";
import {
    StartStopRecordingButton
} from "@/components/recording-info-panel/recording-subcomponents/StartStopRecordingButton";
import {RecordingPathTreeItem} from "@/components/recording-info-panel/RecordingPathTreeItem";
import LanIcon from '@mui/icons-material/Lan';
import {
    FullRecordingPathPreview
} from "@/components/recording-info-panel/recording-subcomponents/FullRecordingPathPreview";
import PipelineConnectionStatus from "@/components/processing-pipeline-panel/PipelineConnectionStatus";

export const ProcessingPipelinePanel: React.FC = () => {
    const theme = useTheme();
    const dispatch = useAppDispatch();

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
                            <LanIcon sx={{transform: 'scaleY(-1.3) scaleX(1.25)'}}/>

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
