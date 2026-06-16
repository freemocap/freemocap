import React from 'react';
import {ExposureMode} from "@/store/slices/cameras/cameras-types";
import {useTranslation} from 'react-i18next';

interface CameraConfigExposureProps {
    exposureMode: ExposureMode;
    exposure: number;
    onExposureModeChange: (mode: ExposureMode) => void;
    onExposureValueChange: (value: number) => void;
}

const EXPOSURE_CONSTRAINTS = {
    min: -13,
    max: -4,
    default: -7
};

const EXPOSURE_MODES: ExposureMode[] = ['MANUAL', 'AUTO', 'RECOMMEND'];

export const CameraConfigExposure: React.FC<CameraConfigExposureProps> = ({
    exposureMode = 'MANUAL',
    exposure = EXPOSURE_CONSTRAINTS.default,
    onExposureModeChange,
    onExposureValueChange
}) => {
    const {t} = useTranslation();

    const handleSliderChange = (event: React.ChangeEvent<HTMLInputElement>): void => {
        onExposureValueChange(Number(event.target.value));
    };

    const isDisabled = exposureMode === 'AUTO' || exposureMode === 'RECOMMEND';

    const exposureTooltip = `${(1000 / Math.pow(2, -1 * exposure)).toFixed(3)}ms (1/2^${exposure} sec)`;

    return (
        <div>
            <div className="flex flex-row items-center gap-2 mb-1">
                <span className="text sm text-gray text-nowrap" style={{fontSize: 12}}>
                    {t("exposure")}
                </span>
                <div className="flex flex-row gap-1" title={t("exposureControl")}>
                    {EXPOSURE_MODES.map((mode) => (
                        <button
                            key={mode}
                            className={`button sm${exposureMode === mode ? ' primary' : ' secondary'}`}
                            onClick={() => onExposureModeChange(mode)}
                            style={{padding: '2px 8px', fontSize: 11}}
                        >
                            {mode === 'MANUAL' ? t("manual") : mode === 'AUTO' ? t("auto") : t("recommend")}
                        </button>
                    ))}
                </div>
            </div>
            <div className="pl-1 pr-1" title={isDisabled ? undefined : t("adjustExposure")}>
                <input
                    type="range"
                    value={exposure}
                    disabled={isDisabled}
                    min={EXPOSURE_CONSTRAINTS.min}
                    max={EXPOSURE_CONSTRAINTS.max}
                    step={1}
                    onChange={handleSliderChange}
                    title={exposureTooltip}
                    className="w-full"
                    style={{accentColor: 'var(--color-info)'}}
                />
                <div className="flex flex-row justify-content-space-between">
                    <span className="text sm text-gray" style={{fontSize: 11}}>{EXPOSURE_CONSTRAINTS.min}</span>
                    <span className="text sm text-gray" style={{fontSize: 11}}>{exposure}</span>
                    <span className="text sm text-gray" style={{fontSize: 11}}>{EXPOSURE_CONSTRAINTS.max}</span>
                </div>
            </div>
        </div>
    );
};
