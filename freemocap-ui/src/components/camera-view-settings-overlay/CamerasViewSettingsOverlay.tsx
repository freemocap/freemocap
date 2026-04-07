import React, { useState } from 'react';
import {
    Box,
    IconButton,
    Paper,
    TextField,
    Checkbox,
    FormControlLabel,
    Tooltip,
    Divider,
    ToggleButton,
    ToggleButtonGroup,
    Switch,
} from '@mui/material';
import SettingsIcon from '@mui/icons-material/Settings';
import CloseIcon from '@mui/icons-material/Close';
import GridViewIcon from '@mui/icons-material/GridView';
import ViewSidebarIcon from '@mui/icons-material/ViewSidebar';
import SplitscreenIcon from '@mui/icons-material/Splitscreen';
import ViewAgendaIcon from '@mui/icons-material/ViewAgenda';
import { useServer } from '@/services/server/ServerContextProvider';
import { useTranslation } from 'react-i18next';
import type { CameraSettings, LayoutDirection } from '@/pages/CamerasPage';

interface CamerasViewSettingsOverlayProps {
    settings: CameraSettings;
    onSettingsChange: (partial: Partial<CameraSettings>) => void;
    onResetLayout: () => void;
}

export const CamerasViewSettingsOverlay: React.FC<CamerasViewSettingsOverlayProps> = ({
    settings,
    onSettingsChange,
    onResetLayout,
}) => {
    const { connectedCameraIds } = useServer();
    const { t } = useTranslation();
    const [isOpen, setIsOpen] = useState<boolean>(false);
    const [isAuto, setIsAuto] = useState<boolean>(settings.columns === null);
    const [manualColumns, setManualColumns] = useState<number>(settings.columns ?? 2);

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
            if (isAuto) setIsAuto(false);
            onSettingsChange({ columns: value });
        }
    };

    const handle3dViewToggle = (event: React.ChangeEvent<HTMLInputElement>) => {
        onSettingsChange({ show3dView: event.target.checked });
    };

    const handleLayoutDirectionChange = (
        _event: React.MouseEvent<HTMLElement>,
        newDirection: LayoutDirection | null,
    ) => {
        if (newDirection !== null) {
            onSettingsChange({ layoutDirection: newDirection });
        }
    };

    return (
        <>
            {/* Settings toggle button */}
            <Box sx={{ position: 'absolute', top: 16, right: 16, zIndex: 1000 }}>
                <Tooltip title={isOpen ? t('closeSettings') : t('gridSettings')}>
                    <IconButton
                        onClick={() => setIsOpen(!isOpen)}
                        sx={{
                            backgroundColor: 'background.paper',
                            boxShadow: 2,
                            '&:hover': { backgroundColor: 'action.hover' },
                        }}
                    >
                        {isOpen ? <CloseIcon /> : <SettingsIcon />}
                    </IconButton>
                </Tooltip>
            </Box>

            {/* Settings panel */}
            {isOpen && (
                <Paper
                    elevation={8}
                    sx={{
                        position: 'absolute',
                        top: 70,
                        right: 16,
                        zIndex: 999,
                        padding: 2,
                        minWidth: 260,
                        display: 'flex',
                        flexDirection: 'column',
                        gap: 2,
                    }}
                >
                    {/* ── Grid columns ──────────────────────────── */}
                    <Box>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.5 }}>
                            <GridViewIcon fontSize="small" />
                            <Box sx={{ fontWeight: 600, fontSize: '0.875rem' }}>{t('gridColumns')}</Box>
                        </Box>

                        <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1 }}>
                            <FormControlLabel
                                control={
                                    <Checkbox
                                        checked={isAuto}
                                        onChange={handleAutoChange}
                                        sx={{ '&.Mui-checked': { color: 'text.primary' } }}
                                    />
                                }
                                label={t('auto')}
                            />
                            <TextField
                                type="number"
                                label={t('columns')}
                                value={isAuto ? autoColumns : manualColumns}
                                onChange={handleColumnsChange}
                                fullWidth
                                inputProps={{ min: 1, step: 1 }}
                                helperText={
                                    isAuto
                                        ? `Auto-detected: ${autoColumns}`
                                        : 'Enter any positive number'
                                }
                            />
                        </Box>
                    </Box>

                    <Divider />

                    {/* ── 3D viewport toggle ────────────────────── */}
                    <Box>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                            <ViewSidebarIcon fontSize="small" />
                            <Box sx={{ fontWeight: 600, fontSize: '0.875rem' }}>3D Viewport</Box>
                        </Box>

                        <FormControlLabel
                            control={
                                <Switch
                                    checked={settings.show3dView}
                                    onChange={handle3dViewToggle}
                                    size="small"
                                />
                            }
                            label={settings.show3dView ? 'Visible' : 'Hidden'}
                            sx={{ ml: 0 }}
                        />
                    </Box>

                    {/* ── Layout direction (only when 3D is on) ─── */}
                    {settings.show3dView && (
                        <>
                            <Divider />

                            <Box>
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                                    <SplitscreenIcon fontSize="small" />
                                    <Box sx={{ fontWeight: 600, fontSize: '0.875rem' }}>Layout</Box>
                                </Box>

                                <ToggleButtonGroup
                                    value={settings.layoutDirection}
                                    exclusive
                                    onChange={handleLayoutDirectionChange}
                                    size="small"
                                    fullWidth
                                >
                                    <ToggleButton value="horizontal" aria-label="side by side">
                                        <Tooltip title="Side by side">
                                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                                                {/* Two vertical panels icon */}
                                                <ViewSidebarIcon fontSize="small" />
                                                <Box sx={{ fontSize: '0.75rem' }}>Side by side</Box>
                                            </Box>
                                        </Tooltip>
                                    </ToggleButton>
                                    <ToggleButton value="vertical" aria-label="stacked">
                                        <Tooltip title="Stacked">
                                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                                                <ViewAgendaIcon fontSize="small" />
                                                <Box sx={{ fontSize: '0.75rem' }}>Stacked</Box>
                                            </Box>
                                        </Tooltip>
                                    </ToggleButton>
                                </ToggleButtonGroup>
                            </Box>
                        </>
                    )}
                </Paper>
            )}
        </>
    );
};
