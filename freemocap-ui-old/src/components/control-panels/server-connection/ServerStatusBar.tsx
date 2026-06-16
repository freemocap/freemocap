import React from 'react';
import {Box, Chip, IconButton, Tooltip, Typography} from '@mui/material';
import {CircularProgress} from '@mui/material';
import WifiIcon from '@mui/icons-material/Wifi';
import WifiOffIcon from '@mui/icons-material/WifiOff';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import StopIcon from '@mui/icons-material/Stop';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import {useTranslation} from 'react-i18next';
import {ServerPanelState} from './useServerPanel';

type Props = Pick<
    ServerPanelState,
    | 'theme'
    | 'isConnected'
    | 'connectedCameraIds'
    | 'isElectron'
    | 'expanded'
    | 'setExpanded'
    | 'serverRunning'
    | 'serverLoading'
    | 'autoConnectWs'
    | 'wsStatusColor'
    | 'serverStatusColor'
    | 'handleToggleWsConnected'
    | 'handleToggleServerRunning'
>;

export const ServerStatusBar: React.FC<Props> = ({
    theme,
    isConnected,
    connectedCameraIds,
    isElectron,
    expanded,
    setExpanded,
    serverRunning,
    serverLoading,
    autoConnectWs,
    wsStatusColor,
    serverStatusColor,
    handleToggleWsConnected,
    handleToggleServerRunning,
}) => {
    const {t} = useTranslation();

    return (
        <Box
            onClick={() => setExpanded((prev) => !prev)}
            sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 0.5,
                px: 1.5,
                py: 0.5,
                cursor: 'pointer',
                '&:hover': {backgroundColor: 'rgba(255,255,255,0.03)'},
            }}
        >
            <Box sx={{display: 'flex', alignItems: 'center', gap: 0.5, flex: 1, minWidth: 0}}>
                <Tooltip title={isConnected ? t('disconnectWebSocket') : t('connectWebSocket')}>
                    <IconButton
                        size="small"
                        onClick={handleToggleWsConnected}
                        sx={{p: 0.25, color: wsStatusColor}}
                    >
                        {isConnected ? (
                            <WifiIcon sx={{fontSize: 16}}/>
                        ) : (
                            <WifiOffIcon sx={{fontSize: 16}}/>
                        )}
                    </IconButton>
                </Tooltip>

                <Typography
                    variant="caption"
                    sx={{fontWeight: 500, color: wsStatusColor, whiteSpace: 'nowrap', fontSize: '0.7rem'}}
                >
                    {isConnected ? t('connected') : autoConnectWs ? t('connecting') : t('off')}
                </Typography>

                {isElectron && (
                    <>
                        <Box sx={{mx: 0.25, color: theme.palette.text.disabled, fontSize: '0.7rem'}}>|</Box>

                        <Tooltip title={serverRunning ? t('stopServer') : t('launchServer')}>
                            <IconButton
                                size="small"
                                onClick={handleToggleServerRunning}
                                disabled={serverLoading}
                                sx={{p: 0.25, color: serverStatusColor}}
                            >
                                {serverLoading ? (
                                    <CircularProgress size={14}/>
                                ) : serverRunning ? (
                                    <StopIcon sx={{fontSize: 16}}/>
                                ) : (
                                    <PlayArrowIcon sx={{fontSize: 16}}/>
                                )}
                            </IconButton>
                        </Tooltip>

                        <Typography
                            variant="caption"
                            sx={{fontWeight: 500, color: serverStatusColor, whiteSpace: 'nowrap', fontSize: '0.7rem'}}
                        >
                            {serverLoading ? t('working') : serverRunning ? t('running') : t('stopped')}
                        </Typography>
                    </>
                )}

                {isConnected && connectedCameraIds.length > 0 && (
                    <Chip
                        label={`${connectedCameraIds.length} cam${connectedCameraIds.length !== 1 ? 's' : ''}`}
                        size="small"
                        sx={{
                            height: 18,
                            fontSize: '0.6rem',
                            ml: 0.5,
                            backgroundColor: 'rgba(0, 255, 255, 0.1)',
                            color: '#00ffff',
                        }}
                    />
                )}
            </Box>

            {expanded ? (
                <ExpandLessIcon sx={{fontSize: 16, color: theme.palette.text.secondary}}/>
            ) : (
                <ExpandMoreIcon sx={{fontSize: 16, color: theme.palette.text.secondary}}/>
            )}
        </Box>
    );
};
