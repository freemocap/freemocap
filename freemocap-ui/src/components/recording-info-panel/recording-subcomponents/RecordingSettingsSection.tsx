import React from 'react';
import { useTranslation } from 'react-i18next';
import {Box, Checkbox, FormControlLabel, TextField, Typography, useTheme} from '@mui/material';

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
    <Box sx={{display: 'flex', alignItems: 'center', gap: 0.5, minHeight: 32}}>
        <FormControlLabel
            control={
                <Checkbox
                    checked={checked}
                    onChange={(e) => onCheck(e.target.checked)}
                    size="small"
                    sx={{p: 0.25}}
                />
            }
            label={label}
            sx={{
                mr: 0,
                flexShrink: 0,
                whiteSpace: 'nowrap',
                '& .MuiFormControlLabel-label': {fontSize: 12},
            }}
        />
        {children && (
            <Box sx={{flex: 1, minWidth: 0}}>
                {children}
            </Box>
        )}
    </Box>
);

/** Compact text field that aligns vertically with checkboxes (no floating label). */
const CompactTextField: React.FC<{
    value: string | number;
    onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
    placeholder: string;
    disabled: boolean;
    type?: string;
    inputProps?: React.InputHTMLAttributes<HTMLInputElement>;
    fullWidth?: boolean;
    sx?: object;
}> = ({value, onChange, placeholder, disabled, type, inputProps, fullWidth = true, sx}) => (
    <TextField
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        disabled={disabled}
        type={type}
        inputProps={inputProps}
        size="small"
        fullWidth={fullWidth}
        sx={{
            '& .MuiOutlinedInput-root': {
                height: 28,
                fontSize: 12,
            },
            '& .MuiOutlinedInput-input': {
                py: 0.5,
                px: 1,
            },
            ...sx,
        }}
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
    const theme = useTheme();
    const { t } = useTranslation();

    return (
        <Box sx={{
            mt: 1,
            p: 1.5,
            bgcolor: theme.palette.mode === 'dark'
                ? 'rgba(255, 255, 255, 0.05)'
                : 'rgba(0, 0, 0, 0.04)',
            borderRadius: 1,
            display: 'flex',
            flexDirection: 'column',
            gap: 0.5,
        }}>
            <Typography variant="subtitle2" sx={{mb: 0.5, fontSize: 13, fontWeight: 600}}>
                {t('recordingSettings')}
            </Typography>

            {/* Timestamp toggle + base name input */}
            <SettingRow checked={useTimestamp} label={t("timestamp")} onCheck={onUseTimestampChange}>
                <CompactTextField
                    value={baseName}
                    onChange={(e) => onBaseNameChange(e.target.value)}
                    placeholder={t("baseName")}
                    disabled={useTimestamp}
                />
            </SettingRow>

            {/* Subfolder toggle + custom name input */}
            <SettingRow checked={createSubfolder} label={t("subfolder")} onCheck={onCreateSubfolderChange}>
                <CompactTextField
                    value={customSubfolderName}
                    onChange={(e) => onCustomSubfolderNameChange(e.target.value)}
                    placeholder={t("subfolderPlaceholder")}
                    disabled={!createSubfolder}
                />
            </SettingRow>

            {/* Auto-increment toggle + number input */}
            <SettingRow checked={useIncrement} label={t("increment")} onCheck={onUseIncrementChange}>
                <CompactTextField
                    value={currentIncrement}
                    onChange={(e) => onIncrementChange(parseInt(e.target.value) || 1)}
                    placeholder="#"
                    disabled={!useIncrement}
                    type="number"
                    inputProps={{min: 1, step: 1}}
                    fullWidth={false}
                    sx={{maxWidth: 64}}
                />
            </SettingRow>
        </Box>
    );
};
