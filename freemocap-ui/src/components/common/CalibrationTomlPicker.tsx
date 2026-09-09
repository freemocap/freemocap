import React from "react";
import IconButton from "@/components/ui-components/IconButton";


interface CalibrationTomlPickerProps {
    tomlPath: string | null;
    onSelect: () => void;
    onClear: () => void;
    disabled?: boolean;
}


export const CalibrationTomlPicker: React.FC<CalibrationTomlPickerProps> = ({
    tomlPath,
    onSelect,
    onClear,
    disabled = false,
}) => {
    return (
        <div className="flex flex-row items-center gap-1 p-1 br-1 border-1 border-mid-black" style={{ minHeight: 36 }}>
            <span className={`icon icon-size-20 ${tomlPath ? 'upToDate-icon' : 'warning-icon'}`} />

            <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
                {tomlPath ? (
                    <>
                        <span className="tag text sm">Selected calibration</span>
                        <span
                            className="text sm"
                            title={tomlPath}
                            style={{ fontFamily: 'monospace', color: 'var(--color-success)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                        >
                            {tomlPath}
                        </span>
                    </>
                ) : (
                    <span className="text sm text-gray">No calibration selected</span>
                )}
            </div>

            {tomlPath && (
                <IconButton
                    icon="rotate-icon"
                    onClick={onClear}
                    disabled={disabled}
                    title="Clear calibration"
                />
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
