import React, { useState } from 'react';
import { Box, TextField, ToggleButton, ToggleButtonGroup, Tooltip, Typography, useTheme } from '@mui/material';
import { useTranslation } from 'react-i18next';

interface CameraConfigFramerateProps {
    framerate: number | null;
    onChange: (value: number | null) => void;
}

const FRAMERATE_CONSTRAINTS = {
    min: 1,
    max: 1000,
    default: 30
};

export const CameraConfigFramerate: React.FC<CameraConfigFramerateProps> = ({
    framerate = FRAMERATE_CONSTRAINTS.default,
    onChange
}) => {
    const theme = useTheme();
    const { t } = useTranslation();
    const isAuto = framerate === null;
    const [mode, setMode] = useState<'AUTO' | 'MANUAL'>(isAuto ? 'AUTO' : 'MANUAL');
    const [localValue, setLocalValue] = useState<string>(
        isAuto ? FRAMERATE_CONSTRAINTS.default.toFixed(2) : framerate.toFixed(2)
    );
    const [error, setError] = useState<string>('');

    const validateAndUpdate = (value: string): void => {
        const numValue = parseFloat(value);

        if (value === '' || isNaN(numValue)) {
            setError('Enter a valid number');
            return;
        }

        if (numValue < FRAMERATE_CONSTRAINTS.min) {
            setError(`Min: ${FRAMERATE_CONSTRAINTS.min} FPS`);
            return;
        }

        if (numValue > FRAMERATE_CONSTRAINTS.max) {
            setError(`Max: ${FRAMERATE_CONSTRAINTS.max} FPS`);
            return;
        }

        setError('');
        const roundedValue = Math.round(numValue * 100) / 100;
        onChange(roundedValue);
    };

    const handleModeChange = (
        event: React.MouseEvent<HTMLElement>,
        newMode: 'AUTO' | 'MANUAL' | null
    ): void => {
        if (newMode === null) return;

        setMode(newMode);

        if (newMode === 'AUTO') {
            setError('');
            onChange(null);
        } else {
            // Switch to manual mode with the last valid value
            validateAndUpdate(localValue);
        }
    };

    const handleChange = (event: React.ChangeEvent<HTMLInputElement>): void => {
        const value = event.target.value;
        setLocalValue(value);
    };

    const handleBlur = (): void => {
        validateAndUpdate(localValue);

        // Reset to valid value if invalid, otherwise format to 2 decimals
        if (error) {
            const validValue = framerate === null ? FRAMERATE_CONSTRAINTS.default : framerate;
            setLocalValue(validValue.toFixed(2));
            setError('');
        } else {
            setLocalValue(parseFloat(localValue).toFixed(2));
        }
    };

    const handleKeyDown = (event: React.KeyboardEvent<HTMLInputElement>): void => {
        if (event.key === 'Enter') {
            validateAndUpdate(localValue);
            if (error) {
                const validValue = framerate === null ? FRAMERATE_CONSTRAINTS.default : framerate;
                setLocalValue(validValue.toFixed(2));
                setError('');
            } else {
                setLocalValue(parseFloat(localValue).toFixed(2));
            }
            event.currentTarget.blur();
        }
    };

    return (
        <Box>
            <Typography variant="body2" color="text.secondary" gutterBottom>
                {t("framerate")}
            </Typography>
            <Tooltip title={t("framerateControl")}>
                <ToggleButtonGroup
                    color={theme.palette.primary.main as any}
                    value={mode}
                    exclusive
                    onChange={handleModeChange}
                    size="small"
                    fullWidth
                    sx={{
                        mb: mode === 'MANUAL' ? 1 : 0,
                        '& .MuiToggleButton-root.Mui-selected': {
                            backgroundColor: theme.palette.primary.dark,
                            border: `1px solid ${theme.palette.text.secondary}`,
                            color: theme.palette.primary.contrastText,
                            '&:hover': {
                                backgroundColor: theme.palette.primary.light,
                            },
                        }
                    }}
                >
                    <ToggleButton value="AUTO">{t("auto")}</ToggleButton>
                    <ToggleButton value="MANUAL">{t("manual")}</ToggleButton>
                </ToggleButtonGroup>
            </Tooltip>

            {mode === 'MANUAL' && (
                <Tooltip title={t("setTargetFps")}>
                    <TextField
                        label={t("fps")}
                        value={localValue}
                        onChange={handleChange}
                        onBlur={handleBlur}
                        onKeyDown={handleKeyDown}
                        type="number"
                        size="small"
                        error={!!error}
                        helperText={error}
                        fullWidth
                        inputProps={{
                            min: FRAMERATE_CONSTRAINTS.min,
                            max: FRAMERATE_CONSTRAINTS.max,
                            step: 0.01,
                        }}
                        sx={{
                            '& .MuiInputLabel-root': {
                                color: theme.palette.text.primary,
                            },
                            '& .MuiOutlinedInput-root': {
                                color: theme.palette.text.primary,
                                '& fieldset': {
                                    borderColor: theme.palette.divider,
                                },
                                '&:hover fieldset': {
                                    borderColor: theme.palette.primary.main,
                                },
                                '&.Mui-focused fieldset': {
                                    borderColor: theme.palette.primary.main,
                                },
                            },
                            '& .MuiFormHelperText-root': {
                                color: error ? theme.palette.error.main : theme.palette.text.secondary,
                            },
                        }}
                    />
                </Tooltip>
            )}
        </Box>
    );
};