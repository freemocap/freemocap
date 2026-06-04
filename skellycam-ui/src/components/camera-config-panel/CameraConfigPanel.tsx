import React from "react";
import clsx from "clsx";
import ButtonSm from "@/components/ui-components/ButtonSm";
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
    compact?: boolean;
}

export const CameraConfigPanel: React.FC<CameraConfigPanelProps> = ({
    config, onConfigChange, isExpanded, compact = false,
}) => {
    const dispatch = useAppDispatch();
    const { t } = useTranslation();
    const allCameras = useAppSelector(selectCameras);
    const otherCamerasCount = allCameras.length - 1;

    const handleChange = <K extends keyof CameraConfig>(key: K, value: CameraConfig[K]) => {
        onConfigChange({ ...config, [key]: value });
    };

    return (
        <div className={clsx("config-panel", !isExpanded && "hidden", compact && "config-panel-compact")}>
            <div className={clsx("flex gap-1", compact ? "flex-col" : "items-center flex-wrap")}>
                <CameraConfigResolution
                    resolution={config.resolution}
                    onChange={(w, h) => handleChange("resolution", { width: w, height: h })}
                />
                <CameraConfigRotation
                    rotation={config.rotation}
                    onChange={(v: RotationValue) => handleChange("rotation", v)}
                />
                <ButtonSm
                    text={otherCamerasCount > 0
                        ? `Copy to ${otherCamerasCount} other${otherCamerasCount > 1 ? 's' : ''}`
                        : t("copySettingsToAll")}
                    iconClass="stream-icon"
                    buttonType={clsx(otherCamerasCount === 0 && "disabled", compact && "full-width justify-center")}
                    onClick={() => { if (otherCamerasCount > 0) dispatch(configCopiedToAll(config.camera_id)); }}
                />
            </div>

            <div className="config-panel-divider">
                <CameraConfigExposure
                    exposureMode={config.exposure_mode}
                    exposure={config.exposure}
                    onExposureModeChange={(mode: ExposureMode) => handleChange("exposure_mode", mode)}
                    onExposureValueChange={(v) => handleChange("exposure", v)}
                />
            </div>
        </div>
    );
};
