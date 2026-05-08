import React from 'react';
import {Box, Button, FormControlLabel, Switch, TextField, Typography} from '@mui/material';
import WifiIcon from '@mui/icons-material/Wifi';
import WifiOffIcon from '@mui/icons-material/WifiOff';
import {useTranslation} from 'react-i18next';
import {ServerPanelState} from './useServerPanel';

type Props = Pick<
    ServerPanelState,
    | 'theme'
    | 'isConnected'
    | 'connectedCameraIds'
    | 'autoConnectWs'
    | 'hostDraft'
    | 'setHostDraft'
    | 'portDraft'
    | 'setPortDraft'
    | 'applyHostPort'
    | 'handleHostPortKeyDown'
    | 'handleToggleAutoConnectWs'
    | 'handleToggleWsConnected'
>;

export const WebSocketSection: React.FC<Props> = ({
    theme,
    isConnected,
    connectedCameraIds,
    autoConnectWs,
    hostDraft,
    setHostDraft,
    portDraft,
    setPortDraft,
    applyHostPort,
    handleHostPortKeyDown,
    handleToggleAutoConnectWs,
    handleToggleWsConnected,
}) => {
    const {t} = useTranslation();

    return (
        <Box sx={{border: `1px solid ${theme.palette.divider}`, borderRadius: 1, p: 1}}>
            {/* Header */}
            <Box sx={{display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 0.5}}>
                <Typography variant="caption" sx={{fontWeight: 600, color: theme.palette.text.secondary}}>
                    WEBSOCKET CONNECTION
                </Typography>
                <FormControlLabel
                    control={
                        <Switch
                            size="small"
                            checked={autoConnectWs}
                            onClick={handleToggleAutoConnectWs}
                            onChange={() => {}}
                        />
                    }
                    label={
                        <Typography variant="caption" sx={{fontSize: '0.65rem', color: theme.palette.text.secondary}}>
                            {t('autoConnect')}
                        </Typography>
                    }
                    sx={{mr: 0, ml: 0, height: 24}}
                    labelPlacement="start"
                />
            </Box>

            {/* Host / Port inputs */}
            <Box sx={{display: 'flex', gap: 0.5, mb: 1}}>
                <TextField
                    size="small"
                    label={t('host')}
                    value={hostDraft}
                    onChange={(e) => setHostDraft(e.target.value)}
                    onBlur={applyHostPort}
                    onKeyDown={handleHostPortKeyDown}
                    disabled={isConnected}
                    slotProps={{
                        inputLabel: {sx: {fontSize: '0.7rem'}},
                        input: {sx: {fontSize: '0.75rem'}},
                    }}
                    sx={{flex: 3}}
                />
                <TextField
                    size="small"
                    label={t('port')}
                    type="number"
                    value={portDraft}
                    onChange={(e) => setPortDraft(e.target.value)}
                    onBlur={applyHostPort}
                    onKeyDown={handleHostPortKeyDown}
                    disabled={isConnected}
                    slotProps={{
                        inputLabel: {sx: {fontSize: '0.7rem'}},
                        input: {sx: {fontSize: '0.75rem'}},
                        htmlInput: {min: 1, max: 65535},
                    }}
                    sx={{flex: 1}}
                />
            </Box>

            {/* Status + connect button */}
            <Box sx={{display: 'flex', alignItems: 'center', gap: 1}}>
                <Box
                    sx={{
                        width: 8,
                        height: 8,
                        borderRadius: '50%',
                        backgroundColor: isConnected ? '#00ffff' : theme.palette.error.main,
                    }}
                />
                <Typography variant="caption" sx={{color: theme.palette.text.primary, flex: 1}}>
                    {isConnected ? t('connected') : autoConnectWs ? t('connecting') : t('disconnected')}
                    {isConnected && connectedCameraIds.length > 0
                        ? ` — ${connectedCameraIds.length} camera${connectedCameraIds.length !== 1 ? 's' : ''}`
                        : ''}
                </Typography>

                <Button
                    variant={isConnected ? 'outlined' : 'contained'}
                    size="small"
                    color={isConnected ? 'error' : 'info'}
                    startIcon={isConnected ? <WifiOffIcon/> : <WifiIcon/>}
                    onClick={(e) => {
                        e.stopPropagation();
                        handleToggleWsConnected(e);
                    }}
                    sx={{fontSize: '0.7rem', textTransform: 'none'}}
                >
                    {isConnected ? t('disconnect') : t('connect')}
                </Button>
            </Box>
        </Box>
    );
};
