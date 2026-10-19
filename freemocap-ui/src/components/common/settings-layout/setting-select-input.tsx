import './settings-layout.css';

interface SettingSelectOption<Value extends string> {
    label: string;
    value: Value;
    disabledReason?: string;
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
    const unavailableReasons = options.flatMap(option => option.disabledReason ? [option.disabledReason] : []);
    return <span className="setting-select-input" title={unavailableReasons.join(' ') || undefined}>
        <select aria-label={label} value={value} disabled={disabled}
            onChange={event => onChange(event.target.value as Value)}>
            {options.map(option => <option key={option.value} value={option.value}
                disabled={!!option.disabledReason} title={option.disabledReason}>{option.label}</option>)}
        </select>
    </span>;
}
