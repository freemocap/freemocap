import React from 'react';
import { useTranslation } from 'react-i18next';
import ToggleComponent from '@/components/ui-components/ToggleComponent';
import ValueSelector from '@/components/ui-components/ValueSelector';

interface DelayStartControlProps {
    useDelay: boolean;
    delaySeconds: number;
    onDelayToggle: (checked: boolean) => void;
    onDelayChange: (seconds: number) => void;
}

export const DelayRecordingStartControl: React.FC<DelayStartControlProps> = ({
    useDelay, delaySeconds, onDelayToggle, onDelayChange,
}) => {
    const { t } = useTranslation();
    return (
        <div className="flex items-center gap-1 flex-wrap align-end">
            <ToggleComponent
                text={t("delayStart")}
                isToggled={useDelay}
                onToggle={onDelayToggle}
            />
            {useDelay && (
                <ValueSelector
                    value={delaySeconds}
                    min={1}
                    max={60}
                    unit="s"
                    onChange={onDelayChange}
                />
            )}
        </div>
    );
};
