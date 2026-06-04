import React from "react";

interface PresetOption<T extends string> {
    value: T;
    label: string;
}

interface PresetPickerProps<T extends string> {
    label?: string;
    value: T;
    options: PresetOption<T>[];
    onChange: (value: T) => void;
    disabled?: boolean;
    minWidth?: number;
}

export function PresetPicker<T extends string>({
    label,
    value,
    options,
    onChange,
    disabled = false,
    minWidth = 120,
}: PresetPickerProps<T>): React.ReactElement {
    return (
        <div className="flex flex-col gap-1" style={{ minWidth }}>
            {label && <label className="text sm text-gray">{label}</label>}
            <div className="input-with-string">
                <select
                    className="input-field text md w-full"
                    value={value}
                    onChange={(e) => onChange(e.target.value as T)}
                    disabled={disabled}
                    style={{ width: '100%', cursor: disabled ? 'not-allowed' : 'pointer' }}
                >
                    {options.map((opt) => (
                        <option key={opt.value} value={opt.value}>
                            {opt.label}
                        </option>
                    ))}
                </select>
            </div>
        </div>
    );
}
