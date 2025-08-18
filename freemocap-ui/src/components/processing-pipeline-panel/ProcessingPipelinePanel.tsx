// skellycam-ui/src/components/available-cameras-panel/AvailableCamerasView.tsx
import {Accordion, AccordionDetails, Box, Paper, Stack, Typography, useTheme,} from "@mui/material";
import * as React from "react";
import AccordionSummary from "@mui/material/AccordionSummary";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import {CameraConfigPanel} from "@/components/available-cameras-panel/CameraConfigPanel";
import {CameraListItem} from "@/components/available-cameras-panel/CameraListItem";
import {useAppDispatch} from "@/store/AppStateStore";
import {ConnectToCamerasButton} from "@/components/available-cameras-panel/ConnectToCamerasButton";
import {CloseCamerasButton} from "@/components/available-cameras-panel/CloseCamerasButton";
import {ApplyCameraConfigsButton} from "@/components/available-cameras-panel/ApplyCameraConfigsButton";
import {PauseUnpauseButton} from "../PauseUnpauseButton";
import LanIcon from '@mui/icons-material/Lan';

export const ProcessingPipelinePanel = () => {
    const theme = useTheme();
    const dispatch = useAppDispatch();




    return (
        <Accordion
            defaultExpanded
            sx={{
                borderRadius: 2,
                "&:before": {display: "none"},
                boxShadow: theme.shadows[3],
                justifyContent: "left",
            }}
        >
            <Box
                sx={{
                    display: "flex",
                    alignItems: "center",
                    backgroundColor: theme.palette.primary.main,
                    borderTopLeftRadius: 8,
                    borderBottomLeftRadius: 8,
                }}
            >
                <AccordionSummary
                    expandIcon={
                        <ExpandMoreIcon
                            sx={{color: theme.palette.primary.contrastText}}
                        />
                    }
                    sx={{
                        flex: 1,
                        color: theme.palette.primary.contrastText,
                        "&:hover": {
                            backgroundColor: theme.palette.primary.light,
                        },
                    }}
                >
                    <Stack direction="row" alignItems="center" spacing={1}>
                        <LanIcon sx={{ transform: 'scaleY(-1.3) scaleX(1.25)' }} />
                        <Typography variant="subtitle1" fontWeight="medium">
                            Processing Pipeline
                        </Typography>
                    </Stack>
                </AccordionSummary>

            </Box>

            <AccordionDetails sx={{bgcolor: "background.default"}}>
                <Paper
                    elevation={0}
                    sx={{
                        borderRadius: 2,
                        overflow: "hidden",
                    }}
                >
                    <Box
                        sx={{
                            p: 2,
                        }}
                    >
                        <Typography variant="body2" color="textSecondary">
                            Processing pipeline steps will be listed here.
                        </Typography>
                    </Box>
                </Paper>
            </AccordionDetails>
        </Accordion>
    );
};
