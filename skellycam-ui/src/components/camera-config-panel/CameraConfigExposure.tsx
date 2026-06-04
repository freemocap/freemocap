import React from 'react';
import SegmentedControl from '@/components/ui-components/SegmentedControl';
import { ExposureMode } from "@/store/slices/cameras/cameras-types";
import { useTranslation } from 'react-i18next';

interface CameraConfigExposureProps {
    exposureMode: ExposureMode;
    exposure: number;
    onExposureModeChange: (mode: ExposureMode) => void;
    onExposureValueChange: (value: number) => void;
}

const EXPOSURE_CONSTRAINTS = { min: -13, max: -4, default: -7 };

export const CameraConfigExposure: React.FC<CameraConfigExposureProps> = ({
    exposureMode = 'MANUAL',
    exposure = EXPOSURE_CONSTRAINTS.default,
    onExposureModeChange,
    onExposureValueChange,
}) => {
    const { t } = useTranslation();
    const isDisabled = exposureMode === 'AUTO' || exposureMode === 'RECOMMEND';

    return (
        <div className="flex flex-col gap-1">
            <div className="flex items-center gap-1 flex-wrap">
                <p className="text sm text-gray text-nowrap">{t("exposure")}</p>
                <SegmentedControl
                    options={[
                        { label: t("manual"), value: "MANUAL" },
                        { label: t("auto"), value: "AUTO" },
                        { label: t("recommend"), value: "RECOMMEND" },
                    ]}
                    value={exposureMode}
                    onChange={(v) => onExposureModeChange(v as ExposureMode)}
                    size="sm"
                />
            </div>

            <div className={`flex flex-col gap-1 ${isDisabled ? 'disabled' : ''}`}>
                <input
                    type="range"
                    className="range-input"
                    min={EXPOSURE_CONSTRAINTS.min}
                    max={EXPOSURE_CONSTRAINTS.max}
                    step={1}
                    value={exposure}
                    disabled={isDisabled}
                    onChange={(e) => onExposureValueChange(parseInt(e.target.value))}
                />
                <div className="flex justify-content-space-between">
                    <p className="text sm text-darkgray">{EXPOSURE_CONSTRAINTS.min}</p>
                    <p className="text sm text-gray">{exposure}</p>
                    <p className="text sm text-darkgray">{EXPOSURE_CONSTRAINTS.max}</p>
                </div>
            </div>
        </div>
    );
};
