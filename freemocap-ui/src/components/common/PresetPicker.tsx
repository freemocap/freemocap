import React from "react";
import {FormControl, InputLabel, MenuItem, Select, SxProps, Theme} from "@mui/material";

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
    size?: "small" | "medium";
    minWidth?: number;
    sx?: SxProps<Theme>;
}

export function PresetPicker<T extends string>({
    label,
    value,
    options,
    onChange,
    disabled = false,
    size = "small",
    minWidth = 120,
    sx,
}: PresetPickerProps<T>): React.ReactElement {
    const labelId = label ? `preset-picker-${label.toLowerCase().replace(/\s+/g, "-")}-label` : undefined;

    return (
        <FormControl size={size} sx={{minWidth, ...sx}}>
            {label && <InputLabel id={labelId}>{label}</InputLabel>}
            <Select
                labelId={labelId}
                value={value}
                label={label || undefined}
                onChange={(e) => onChange(e.target.value as T)}
                disabled={disabled}
            >
                {options.map((opt) => (
                    <MenuItem key={opt.value} value={opt.value}>
                        {opt.label}
                    </MenuItem>
                ))}
            </Select>
        </FormControl>
    );
}
