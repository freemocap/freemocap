import React, {useState} from 'react';
import {Box, Button, Checkbox, FormControlLabel, IconButton, Paper, TextField, Tooltip} from '@mui/material';
import SettingsIcon from '@mui/icons-material/Settings';
import CloseIcon from '@mui/icons-material/Close';
import GridViewIcon from '@mui/icons-material/GridView';
import ViewInArIcon from '@mui/icons-material/ViewInAr';
import RestartAltIcon from '@mui/icons-material/RestartAlt';

import {useServer} from "@/hooks/useServer";

interface CameraSettings {
    columns: number | null;
    show3dView: boolean;
}

interface CamerasViewSettingsOverlayProps {
    onSettingsChange: (settings: CameraSettings) => void;
    onResetViews: () => void;
}

export const CamerasViewSettingsOverlay: React.FC<CamerasViewSettingsOverlayProps> = ({
                                                                                          onSettingsChange,
                                                                                          onResetViews
                                                                                      }) => {
    const { connectedCameraIds } = useServer();
    const [isOpen, setIsOpen] = useState<boolean>(false);
    const [isAuto, setIsAuto] = useState<boolean>(true);
    const [manualColumns, setManualColumns] = useState<number>(2);
    const [show3dView, setShow3dView] = useState<boolean>(true);

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
        onSettingsChange({
            columns: checked ? null : manualColumns,
            show3dView
        });
    };

    const handleColumnsChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        const value = parseInt(event.target.value);
        if (!isNaN(value) && value > 0) {
            setManualColumns(value);
            if (isAuto) {
                // User is adjusting input while Auto is checked, so uncheck Auto
                setIsAuto(false);
            }
            onSettingsChange({
                columns: value,
                show3dView
            });
        }
    };

    const handle3dViewChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        const checked = event.target.checked;
        setShow3dView(checked);
        onSettingsChange({
            columns: isAuto ? null : manualColumns,
            show3dView: checked
        });
    };

    const handleResetViews = () => {
        onResetViews();
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

                    <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1, mb: 3 }}>
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

                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                        <ViewInArIcon fontSize="small" />
                        <Box sx={{ fontWeight: 600 }}>3D View</Box>
                    </Box>

                    <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1, mb: 3 }}>
                        <FormControlLabel
                            control={
                                <Checkbox
                                    checked={show3dView}
                                    onChange={handle3dViewChange}
                                    sx={{
                                        '&.Mui-checked': {
                                            color: 'text.primary',
                                        },
                                    }}
                                />
                            }
                            label="Show 3D View"
                        />
                    </Box>

                    <Button
                        variant="outlined"
                        startIcon={<RestartAltIcon />}
                        onClick={handleResetViews}
                        fullWidth
                        sx={{
                            mt: 1,
                            textTransform: 'none',
                            color: 'text.primary',
                            borderColor: 'text.primary',
                            '&:hover': {
                                borderColor: 'text.primary',
                                backgroundColor: 'action.hover',
                            },
                        }}
                    >
                        Reset Panel Sizes
                    </Button>
                </Paper>
            )}
        </>
    );
};
