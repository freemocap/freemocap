import React from "react";
import {CameraConfigResolution} from "./CameraConfigResolution";
import {CameraConfigExposure} from "./CameraConfigExposure";
import {CameraConfigRotation} from "./CameraConfigRotation";
import {CameraConfig, ExposureMode, RotationValue} from "@/store/slices/cameras/cameras-types";
import {useAppDispatch, useAppSelector} from "@/store";
import {configCopiedToAll, selectCameras} from "@/store/slices/cameras";
import {useTranslation} from 'react-i18next';

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
    const {t} = useTranslation();
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
            className="flex flex-col gap-1 br-1"
            style={{
                paddingLeft: 12,
                paddingRight: 8,
                paddingTop: 8,
                paddingBottom: 4,
                marginLeft: 20,
                marginRight: 4,
                marginBottom: 4,
                border: '1px solid var(--color-border-secondary)',
                backgroundColor: 'var(--color-bg-paper)',
            }}
        >
            <div className="flex flex-row items-center gap-2" style={{flexWrap: 'wrap'}}>
                <CameraConfigResolution
                    resolution={config.resolution}
                    onChange={handleResolutionChange}
                />

                <CameraConfigRotation
                    rotation={config.rotation}
                    onChange={handleRotationChange}
                />

                <div style={{flex: 1}} />

                <button
                    className="button icon-button br-1"
                    onClick={handleCopyToAllCameras}
                    disabled={otherCamerasCount === 0}
                    aria-label={t("copySettingsToAll")}
                    title={
                        otherCamerasCount > 0
                            ? `Copy settings to ${otherCamerasCount} other camera${otherCamerasCount > 1 ? "s" : ""}`
                            : "No other cameras to copy to"
                    }
                    style={{
                        border: '1px solid var(--color-border-secondary)',
                    }}
                >
                    <span className="icon mediation-icon icon-size-20" />
                </button>
            </div>

            <div style={{paddingTop: 4, borderTop: '1px solid var(--color-border-secondary)'}}>
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
