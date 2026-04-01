import React from "react";
import {Box, FormControlLabel, Stack, Switch, Typography, useTheme} from "@mui/material";
import LanIcon from "@mui/icons-material/Lan";
import {CollapsibleSidebarSection} from "@/components/common/CollapsibleSidebarSection";
import {PipelineConnectionToggle} from "@/components/processing-pipeline-panel/PipelineConnectionToggle";
import {PipelineSummary} from "@/components/processing-pipeline-panel/PipelineSummary";
import {useAppSelector} from "@/store/hooks";
import {selectBackendPipeline} from "@/store/slices/settings";
import {MediapipeConfigPanel} from "@/components/mocap-control-panel/MediapipeConfigPanel";
import {SkeletonFilterConfigPanel} from "@/components/mocap-control-panel/SkeletonFilterConfigPanel";
import {useServer} from "@/services";

export const ProcessingPipelinePanel: React.FC = () => {
    const theme = useTheme();
    const {send, isConnected} = useServer();
    const backendPipeline = useAppSelector(selectBackendPipeline);

    const pipelineConfig = backendPipeline?.config;
    const isPipelineConnected = backendPipeline?.is_connected ?? false;
    const canToggle = isConnected && isPipelineConnected;

    const handleToggleCalibrationDetection = (_: React.ChangeEvent, checked: boolean) => {
        send({
            message_type: "settings/patch",
            patch: {
                pipeline: {
                    config: {
                        calibration_detection_enabled: checked,
                    },
                },
            },
        });
    };

    const handleToggleMocapDetection = (_: React.ChangeEvent, checked: boolean) => {
        send({
            message_type: "settings/patch",
            patch: {
                pipeline: {
                    config: {
                        mocap_detection_enabled: checked,
                    },
                },
            },
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
                <Stack spacing={2}>
                    {/* Detection toggles — always visible, disabled when pipeline not connected */}
                    <Typography
                        variant="subtitle2"
                        sx={{color: theme.palette.text.secondary, fontWeight: 600}}
                    >
                        Detection Stages
                    </Typography>
                    {!isPipelineConnected && (
                        <Typography variant="caption" color="text.secondary" sx={{fontStyle: "italic"}}>
                            Connect a pipeline to enable detection toggles.
                        </Typography>
                    )}
                    <FormControlLabel
                        control={
                            <Switch
                                size="small"
                                checked={pipelineConfig?.calibration_detection_enabled ?? true}
                                onChange={handleToggleCalibrationDetection}
                                disabled={!canToggle}
                            />
                        }
                        label={
                            <Typography variant="body2">
                                Charuco Detection (Calibration)
                            </Typography>
                        }
                    />
                    <FormControlLabel
                        control={
                            <Switch
                                size="small"
                                checked={pipelineConfig?.mocap_detection_enabled ?? true}
                                onChange={handleToggleMocapDetection}
                                disabled={!canToggle}
                            />
                        }
                        label={
                            <Typography variant="body2">
                                MediaPipe Detection (MoCap)
                            </Typography>
                        }
                    />

                    {/* MediaPipe config — always visible */}
                    <Box sx={{mt: 1, pl: 1, borderLeft: `2px solid ${theme.palette.divider}`}}>
                        <MediapipeConfigPanel />
                    </Box>

                    {/* Skeleton filter config — always visible */}
                    <Box sx={{mt: 1, pl: 1, borderLeft: `2px solid ${theme.palette.divider}`}}>
                        <SkeletonFilterConfigPanel />
                    </Box>
                </Stack>
            </Box>
        </CollapsibleSidebarSection>
    );
};
