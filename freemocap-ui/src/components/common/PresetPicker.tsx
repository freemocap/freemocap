import React from "react";
import NameDropdownSelector from "@/components/ui-components/NameDropdownSelector";

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
}

export function PresetPicker<T extends string>({
    label,
    value,
    options,
    onChange,
    disabled = false,
}: PresetPickerProps<T>): React.ReactElement {
    const labels = options.map(o => o.label);
    const selectedLabel = options.find(o => o.value === value)?.label ?? labels[0];

    const handleChange = (label: string) => {
        const opt = options.find(o => o.label === label);
        if (opt) onChange(opt.value);
    };

    return (
        <div className={`flex flex-col gap-1${disabled ? ' disabled' : ''}`} style={{minWidth: 95}}>
            {label && <label className="text sm text-gray">{label}</label>}
            <NameDropdownSelector
                key={value}
                options={labels}
                initialValue={selectedLabel}
                onChange={handleChange}
            />
        </div>
    );
}
