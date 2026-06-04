import React, { useState } from 'react';
import SegmentedControl from '@/components/ui-components/SegmentedControl';
import { useTranslation } from 'react-i18next';

interface CameraConfigFramerateProps {
    framerate: number | null;
    onChange: (value: number | null) => void;
}

const FRAMERATE_CONSTRAINTS = { min: 1, max: 1000, default: 30 };

export const CameraConfigFramerate: React.FC<CameraConfigFramerateProps> = ({
    framerate = FRAMERATE_CONSTRAINTS.default,
    onChange,
}) => {
    const { t } = useTranslation();
    const isAuto = framerate === null;
    const [mode, setMode] = useState<'AUTO' | 'MANUAL'>(isAuto ? 'AUTO' : 'MANUAL');
    const [localValue, setLocalValue] = useState<string>(
        isAuto ? FRAMERATE_CONSTRAINTS.default.toFixed(2) : (framerate ?? FRAMERATE_CONSTRAINTS.default).toFixed(2)
    );
    const [error, setError] = useState<string>('');

    const validateAndUpdate = (value: string): void => {
        const numValue = parseFloat(value);
        if (value === '' || isNaN(numValue)) { setError('Enter a valid number'); return; }
        if (numValue < FRAMERATE_CONSTRAINTS.min) { setError(`Min: ${FRAMERATE_CONSTRAINTS.min} FPS`); return; }
        if (numValue > FRAMERATE_CONSTRAINTS.max) { setError(`Max: ${FRAMERATE_CONSTRAINTS.max} FPS`); return; }
        setError('');
        onChange(Math.round(numValue * 100) / 100);
    };

    const handleModeChange = (newMode: string) => {
        const m = newMode as 'AUTO' | 'MANUAL';
        setMode(m);
        if (m === 'AUTO') { setError(''); onChange(null); }
        else { validateAndUpdate(localValue); }
    };

    const handleBlur = () => {
        validateAndUpdate(localValue);
        if (error) {
            const v = framerate === null ? FRAMERATE_CONSTRAINTS.default : framerate;
            setLocalValue(v.toFixed(2));
            setError('');
        } else {
            setLocalValue(parseFloat(localValue).toFixed(2));
        }
    };

    const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
        if (e.key === 'Enter') { handleBlur(); e.currentTarget.blur(); }
    };

    return (
        <div className="flex flex-col gap-1">
            <p className="text sm text-gray">{t("framerate")}</p>
            <SegmentedControl
                options={[{ label: t("auto"), value: "AUTO" }, { label: t("manual"), value: "MANUAL" }]}
                value={mode}
                onChange={handleModeChange}
                size="sm"
            />
            {mode === 'MANUAL' && (
                <div className="flex flex-col gap-1">
                    <div className="input-with-unit">
                        <input
                            className="input-field numeric-input"
                            type="number"
                            value={localValue}
                            min={FRAMERATE_CONSTRAINTS.min}
                            max={FRAMERATE_CONSTRAINTS.max}
                            step={0.01}
                            onChange={(e) => setLocalValue(e.target.value)}
                            onBlur={handleBlur}
                            onKeyDown={handleKeyDown}
                        />
                        <span className="unit-label text md">fps</span>
                    </div>
                    {error && <p className="text sm text-warning">{error}</p>}
                </div>
            )}
        </div>
    );
};
