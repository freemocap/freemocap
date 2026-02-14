import React from "react";
import {Box, FormControlLabel, Stack, Switch, Typography, useTheme} from "@mui/material";
import LanIcon from "@mui/icons-material/Lan";
import {CollapsibleSidebarSection} from "@/components/common/CollapsibleSidebarSection";
import {PipelineConnectionToggle} from "@/components/processing-pipeline-panel/PipelineConnectionToggle";
import {PipelineSummary} from "@/components/processing-pipeline-panel/PipelineSummary";
import {useAppSelector} from "@/store/hooks";
import {selectBackendPipeline} from "@/store/slices/settings";
import {useServer} from "@/hooks/useServer";
import {MediapipeConfigPanel} from "@/components/mocap-control-panel/MediapipeConfigPanel";

export const ProcessingPipelinePanel: React.FC = () => {
    const theme = useTheme();
    const {send, isConnected} = useServer();
    const backendPipeline = useAppSelector(selectBackendPipeline);

    const pipelineConfig = backendPipeline?.config;
    const isPipelineConnected = backendPipeline?.is_connected ?? false;

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
                    {/* Detection toggles — only visible when pipeline is connected */}
                    {isPipelineConnected && pipelineConfig ? (
                        <>
                            <Typography
                                variant="subtitle2"
                                sx={{color: theme.palette.text.secondary, fontWeight: 600}}
                            >
                                Detection Stages
                            </Typography>
                            <FormControlLabel
                                control={
                                    <Switch
                                        size="small"
                                        checked={pipelineConfig.calibration_detection_enabled}
                                        onChange={handleToggleCalibrationDetection}
                                        disabled={!isConnected}
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
                                        checked={pipelineConfig.mocap_detection_enabled}
                                        onChange={handleToggleMocapDetection}
                                        disabled={!isConnected}
                                    />
                                }
                                label={
                                    <Typography variant="body2">
                                        MediaPipe Detection (MoCap)
                                    </Typography>
                                }
                            />

                            {/* MediaPipe config — show when mocap detection is enabled */}
                            {pipelineConfig.mocap_detection_enabled && (
                                <Box sx={{mt: 1, pl: 1, borderLeft: `2px solid ${theme.palette.divider}`}}>
                                    <MediapipeConfigPanel />
                                </Box>
                            )}
                        </>
                    ) : (
                        <Typography variant="body2" color="text.secondary">
                            Connect a pipeline to configure detection stages.
                        </Typography>
                    )}
                </Stack>
            </Box>
        </CollapsibleSidebarSection>
    );
};
