import React from "react";
import {useTranslation} from "react-i18next";
import IconButton from "@/components/ui-components/IconButton";

export type CalibrationTomlSource = "auto" | "calibration-panel" | "manual" | "last-successful";

interface CalibrationTomlPickerProps {
    tomlPath: string | null;
    source: CalibrationTomlSource;
    onSelect: () => void;
    onUseAutoDetected: () => void;
    disabled?: boolean;
}

export const CalibrationTomlPicker: React.FC<CalibrationTomlPickerProps> = ({
    tomlPath,
    source,
    onSelect,
    onUseAutoDetected,
    disabled = false,
}) => {
    const {t} = useTranslation();
    const sourceLabels: Record<CalibrationTomlSource, string> = {
        auto: t("calibrationToml.autoDetected"),
        "calibration-panel": t("calibrationToml.fromPanel"),
        manual: t("calibrationToml.manuallySelected"),
        "last-successful": t("calibrationToml.lastSuccessful"),
    };

    return (
        <div className="flex flex-row items-center gap-1 p-1 br-1 border-1 border-mid-black" style={{ minHeight: 36 }}>
            <span className={`icon icon-size-20 ${tomlPath ? 'upToDate-icon' : 'warning-icon'}`} />

            <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
                {tomlPath ? (
                    <>
                        <span className="tag text sm">{sourceLabels[source]}</span>
                        <span
                            className="text sm"
                            title={tomlPath}
                            style={{ fontFamily: 'monospace', color: 'var(--color-success)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                        >
                            {tomlPath}
                        </span>
                    </>
                ) : (
                    <span className="text sm text-gray">{t("calibrationToml.notFound")}</span>
                )}
            </div>

            {source !== "auto" && tomlPath && (
                <IconButton
                    icon="rotate-icon"
                    onClick={onUseAutoDetected}
                    disabled={disabled}
                    title={t("calibrationToml.useAutoDetected")}
                />
            )}

            <button
                className="button sm secondary br-1 flex flex-row items-center gap-1"
                onClick={onSelect}
                disabled={disabled}
            >
                <span className="icon load-icon icon-size-20" />
                <p className="text sm text-white">{t("browse")}</p>
            </button>
        </div>
    );
};
