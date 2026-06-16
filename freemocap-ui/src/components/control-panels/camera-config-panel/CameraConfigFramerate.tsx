import React, {useState} from 'react';
import {useTranslation} from 'react-i18next';

interface CameraConfigFramerateProps {
    framerate: number | null;
    onChange: (value: number | null) => void;
}

const FRAMERATE_CONSTRAINTS = {
    min: 1,
    max: 1000,
    default: 30
};

export const CameraConfigFramerate: React.FC<CameraConfigFramerateProps> = ({
    framerate = FRAMERATE_CONSTRAINTS.default,
    onChange
}) => {
    const {t} = useTranslation();
    const isAuto = framerate === null;
    const [mode, setMode] = useState<'AUTO' | 'MANUAL'>(isAuto ? 'AUTO' : 'MANUAL');
    const [localValue, setLocalValue] = useState<string>(
        isAuto ? FRAMERATE_CONSTRAINTS.default.toFixed(2) : framerate.toFixed(2)
    );
    const [error, setError] = useState<string>('');

    const validateAndUpdate = (value: string): void => {
        const numValue = parseFloat(value);

        if (value === '' || isNaN(numValue)) {
            setError('Enter a valid number');
            return;
        }

        if (numValue < FRAMERATE_CONSTRAINTS.min) {
            setError(`Min: ${FRAMERATE_CONSTRAINTS.min} FPS`);
            return;
        }

        if (numValue > FRAMERATE_CONSTRAINTS.max) {
            setError(`Max: ${FRAMERATE_CONSTRAINTS.max} FPS`);
            return;
        }

        setError('');
        const roundedValue = Math.round(numValue * 100) / 100;
        onChange(roundedValue);
    };

    const handleModeChange = (newMode: 'AUTO' | 'MANUAL'): void => {
        setMode(newMode);

        if (newMode === 'AUTO') {
            setError('');
            onChange(null);
        } else {
            validateAndUpdate(localValue);
        }
    };

    const handleChange = (event: React.ChangeEvent<HTMLInputElement>): void => {
        const value = event.target.value;
        setLocalValue(value);
    };

    const handleBlur = (): void => {
        validateAndUpdate(localValue);

        if (error) {
            const validValue = framerate === null ? FRAMERATE_CONSTRAINTS.default : framerate;
            setLocalValue(validValue.toFixed(2));
            setError('');
        } else {
            setLocalValue(parseFloat(localValue).toFixed(2));
        }
    };

    const handleKeyDown = (event: React.KeyboardEvent<HTMLInputElement>): void => {
        if (event.key === 'Enter') {
            validateAndUpdate(localValue);
            if (error) {
                const validValue = framerate === null ? FRAMERATE_CONSTRAINTS.default : framerate;
                setLocalValue(validValue.toFixed(2));
                setError('');
            } else {
                setLocalValue(parseFloat(localValue).toFixed(2));
            }
            event.currentTarget.blur();
        }
    };

    return (
        <div>
            <p className="text sm text-gray mb-1">{t("framerate")}</p>
            <div className="flex flex-row gap-1" style={{marginBottom: mode === 'MANUAL' ? 4 : 0}} title={t("framerateControl")}>
                {(['AUTO', 'MANUAL'] as const).map((m) => (
                    <button
                        key={m}
                        className={`button sm flex-1${mode === m ? ' primary' : ' secondary'}`}
                        onClick={() => handleModeChange(m)}
                        style={{padding: '2px 8px', fontSize: 11}}
                    >
                        {m === 'AUTO' ? t("auto") : t("manual")}
                    </button>
                ))}
            </div>

            {mode === 'MANUAL' && (
                <div title={t("setTargetFps")}>
                    <div className="input-with-string">
                        <input
                            className="input-field text md"
                            type="number"
                            placeholder={t("fps")}
                            value={localValue}
                            onChange={handleChange}
                            onBlur={handleBlur}
                            onKeyDown={handleKeyDown}
                            min={FRAMERATE_CONSTRAINTS.min}
                            max={FRAMERATE_CONSTRAINTS.max}
                            step={0.01}
                        />
                    </div>
                    {error && <span className="text sm text-error">{error}</span>}
                </div>
            )}
        </div>
    );
};
