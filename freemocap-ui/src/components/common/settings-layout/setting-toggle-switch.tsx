import './settings-layout.css';

interface SettingToggleSwitchProps {
    /** Names the switch for assistive technology; the row's label is the visible name. */
    label: string;
    isToggled: boolean;
    onToggle: (toggled: boolean) => void;
    disabled?: boolean;
}

/**
 * The bare switch, for the control column of a row whose label already names it.
 * A real button with role="switch", so it is reachable and operable by keyboard.
 */
export default function SettingToggleSwitch({label, isToggled, onToggle, disabled = false}: SettingToggleSwitchProps) {
    return <button type="button" role="switch" aria-checked={isToggled} aria-label={label}
        className="setting-toggle-switch" disabled={disabled} onClick={() => onToggle(!isToggled)}>
        <span className={`icon toggle-container ${isToggled ? 'on' : 'off'}`}>
            <span className="icon toggle-circle"/>
        </span>
    </button>;
}
