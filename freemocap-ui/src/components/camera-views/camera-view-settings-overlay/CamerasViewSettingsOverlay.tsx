import React, {useState} from 'react';
import {Box, Button, Checkbox, FormControlLabel, IconButton, Paper, TextField, ToggleButton, ToggleButtonGroup, Tooltip} from '@mui/material';
import SettingsIcon from '@mui/icons-material/Settings';
import CloseIcon from '@mui/icons-material/Close';
import GridViewIcon from '@mui/icons-material/GridView';
import ViewInArIcon from '@mui/icons-material/ViewInAr';
import RestartAltIcon from '@mui/icons-material/RestartAlt';
import ViewColumnIcon from '@mui/icons-material/ViewColumn';
import TableRowsIcon from '@mui/icons-material/TableRows';
import {useServer} from "@/hooks/useServer";
import {CameraSettings, LayoutDirection} from "@/pages/CamerasPage";

interface CamerasViewSettingsOverlayProps {
    onSettingsChange: (settings: CameraSettings) => void;
    onResetViews: () => void;
}

export const CamerasViewSettingsOverlay: React.FC<CamerasViewSettingsOverlayProps> = ({
                                                                                          onSettingsChange,
                                                                                          onResetViews
                                                                                      }) => {
    const {connectedCameraIds} = useServer();
    const [isOpen, setIsOpen] = useState<boolean>(false);
    const [isAuto, setIsAuto] = useState<boolean>(true);
    const [manualColumns, setManualColumns] = useState<number>(2);
    const [show3dView, setShow3dView] = useState<boolean>(true);
    const [layoutDirection, setLayoutDirection] = useState<LayoutDirection>('horizontal');

    const getAutoColumns = (total: number): number => {
        if (total <= 1) return 1;
        if (total <= 4) return 2;
        if (total <= 9) return 3;
        return 4;
    };

    const autoColumns = getAutoColumns(connectedCameraIds.length);

    const buildSettings = (overrides: Partial<{
        columns: number | null;
        show3dView: boolean;
        layoutDirection: LayoutDirection;
    }> = {}): CameraSettings => ({
        columns: overrides.columns !== undefined ? overrides.columns : (isAuto ? null : manualColumns),
        show3dView: overrides.show3dView !== undefined ? overrides.show3dView : show3dView,
        layoutDirection: overrides.layoutDirection !== undefined ? overrides.layoutDirection : layoutDirection,
    });

    const handleAutoChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        const checked = event.target.checked;
        setIsAuto(checked);
        onSettingsChange(buildSettings({columns: checked ? null : manualColumns}));
    };

    const handleColumnsChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        const value = parseInt(event.target.value);
        if (!isNaN(value) && value > 0) {
            setManualColumns(value);
            if (isAuto) {
                setIsAuto(false);
            }
            onSettingsChange(buildSettings({columns: value}));
        }
    };

    const handle3dViewChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        const checked = event.target.checked;
        setShow3dView(checked);
        onSettingsChange(buildSettings({show3dView: checked}));
    };

    const handleLayoutDirectionChange = (_event: React.MouseEvent<HTMLElement>, newDirection: LayoutDirection | null) => {
        if (newDirection === null) return; // Prevent deselecting both
        setLayoutDirection(newDirection);
        onSettingsChange(buildSettings({layoutDirection: newDirection}));
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
                        {isOpen ? <CloseIcon/> : <SettingsIcon/>}
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
                    <Box sx={{display: 'flex', alignItems: 'center', gap: 1, mb: 2}}>
                        <GridViewIcon fontSize="small"/>
                        <Box sx={{fontWeight: 600}}>Grid Columns</Box>
                    </Box>

                    <Box sx={{display: 'flex', alignItems: 'flex-start', gap: 1, mb: 3}}>
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

                    <Box sx={{display: 'flex', alignItems: 'center', gap: 1, mb: 2}}>
                        <ViewInArIcon fontSize="small"/>
                        <Box sx={{fontWeight: 600}}>3D View</Box>
                    </Box>

                    <Box sx={{display: 'flex', alignItems: 'flex-start', gap: 1, mb: 2}}>
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

                    {/* Layout direction toggle — only meaningful when 3D view is visible */}
                    <Box sx={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 1,
                        mb: 1,
                        opacity: show3dView ? 1 : 0.4,
                    }}>
                        <Box sx={{fontWeight: 600, fontSize: 13}}>Layout</Box>
                    </Box>
                    <ToggleButtonGroup
                        value={layoutDirection}
                        exclusive
                        onChange={handleLayoutDirectionChange}
                        disabled={!show3dView}
                        size="small"
                        sx={{mb: 3, width: '100%'}}
                    >
                        <ToggleButton value="vertical" sx={{flex: 1, textTransform: 'none', fontSize: 12}}>
                            <TableRowsIcon sx={{mr: 0.5, fontSize: 16}}/>
                            Top / Bottom
                        </ToggleButton>
                        <ToggleButton value="horizontal" sx={{flex: 1, textTransform: 'none', fontSize: 12}}>
                            <ViewColumnIcon sx={{mr: 0.5, fontSize: 16}}/>
                            Side by Side
                        </ToggleButton>
                    </ToggleButtonGroup>

                    <Button
                        variant="outlined"
                        startIcon={<RestartAltIcon/>}
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