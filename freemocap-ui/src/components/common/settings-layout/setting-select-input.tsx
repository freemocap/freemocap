import './settings-layout.css';

interface SettingSelectOption<Value extends string> {
    label: string;
    value: Value;
}

interface SettingSelectInputProps<Value extends string> {
    /** Names the control for assistive technology; the row's label is the visible name. */
    label: string;
    value: Value;
    options: readonly SettingSelectOption<Value>[];
    onChange: (value: Value) => void;
    disabled?: boolean;
}

/**
 * A choice whose set of options is open-ended.
 *
 * Use this wherever more options are expected to arrive; a segmented control
 * says "these are all the choices there will ever be", which is a promise the
 * detector list and the model list cannot keep.
 */
export default function SettingSelectInput<Value extends string>(
    {label, value, options, onChange, disabled = false}: SettingSelectInputProps<Value>,
) {
    return <span className="setting-select-input">
        <select aria-label={label} value={value} disabled={disabled}
            onChange={event => onChange(event.target.value as Value)}>
            {options.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
        </select>
    </span>;
}
