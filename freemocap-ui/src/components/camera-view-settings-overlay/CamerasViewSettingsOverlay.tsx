import React, { useState } from 'react';
import { Box, IconButton, Paper, TextField, Checkbox, FormControlLabel, Tooltip } from '@mui/material';
import SettingsIcon from '@mui/icons-material/Settings';
import CloseIcon from '@mui/icons-material/Close';
import GridViewIcon from '@mui/icons-material/GridView';
import { useServer } from '@/services/server/ServerContextProvider';

interface CameraSettings {
    columns: number | null;
}

interface CamerasViewSettingsOverlayProps {
    onSettingsChange: (settings: CameraSettings) => void;
}

export const CamerasViewSettingsOverlay: React.FC<CamerasViewSettingsOverlayProps> = ({
                                                                                          onSettingsChange
                                                                                      }) => {
    const { connectedCameraIds } = useServer();
    const [isOpen, setIsOpen] = useState<boolean>(false);
    const [isAuto, setIsAuto] = useState<boolean>(true);
    const [manualColumns, setManualColumns] = useState<number>(2);

    const getAutoColumns = (total: number): number => {
        if (total <= 1) return 1;
        if (total <= 4) return 2;
        if (total <= 9) return 3;
        return 4;
    };

    const autoColumns = getAutoColumns(connectedCameraIds.length);

    const handleAutoChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        const checked = event.target.checked;
        setIsAuto(checked);
        onSettingsChange({ columns: checked ? null : manualColumns });
    };

    const handleColumnsChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        const value = parseInt(event.target.value);
        if (!isNaN(value) && value > 0) {
            setManualColumns(value);
            if (isAuto) {
                // User is adjusting input while Auto is checked, so uncheck Auto
                setIsAuto(false);
            }
            onSettingsChange({ columns: value });
        }
    };

    return (
        <>
            {/* Settings Button */}
            <Box
                sx={{
                    position: 'absolute',
                    top: 16,
                    right: 16,
                    zIndex: 1000,
                }}
            >
                <Tooltip title={isOpen ? "Close settings" : "Grid settings"}>
                    <IconButton
                        onClick={() => setIsOpen(!isOpen)}
                        sx={{
                            backgroundColor: 'background.paper',
                            boxShadow: 2,
                            '&:hover': {
                                backgroundColor: 'action.hover',
                            },
                        }}
                    >
                        {isOpen ? <CloseIcon /> : <SettingsIcon />}
                    </IconButton>
                </Tooltip>
            </Box>

            {/* Settings Panel */}
            {isOpen && (
                <Paper
                    elevation={8}
                    sx={{
                        position: 'absolute',
                        top: 70,
                        right: 16,
                        zIndex: 999,
                        padding: 2,
                        minWidth: 250,
                    }}
                >
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                        <GridViewIcon fontSize="small" />
                        <Box sx={{ fontWeight: 600 }}>Grid Columns</Box>
                    </Box>

                    <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1 }}>
                        <FormControlLabel
                            control={
                                <Checkbox
                                    checked={isAuto}
                                    onChange={handleAutoChange}
                                    sx={{
                                        '&.Mui-checked': {
                                            color: 'text.primary',
                                        },
                                    }}
                                />
                            }
                            label="Auto"
                        />

                        <TextField
                            type="number"
                            label="Columns"
                            value={isAuto ? autoColumns : manualColumns}
                            onChange={handleColumnsChange}
                            fullWidth
                            inputProps={{
                                min: 1,
                                step: 1,
                            }}
                            helperText={isAuto ? `Auto-detected: ${autoColumns}` : "Enter any positive number"}
                        />
                    </Box>
                </Paper>
            )}
        </>
    );
};
