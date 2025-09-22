import {Box, Collapse, IconButton, Tooltip, useTheme} from "@mui/material";
import Grid from "@mui/material/Grid2";
import MediationIcon from '@mui/icons-material/Mediation';
import * as React from "react";
import {CameraConfigResolution} from "./CameraConfigResolution";
import {CameraConfigExposure} from "./CameraConfigExposure";
import {CameraConfigRotation} from "./CameraConfigRotation";
import {CameraConfig} from "@/store/slices/cameras-slices/camera-types";
import {copyConfigToAllCameras} from "@/store/slices/cameras-slices/camerasSlice";
import {useAppDispatch} from "@/store/AppStateStore";

interface CameraConfigPanelProps {
    config: CameraConfig;
    onConfigChange: (newConfig: CameraConfig) => void;
    isExpanded: boolean;
}

export const CameraConfigPanel: React.FC<CameraConfigPanelProps> = ({
                                                                        config,
                                                                        onConfigChange,
                                                                        isExpanded,
                                                                    }) => {
    const theme = useTheme();
    const dispatch = useAppDispatch();

    const handleChange = <K extends keyof CameraConfig>(
        key: K,
        value: CameraConfig[K]
    ) => {
        onConfigChange({
            ...config,
            [key]: value,
        });
    };
    const handleCopyToAllCameras = () => {
        dispatch(copyConfigToAllCameras(config.camera_id));
    };
    return (
        <Collapse in={isExpanded}>
            <Box
                sx={{
                    p: 1.5,
                    ml: 7,
                    mr: 2,
                    mb: 1,
                    borderRadius: 1,
                    border: `1px solid ${theme.palette.divider}`,
                }}
            >

                <Grid container spacing={2}>
                    {/* Top row with Resolution, Rotation, and Copy Settings */}
                    <Grid size={{xs: 12, sm: 5}}>
                        <CameraConfigResolution
                            resolution={config.resolution}
                            onChange={(width, height) =>
                                handleChange("resolution", {width, height})
                            }
                        />
                    </Grid>

                    <Grid size={{xs: 12, sm: 5}}>
                        <CameraConfigRotation
                            rotation={config.rotation}
                            onChange={(value) => handleChange("rotation", value)}
                        />
                    </Grid>

                    <Grid size={{xs: 12, sm: 2}} sx={{display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
                        <Tooltip title="Copy settings to all cameras">
                            <IconButton
                                size="small"
                                onClick={handleCopyToAllCameras}
                                aria-label="Copy settings to all cameras"
                            >
                                <MediationIcon/>
                            </IconButton>
                        </Tooltip>
                    </Grid>

                    {/* Bottom row with Exposure controls */}
                    <Grid size={12}>
                        <CameraConfigExposure
                            exposureMode={config.exposure_mode}
                            exposure={config.exposure}
                            onExposureModeChange={(mode) =>
                                handleChange("exposure_mode", mode)
                            }
                            onExposureValueChange={(value) => handleChange("exposure", value)}
                        />
                    </Grid>
                </Grid>
            </Box>
        </Collapse>
    );
};
