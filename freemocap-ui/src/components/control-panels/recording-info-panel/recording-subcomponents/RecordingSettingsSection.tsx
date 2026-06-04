import React from 'react';
import {useTranslation} from 'react-i18next';

interface RecordingSettingsProps {
    useTimestamp: boolean;
    baseName: string;
    useIncrement: boolean;
    currentIncrement: number;
    createSubfolder: boolean;
    customSubfolderName: string;
    onUseTimestampChange: (value: boolean) => void;
    onBaseNameChange: (value: string) => void;
    onUseIncrementChange: (value: boolean) => void;
    onIncrementChange: (value: number) => void;
    onCreateSubfolderChange: (value: boolean) => void;
    onCustomSubfolderNameChange: (value: string) => void;
}

/** A compact row: checkbox on the left, optional input filling remaining space. */
const SettingRow: React.FC<{
    checked: boolean;
    label: string;
    onCheck: (value: boolean) => void;
    children?: React.ReactNode;
}> = ({checked, label, onCheck, children}) => (
    <div className="flex flex-row items-center gap-1" style={{minHeight: 32}}>
        <label className="flex flex-row items-center gap-1" style={{flexShrink: 0, whiteSpace: 'nowrap'}}>
            <input
                type="checkbox"
                checked={checked}
                onChange={(e) => onCheck(e.target.checked)}
                style={{accentColor: 'var(--color-info)'}}
            />
            <span className="text sm text-gray" style={{fontSize: 12}}>{label}</span>
        </label>
        {children && (
            <div style={{flex: 1, minWidth: 0}}>
                {children}
            </div>
        )}
    </div>
);

/** Compact input that aligns vertically with checkboxes (no floating label). */
const CompactInput: React.FC<{
    value: string | number;
    onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
    placeholder: string;
    disabled: boolean;
    type?: string;
    min?: number;
    step?: number;
    style?: React.CSSProperties;
}> = ({value, onChange, placeholder, disabled, type, min, step, style}) => (
    <input
        className="input-field text md"
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        disabled={disabled}
        type={type}
        min={min}
        step={step}
        style={{height: 28, fontSize: 12, ...style}}
    />
);

export const RecordingSettingsSection: React.FC<RecordingSettingsProps> = ({
    useTimestamp,
    baseName,
    useIncrement,
    currentIncrement,
    createSubfolder,
    customSubfolderName,
    onUseTimestampChange,
    onBaseNameChange,
    onUseIncrementChange,
    onIncrementChange,
    onCreateSubfolderChange,
    onCustomSubfolderNameChange,
}) => {
    const { t } = useTranslation();

    return (
        <div
            className="flex flex-col gap-1 br-1 bg-middark"
            style={{marginTop: 8, padding: 12}}
        >
            <p className="text sm text-gray" style={{marginBottom: 4, fontSize: 13, fontWeight: 600}}>
                {t('recordingSettings')}
            </p>

            {/* Timestamp toggle + base name input */}
            <SettingRow checked={useTimestamp} label={t("timestamp")} onCheck={onUseTimestampChange}>
                <CompactInput
                    value={baseName}
                    onChange={(e) => onBaseNameChange(e.target.value)}
                    placeholder={t("baseName")}
                    disabled={useTimestamp}
                />
            </SettingRow>

            {/* Subfolder toggle + custom name input */}
            <SettingRow checked={createSubfolder} label={t("subfolder")} onCheck={onCreateSubfolderChange}>
                <CompactInput
                    value={customSubfolderName}
                    onChange={(e) => onCustomSubfolderNameChange(e.target.value)}
                    placeholder={t("subfolderPlaceholder")}
                    disabled={!createSubfolder}
                />
            </SettingRow>

            {/* Auto-increment toggle + number input */}
            <SettingRow checked={useIncrement} label={t("increment")} onCheck={onUseIncrementChange}>
                <CompactInput
                    value={currentIncrement}
                    onChange={(e) => onIncrementChange(parseInt(e.target.value) || 1)}
                    placeholder="#"
                    disabled={!useIncrement}
                    type="number"
                    min={1}
                    step={1}
                    style={{maxWidth: 64}}
                />
            </SettingRow>
        </div>
    );
};
