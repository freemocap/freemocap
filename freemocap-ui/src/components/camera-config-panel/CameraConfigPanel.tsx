import React from "react";
import {
    Box,
    Collapse,
    IconButton,
    Tooltip,
    useTheme,
} from "@mui/material";
import MediationIcon from "@mui/icons-material/Mediation";
import { CameraConfigResolution } from "./CameraConfigResolution";
import { CameraConfigExposure } from "./CameraConfigExposure";
import { CameraConfigRotation } from "./CameraConfigRotation";
import { CameraConfig, ExposureMode, RotationValue } from "@/store/slices/cameras/cameras-types";
import { useAppDispatch, useAppSelector } from "@/store";
import { selectCameras, configCopiedToAll } from "@/store/slices/cameras";
import { useTranslation } from 'react-i18next';

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
    const { t } = useTranslation();
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

    const handleRotationChange = (value: RotationValue): void => {
        handleChange("rotation", value);
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
                    px: 1.5,
                    py: 1,
                    ml: 5,
                    mr: 1,
                    mb: 0.5,
                    borderRadius: 1,
                    border: `1px solid ${theme.palette.divider}`,
                    backgroundColor: theme.palette.background.paper,
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 1,
                }}
            >
                {/* Top row: Resolution, Rotation, then Copy to All pushed right */}
                <Box sx={{display: 'flex', alignItems: 'center', gap: 1.5, flexWrap: 'wrap'}}>
                    <CameraConfigResolution
                        resolution={config.resolution}
                        onChange={handleResolutionChange}
                    />

                    <CameraConfigRotation
                        rotation={config.rotation}
                        onChange={handleRotationChange}
                    />

                    {/* Spacer pushes Copy to All to the right */}
                    <Box sx={{flex: 1}}/>

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
                                aria-label={t("copySettingsToAll")}
                                sx={{
                                    color: theme.palette.primary.contrastText,
                                    border: `1px solid ${theme.palette.divider}`,
                                    '&:hover': {
                                        backgroundColor: theme.palette.primary.dark,
                                        color: theme.palette.primary.contrastText,
                                        borderColor: theme.palette.primary.dark,
                                    },
                                    '&:disabled': {
                                        color: theme.palette.action.disabled,
                                    },
                                }}
                            >
                                <MediationIcon fontSize="small"/>
                            </IconButton>
                        </span>
                    </Tooltip>
                </Box>

                {/* Exposure controls */}
                <Box sx={{pt: 0.5, borderTop: `1px solid ${theme.palette.divider}`}}>
                    <CameraConfigExposure
                        exposureMode={config.exposure_mode}
                        exposure={config.exposure}
                        onExposureModeChange={handleExposureModeChange}
                        onExposureValueChange={handleExposureValueChange}
                    />
                </Box>
            </Box>
        </Collapse>
    );
};
