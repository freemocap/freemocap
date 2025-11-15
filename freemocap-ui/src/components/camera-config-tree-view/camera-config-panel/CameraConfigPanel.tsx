import React from "react";
import {Box, Collapse, IconButton, Tooltip, useTheme,} from "@mui/material";
import Grid from "@mui/material/Grid2";
import MediationIcon from "@mui/icons-material/Mediation";
import {CameraConfigResolution} from "./CameraConfigResolution";
import {CameraConfigExposure} from "./CameraConfigExposure";
import {CameraConfigRotation} from "./CameraConfigRotation";
import {CameraConfig, ExposureMode} from "@/store/slices/cameras/cameras-types";
import {useAppDispatch, useAppSelector} from "@/store";
import {configCopiedToAll, selectCameras} from "@/store/slices/cameras";

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

    // Get total camera count for UI feedback
    const allCameras = useAppSelector(selectCameras);
    const otherCamerasCount = allCameras.length - 1;

    const handleChange = <K extends keyof CameraConfig>(
        key: K,
        value: CameraConfig[K]
    ): void => {
        onConfigChange({
            ...config,
            [key]: value,
        });
    };

    const handleCopyToAllCameras = (): void => {
        dispatch(configCopiedToAll(config.camera_id));
    };

    const handleResolutionChange = (width: number, height: number): void => {
        handleChange("resolution", { width, height });
    };

    const handleRotationChange = (value: string): void => {
        handleChange("rotation", value as CameraConfig['rotation']);
    };

    const handleExposureModeChange = (mode: ExposureMode): void => {
        handleChange("exposure_mode", mode);
    };

    const handleExposureValueChange = (value: number): void => {
        handleChange("exposure", value);
    };

    return (
        <Collapse in={isExpanded} timeout="auto" unmountOnExit>
            <Box
                sx={{
                    p: 1.5,
                    ml: 7,
                    mr: 2,
                    mb: 1,
                    borderRadius: 1,
                    border: `1px solid ${theme.palette.divider}`,
                    backgroundColor: theme.palette.background.paper,
                }}
            >
                <Grid container spacing={2}>
                    {/* Top row with Resolution and Rotation */}
                    <Grid size={{ xs: 12, md: 5 }}>
                        <CameraConfigResolution
                            resolution={config.resolution}
                            onChange={handleResolutionChange}
                        />
                    </Grid>

                    <Grid size={{ xs: 12, md: 5 }}>
                        <CameraConfigRotation
                            rotation={config.rotation}
                            onChange={handleRotationChange}
                        />
                    </Grid>

                    <Grid
                        size={{ xs: 12, md: 2 }}
                        sx={{
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                        }}
                    >
                        <Tooltip
                            title={
                                otherCamerasCount > 0
                                    ? `Copy settings to ${otherCamerasCount} other camera${
                                        otherCamerasCount > 1 ? "s" : ""
                                    }`
                                    : "No other cameras to copy to"
                            }
                        >
                            <span>
                                <IconButton
                                    size="small"
                                    onClick={handleCopyToAllCameras}
                                    disabled={otherCamerasCount === 0}
                                    aria-label="Copy settings to all cameras"
                                    sx={{
                                        color: theme.palette.primary.main,
                                        "&:hover": {
                                            backgroundColor: theme.palette.primary.light,
                                            color: theme.palette.primary.contrastText,
                                        },
                                        "&:disabled": {
                                            color: theme.palette.action.disabled,
                                        },
                                    }}
                                >
                                    <MediationIcon />
                                </IconButton>
                            </span>
                        </Tooltip>
                    </Grid>

                    {/* Bottom row with Exposure controls */}
                    <Grid size={12}>
                        <CameraConfigExposure
                            exposureMode={config.exposure_mode}
                            exposure={config.exposure}
                            onExposureModeChange={handleExposureModeChange}
                            onExposureValueChange={handleExposureValueChange}
                        />
                    </Grid>
                </Grid>
            </Box>
        </Collapse>
    );
};
