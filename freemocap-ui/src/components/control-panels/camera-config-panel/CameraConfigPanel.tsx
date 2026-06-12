import React from "react";
import {CameraConfigResolution} from "./CameraConfigResolution";
import {CameraConfigExposure} from "./CameraConfigExposure";
import {CameraConfigRotation} from "./CameraConfigRotation";
import {CameraConfig, ExposureMode, RotationValue} from "@/store/slices/cameras/cameras-types";
import {useAppDispatch, useAppSelector} from "@/store";
import {configCopiedToAll, selectCameras} from "@/store/slices/cameras";
import IconButton from "@/components/ui-components/IconButton";

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
    const dispatch = useAppDispatch();
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

    if (!isExpanded) return null;

    return (
        <div
            className="flex flex-col gap-1 br-1 pl-3 pr-2 pt-2 pb-1 mr-1 mb-1"
            style={{
                marginLeft: 20,
                border: '1px solid var(--color-border-secondary)',
                backgroundColor: 'var(--color-bg-paper)',
            }}
        >
            <div className="flex flex-row items-center gap-2 flex-wrap">
                <CameraConfigResolution
                    resolution={config.resolution}
                    onChange={handleResolutionChange}
                />

                <CameraConfigRotation
                    rotation={config.rotation}
                    onChange={handleRotationChange}
                />

                <div className="flex-1" />

                <IconButton
                    icon="mediation-icon"
                    onClick={handleCopyToAllCameras}
                    disabled={otherCamerasCount === 0}
                    title={
                        otherCamerasCount > 0
                            ? `Copy settings to ${otherCamerasCount} other camera${otherCamerasCount > 1 ? "s" : ""}`
                            : "No other cameras to copy to"
                    }
                    style={{
                        border: '1px solid var(--color-border-secondary)',
                    }}
                />
            </div>

            <div className="pt-1" style={{borderTop: '1px solid var(--color-border-secondary)'}}>
                <CameraConfigExposure
                    exposureMode={config.exposure_mode}
                    exposure={config.exposure}
                    onExposureModeChange={handleExposureModeChange}
                    onExposureValueChange={handleExposureValueChange}
                />
            </div>
        </div>
    );
};
