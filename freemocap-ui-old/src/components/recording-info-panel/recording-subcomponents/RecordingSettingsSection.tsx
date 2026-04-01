import React from 'react';
import {Box, Checkbox, FormControlLabel, Grid, TextField, Typography, useTheme} from '@mui/material';

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

    return (
        <Box sx={{
            mt: 2,
            p: 2,
            bgcolor: theme.palette.mode === 'dark'
                ? 'rgba(255, 255, 255, 0.05)'
                : 'rgba(0, 0, 0, 0.04)',
            borderRadius: 1
        }}>
            <Typography variant="subtitle1" sx={{mb: 2}}>Recording Settings</Typography>

            <Grid container spacing={2} alignItems="center">
                {/* Timestamp & Base name row */}
                <Grid item xs={12} sm={4}>
                    <FormControlLabel
                        control={
                            <Checkbox
                                sx={{
                                    color: theme.palette.text.primary,
                                    '&.Mui-checked': {
                                        color: theme.palette.text.primary,
                                    },
                                }}
                                checked={useTimestamp}
                                onChange={(e) => onUseTimestampChange(e.target.checked)}
                            />
                        }
                        label="Use Timestamp"
                    />
                </Grid>
                <Grid item xs={12} sm={8}>
                    <TextField
                        label="Base Recording Name"
                        value={baseName}
                        onChange={(e) => onBaseNameChange(e.target.value)}
                        disabled={useTimestamp}
                        size="small"
                        fullWidth
                    />
                </Grid>

                {/* Subfolder row */}
                <Grid item xs={12} sm={4}>
                    <FormControlLabel
                        control={
                            <Checkbox
                                sx={{
                                    color: theme.palette.text.primary,
                                    '&.Mui-checked': {
                                        color: theme.palette.text.primary,
                                    },
                                }}

                                checked={createSubfolder}
                                onChange={(e) => onCreateSubfolderChange(e.target.checked)}
                            />
                        }
                        label="Use Subfolder"
                    />
                </Grid>
                <Grid item xs={12} sm={8}>
                    <TextField
                        label="Custom Subfolder Name"
                        value={customSubfolderName}
                        onChange={(e) => onCustomSubfolderNameChange(e.target.value)}
                        disabled={!createSubfolder}
                        size="small"
                        fullWidth
                        placeholder="Leave empty to use timestamp"
                    />
                </Grid>

                {/* Auto increment row */}
                <Grid item xs={12} sm={4}>
                    <FormControlLabel
                        control={
                            <Checkbox
                                checked={useIncrement}
                                onChange={(e) => onUseIncrementChange(e.target.checked)}
                                sx={{
                                    color: theme.palette.text.primary,
                                    '&.Mui-checked': {
                                        color: theme.palette.text.primary,
                                    },
                                }}
                            />
                        }
                        label="Auto Increment"
                    />
                </Grid>
                <Grid item xs={12} sm={4}>
                    <TextField
                        label="Increment Number"
                        type="number"
                        value={currentIncrement}
                        onChange={(e) => onIncrementChange(parseInt(e.target.value) || 1)}
                        disabled={!useIncrement}
                        inputProps={{min: 1, step: 1}}
                        size="small"
                        fullWidth
                    />
                </Grid>

            </Grid>
        </Box>
    );
};
