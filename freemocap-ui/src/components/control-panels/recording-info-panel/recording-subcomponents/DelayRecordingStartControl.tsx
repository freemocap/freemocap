import React from 'react';
import {useTranslation} from 'react-i18next';

interface DelayStartControlProps {
    useDelay: boolean;
    delaySeconds: number;
    onDelayToggle: (checked: boolean) => void;
    onDelayChange: (seconds: number) => void;
}

export const DelayRecordingStartControl: React.FC<DelayStartControlProps> = ({
    useDelay,
    delaySeconds,
    onDelayToggle,
    onDelayChange
}) => {
    const { t } = useTranslation();
    return (
        <div className="flex flex-row items-center gap-2">
            <label className="flex flex-row items-center gap-1">
                <input
                    type="checkbox"
                    checked={useDelay}
                    onChange={(e) => onDelayToggle(e.target.checked)}
                    style={{accentColor: 'var(--color-info)'}}
                />
                <span className="text sm text-gray">{t("delayStart")}</span>
            </label>
            {useDelay && (
                <div className="input-with-string" style={{width: 100}}>
                    <input
                        className="input-field text md"
                        type="number"
                        value={delaySeconds}
                        onChange={(e) => onDelayChange(Math.max(1, parseInt(e.target.value) || 1))}
                        min={1}
                        step={1}
                        placeholder={t("seconds")}
                    />
                </div>
            )}
        </div>
    );
};
