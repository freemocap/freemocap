import React, {useEffect, useState} from "react";
import {CameraConfig} from "@/store/slices/cameras/cameras-types";
import {useTranslation} from 'react-i18next';

interface CameraConfigResolutionProps {
    resolution: CameraConfig['resolution'];
    onChange: (width: number, height: number) => void;
}

const PRESET_RESOLUTIONS = [
    { width: 640, height: 480, label: "640 x 480" },
    { width: 1280, height: 720, label: "1280 x 720" },
    { width: 1920, height: 1080, label: "1920 x 1080" },
];

const RESOLUTION_CONSTRAINTS = {
    min: 1,
    max: 7680,
    default: { width: 1280, height: 720 }
};

export const CameraConfigResolution: React.FC<CameraConfigResolutionProps> = ({
    resolution,
    onChange
}) => {
    const {t} = useTranslation();
    const isPreset = PRESET_RESOLUTIONS.some(
        preset => preset.width === resolution.width && preset.height === resolution.height
    );

    const [selectedValue, setSelectedValue] = useState<string>(
        isPreset ? `${resolution.width}x${resolution.height}` : 'custom'
    );

    const [customWidth, setCustomWidth] = useState<string>(resolution.width.toString());
    const [customHeight, setCustomHeight] = useState<string>(resolution.height.toString());
    const [widthError, setWidthError] = useState<string>('');
    const [heightError, setHeightError] = useState<string>('');

    useEffect(() => {
        if (selectedValue === 'custom') {
            setCustomWidth(resolution.width.toString());
            setCustomHeight(resolution.height.toString());
        }
    }, [resolution.width, resolution.height, selectedValue]);

    const validateDimension = (value: string, _dimension: 'width' | 'height'): string => {
        const numValue = parseInt(value, 10);

        if (value === '' || isNaN(numValue)) {
            return 'Enter a valid number';
        }

        if (numValue < RESOLUTION_CONSTRAINTS.min) {
            return `Min: ${RESOLUTION_CONSTRAINTS.min}px`;
        }

        if (numValue > RESOLUTION_CONSTRAINTS.max) {
            return `Max: ${RESOLUTION_CONSTRAINTS.max}px`;
        }

        return '';
    };

    const handleSelectChange = (event: React.ChangeEvent<HTMLSelectElement>): void => {
        const value = event.target.value;
        setSelectedValue(value);

        if (value !== 'custom') {
            const [width, height] = value.split('x').map(Number);
            onChange(width, height);
        }
    };

    const handleCustomWidthChange = (event: React.ChangeEvent<HTMLInputElement>): void => {
        const value = event.target.value;
        setCustomWidth(value);

        const error = validateDimension(value, 'width');
        setWidthError(error);

        if (!error) {
            const width = parseInt(value, 10);
            const height = parseInt(customHeight, 10);
            if (!isNaN(height)) {
                onChange(width, height);
            }
        }
    };

    const handleCustomHeightChange = (event: React.ChangeEvent<HTMLInputElement>): void => {
        const value = event.target.value;
        setCustomHeight(value);

        const error = validateDimension(value, 'height');
        setHeightError(error);

        if (!error) {
            const width = parseInt(customWidth, 10);
            const height = parseInt(value, 10);
            if (!isNaN(width)) {
                onChange(width, height);
            }
        }
    };

    const handleCustomBlur = (dimension: 'width' | 'height'): void => {
        const value = dimension === 'width' ? customWidth : customHeight;
        const error = validateDimension(value, dimension);

        if (error) {
            if (dimension === 'width') {
                setCustomWidth(resolution.width.toString());
                setWidthError('');
            } else {
                setCustomHeight(resolution.height.toString());
                setHeightError('');
            }
        }
    };

    const handleKeyDown = (
        event: React.KeyboardEvent<HTMLInputElement>,
        dimension: 'width' | 'height'
    ): void => {
        if (event.key === 'Enter') {
            handleCustomBlur(dimension);
            (event.target as HTMLElement).blur();
        }
    };

    return (
        <div>
            <div className="input-with-string" style={{marginBottom: selectedValue === 'custom' ? 4 : 0}}>
                <select
                    className="input-field text md"
                    value={selectedValue}
                    onChange={handleSelectChange}
                >
                    {PRESET_RESOLUTIONS.map(preset => (
                        <option
                            key={`${preset.width}x${preset.height}`}
                            value={`${preset.width}x${preset.height}`}
                        >
                            {preset.label}
                        </option>
                    ))}
                    <option value="custom">{t("custom")}</option>
                </select>
            </div>

            {selectedValue === 'custom' && (
                <div className="flex flex-row gap-1 mt-1">
                    <div className="flex flex-col flex-1">
                        <div className="input-with-string">
                            <input
                                className="input-field text md"
                                type="number"
                                placeholder={t("width")}
                                value={customWidth}
                                onChange={handleCustomWidthChange}
                                onBlur={() => handleCustomBlur('width')}
                                onKeyDown={(e) => handleKeyDown(e, 'width')}
                                min={RESOLUTION_CONSTRAINTS.min}
                                max={RESOLUTION_CONSTRAINTS.max}
                            />
                        </div>
                        {widthError && <span className="text sm text-error">{widthError}</span>}
                    </div>
                    <div className="flex flex-col flex-1">
                        <div className="input-with-string">
                            <input
                                className="input-field text md"
                                type="number"
                                placeholder={t("height")}
                                value={customHeight}
                                onChange={handleCustomHeightChange}
                                onBlur={() => handleCustomBlur('height')}
                                onKeyDown={(e) => handleKeyDown(e, 'height')}
                                min={RESOLUTION_CONSTRAINTS.min}
                                max={RESOLUTION_CONSTRAINTS.max}
                            />
                        </div>
                        {heightError && <span className="text sm text-error">{heightError}</span>}
                    </div>
                </div>
            )}
        </div>
    );
};
