import React, { useState, useEffect } from "react";
import NameDropdownSelector from '@/components/ui-components/NameDropdownSelector';
import { CameraConfig } from "@/store/slices/cameras/cameras-types";
import { useTranslation } from 'react-i18next';

interface CameraConfigResolutionProps {
    resolution: CameraConfig['resolution'];
    onChange: (width: number, height: number) => void;
}

const PRESET_RESOLUTIONS = [
    { width: 640, height: 480, label: "640 × 480" },
    { width: 1280, height: 720, label: "1280 × 720" },
    { width: 1920, height: 1080, label: "1920 × 1080" },
];

const RESOLUTION_CONSTRAINTS = { min: 1, max: 7680 };

export const CameraConfigResolution: React.FC<CameraConfigResolutionProps> = ({
    resolution, onChange,
}) => {
    const { t } = useTranslation();
    const isPreset = PRESET_RESOLUTIONS.some(p => p.width === resolution.width && p.height === resolution.height);
    const [selectedLabel, setSelectedLabel] = useState<string>(
        isPreset ? `${resolution.width} × ${resolution.height}` : t("custom")
    );
    const [customWidth, setCustomWidth] = useState<string>(resolution.width.toString());
    const [customHeight, setCustomHeight] = useState<string>(resolution.height.toString());

    useEffect(() => {
        if (selectedLabel === t("custom")) {
            setCustomWidth(resolution.width.toString());
            setCustomHeight(resolution.height.toString());
        }
    }, [resolution.width, resolution.height, selectedLabel, t]);

    const handleSelectChange = (label: string) => {
        setSelectedLabel(label);
        const preset = PRESET_RESOLUTIONS.find(p => p.label === label);
        if (preset) onChange(preset.width, preset.height);
    };

    const applyCustom = () => {
        const w = parseInt(customWidth, 10);
        const h = parseInt(customHeight, 10);
        if (!isNaN(w) && !isNaN(h) && w >= RESOLUTION_CONSTRAINTS.min && h >= RESOLUTION_CONSTRAINTS.min) {
            onChange(w, h);
        }
    };

    const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
        if (e.key === 'Enter') { applyCustom(); e.currentTarget.blur(); }
    };

    const options = [...PRESET_RESOLUTIONS.map(p => p.label), t("custom")];

    return (
        <div className="flex flex-col gap-1">
            <NameDropdownSelector
                options={options}
                initialValue={selectedLabel}
                onChange={handleSelectChange}
            />
            {selectedLabel === t("custom") && (
                <div className="flex gap-1">
                    <div className="input-with-unit">
                        <input
                            className="input-field numeric-input"
                            type="number"
                            value={customWidth}
                            min={RESOLUTION_CONSTRAINTS.min}
                            max={RESOLUTION_CONSTRAINTS.max}
                            onChange={(e) => setCustomWidth(e.target.value)}
                            onBlur={applyCustom}
                            onKeyDown={handleKeyDown}
                            placeholder={t("width")}
                        />
                        <span className="unit-label text md">W</span>
                    </div>
                    <div className="input-with-unit">
                        <input
                            className="input-field numeric-input"
                            type="number"
                            value={customHeight}
                            min={RESOLUTION_CONSTRAINTS.min}
                            max={RESOLUTION_CONSTRAINTS.max}
                            onChange={(e) => setCustomHeight(e.target.value)}
                            onBlur={applyCustom}
                            onKeyDown={handleKeyDown}
                            placeholder={t("height")}
                        />
                        <span className="unit-label text md">H</span>
                    </div>
                </div>
            )}
        </div>
    );
};
