import React from 'react';
import {Box, Checkbox, FormControlLabel, TextField, useTheme} from '@mui/material';

interface DelayStartControlProps {
    useDelay: boolean;
    delaySeconds: number;
    onDelayToggle: (checked: boolean) => void;
    onDelayChange: (seconds: number) => void;
}

export const DelayRecordingStartControl: React.FC<DelayStartControlProps> = ({
                                                                                 useDelay,
                                                                                 delaySeconds,
                                                                                 onDelayToggle,
                                                                                 onDelayChange
                                                                             }) => {
    const theme = useTheme();
    return (
        <Box display="flex" alignItems="center" gap={2}>
            <FormControlLabel
                control={
                    <Checkbox
                        checked={useDelay}
                        onChange={(e) => onDelayToggle(e.target.checked)}
                        color="primary"
                    />
                }
                label="Delay Start"
            />
            {useDelay && (
                <TextField
                    label="Seconds"
                    type="number"
                    value={delaySeconds}
                    onChange={(e) => onDelayChange(Math.max(1, parseInt(e.target.value) || 1))}
                    inputProps={{min: 1, step: 1}}
                    size="small"
                    sx={{width: 100}}
                />
            )}
        </Box>
    );
};
