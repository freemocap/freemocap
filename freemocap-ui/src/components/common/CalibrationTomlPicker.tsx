import React from "react";

export type CalibrationTomlSource = "auto" | "calibration-panel" | "manual" | "last-successful";

interface CalibrationTomlPickerProps {
    tomlPath: string | null;
    source: CalibrationTomlSource;
    onSelect: () => void;
    onUseAutoDetected: () => void;
    disabled?: boolean;
}

const SOURCE_LABELS: Record<CalibrationTomlSource, string> = {
    auto: "Auto-detected",
    "calibration-panel": "From calibration panel",
    manual: "Manually selected",
    "last-successful": "Last successful calibration",
};

export const CalibrationTomlPicker: React.FC<CalibrationTomlPickerProps> = ({
    tomlPath,
    source,
    onSelect,
    onUseAutoDetected,
    disabled = false,
}) => {
    return (
        <div className="flex flex-row items-center gap-1 p-1 br-1 border-1 border-mid-black" style={{ minHeight: 36 }}>
            <span className={`icon icon-size-20 ${tomlPath ? 'upToDate-icon' : 'warning-icon'}`} />

            <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
                {tomlPath ? (
                    <>
                        <span className="tag text sm">{SOURCE_LABELS[source]}</span>
                        <span
                            className="text sm"
                            title={tomlPath}
                            style={{ fontFamily: 'monospace', color: 'var(--color-success)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                        >
                            {tomlPath}
                        </span>
                    </>
                ) : (
                    <span className="text sm text-gray">No calibration TOML found</span>
                )}
            </div>

            {source !== "auto" && tomlPath && (
                <button
                    className="button icon-button br-1"
                    onClick={onUseAutoDetected}
                    disabled={disabled}
                    title="Use auto-detected calibration"
                >
                    <span className="icon rotate-icon icon-size-20" />
                </button>
            )}

            <button
                className="button sm secondary br-1 flex flex-row items-center gap-1"
                onClick={onSelect}
                disabled={disabled}
            >
                <span className="icon load-icon icon-size-20" />
                <p className="text sm text-white">Browse</p>
            </button>
        </div>
    );
};
