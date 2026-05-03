import React from 'react';
import {
    Box,
    Button,
    CircularProgress,
    FormControl,
    FormControlLabel,
    IconButton,
    InputLabel,
    MenuItem,
    Select,
    Switch,
    Tooltip,
    Typography,
} from '@mui/material';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import StopIcon from '@mui/icons-material/Stop';
import RestartAltIcon from '@mui/icons-material/RestartAlt';
import RefreshIcon from '@mui/icons-material/Refresh';
import FolderOpenIcon from '@mui/icons-material/FolderOpen';
import {useTranslation} from 'react-i18next';
import {ServerPanelState} from './useServerPanel';

type Props = Pick<
    ServerPanelState,
    | 'theme'
    | 'serverRunning'
    | 'serverLoading'
    | 'processInfo'
    | 'currentExePath'
    | 'autoLaunchServer'
    | 'selectedExePath'
    | 'setSelectedExePath'
    | 'candidates'
    | 'candidatesLoading'
    | 'validCandidates'
    | 'invalidCandidates'
    | 'error'
    | 'startServer'
    | 'stopServer'
    | 'resetServer'
    | 'refreshCandidates'
    | 'browseForExecutable'
    | 'handleToggleAutoLaunch'
>;

export const ServerProcessSection: React.FC<Props> = ({
    theme,
    serverRunning,
    serverLoading,
    processInfo,
    currentExePath,
    autoLaunchServer,
    selectedExePath,
    setSelectedExePath,
    candidatesLoading,
    validCandidates,
    invalidCandidates,
    error,
    startServer,
    stopServer,
    resetServer,
    refreshCandidates,
    browseForExecutable,
    handleToggleAutoLaunch,
}) => {
    const {t} = useTranslation();

    return (
        <Box sx={{border: `1px solid ${theme.palette.divider}`, borderRadius: 1, p: 1}}>
            {/* Header */}
            <Box sx={{display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 0.5}}>
                <Typography variant="caption" sx={{fontWeight: 600, color: theme.palette.text.secondary}}>
                    SERVER PROCESS
                </Typography>
                <FormControlLabel
                    control={
                        <Switch
                            size="small"
                            checked={autoLaunchServer}
                            onClick={handleToggleAutoLaunch}
                            onChange={() => {}}
                        />
                    }
                    label={
                        <Typography variant="caption" sx={{fontSize: '0.65rem', color: theme.palette.text.secondary}}>
                            {t('autoLaunch')}
                        </Typography>
                    }
                    sx={{mr: 0, ml: 0, height: 24}}
                    labelPlacement="start"
                />
            </Box>

            {/* Status dot */}
            <Box sx={{display: 'flex', alignItems: 'center', gap: 0.5, mb: 1}}>
                <Box
                    sx={{
                        width: 8,
                        height: 8,
                        borderRadius: '50%',
                        backgroundColor: serverRunning
                            ? theme.palette.success.main
                            : theme.palette.error.main,
                    }}
                />
                <Typography variant="caption" sx={{color: theme.palette.text.primary}}>
                    {serverRunning ? t('running') : t('stopped')}
                    {processInfo?.pid && ` (PID: ${processInfo.pid})`}
                </Typography>
            </Box>

            {/* Executable selector */}
            <FormControl fullWidth size="small" sx={{mb: 1}}>
                <InputLabel sx={{fontSize: '0.75rem'}}>{t('executable')}</InputLabel>
                <Select
                    value={selectedExePath}
                    onChange={(e) => setSelectedExePath(e.target.value)}
                    label={t('executable')}
                    disabled={serverRunning || serverLoading}
                    sx={{fontSize: '0.75rem'}}
                    renderValue={(value) => (
                        <Tooltip title={value as string} placement="bottom-start">
                            <Box
                                sx={{
                                    overflow: 'auto',
                                    whiteSpace: 'nowrap',
                                    '&::-webkit-scrollbar': {height: 4},
                                    '&::-webkit-scrollbar-track': {background: 'transparent'},
                                    '&::-webkit-scrollbar-thumb': {background: theme.palette.divider, borderRadius: 2},
                                }}
                            >
                                <Typography variant="caption" sx={{fontSize: '0.75rem'}}>
                                    {value as string}
                                </Typography>
                            </Box>
                        </Tooltip>
                    )}
                >
                    {validCandidates.map((candidate) => (
                        <MenuItem key={candidate.path} value={candidate.path} sx={{fontSize: '0.75rem'}}>
                            <Tooltip title={candidate.path} placement="right">
                                <Box sx={{minWidth: 0, maxWidth: 400}}>
                                    <Typography variant="caption" sx={{fontWeight: 600}}>
                                        {candidate.name}
                                    </Typography>
                                    <Typography
                                        variant="caption"
                                        sx={{
                                            display: 'block',
                                            color: theme.palette.text.secondary,
                                            fontSize: '0.65rem',
                                            whiteSpace: 'nowrap',
                                        }}
                                    >
                                        {candidate.path}
                                    </Typography>
                                </Box>
                            </Tooltip>
                        </MenuItem>
                    ))}
                    {invalidCandidates.length > 0 && validCandidates.length > 0 && (
                        <MenuItem disabled divider sx={{fontSize: '0.65rem', opacity: 0.5}}>
                            — invalid —
                        </MenuItem>
                    )}
                    {invalidCandidates.map((candidate) => (
                        <MenuItem
                            key={candidate.path}
                            value={candidate.path}
                            disabled
                            sx={{fontSize: '0.75rem', opacity: 0.4}}
                        >
                            <Tooltip title={candidate.error || t('invalid')} placement="right">
                                <Typography variant="caption">
                                    {candidate.name} — {candidate.error || 'not found'}
                                </Typography>
                            </Tooltip>
                        </MenuItem>
                    ))}
                </Select>
            </FormControl>

            {/* Browse + Refresh */}
            <Box sx={{display: 'flex', gap: 0.5, mb: 1}}>
                <Tooltip title={t('browseForExecutable')}>
                    <IconButton
                        size="small"
                        onClick={browseForExecutable}
                        disabled={serverRunning || serverLoading}
                        sx={{border: `1px solid ${theme.palette.divider}`, borderRadius: 1}}
                    >
                        <FolderOpenIcon sx={{fontSize: 16}}/>
                    </IconButton>
                </Tooltip>
                <Tooltip title={t('refreshCandidates')}>
                    <IconButton
                        size="small"
                        onClick={refreshCandidates}
                        disabled={serverRunning || candidatesLoading}
                        sx={{border: `1px solid ${theme.palette.divider}`, borderRadius: 1}}
                    >
                        {candidatesLoading ? (
                            <CircularProgress size={14}/>
                        ) : (
                            <RefreshIcon sx={{fontSize: 16}}/>
                        )}
                    </IconButton>
                </Tooltip>
            </Box>

            {/* Action buttons */}
            <Box sx={{display: 'flex', gap: 0.5}}>
                <Button
                    variant="contained"
                    size="small"
                    color="success"
                    startIcon={serverLoading ? <CircularProgress size={14} color="inherit"/> : <PlayArrowIcon/>}
                    onClick={() => startServer()}
                    disabled={serverRunning || serverLoading}
                    sx={{flex: 1, fontSize: '0.7rem', textTransform: 'none'}}
                >
                    Launch
                </Button>
                <Button
                    variant="contained"
                    size="small"
                    color="error"
                    startIcon={serverLoading ? <CircularProgress size={14} color="inherit"/> : <StopIcon/>}
                    onClick={() => stopServer()}
                    disabled={!serverRunning || serverLoading}
                    sx={{flex: 1, fontSize: '0.7rem', textTransform: 'none'}}
                >
                    Stop
                </Button>
                <Button
                    variant="outlined"
                    size="small"
                    startIcon={serverLoading ? <CircularProgress size={14}/> : <RestartAltIcon/>}
                    onClick={() => resetServer()}
                    disabled={!serverRunning || serverLoading}
                    sx={{flex: 1, fontSize: '0.7rem', textTransform: 'none'}}
                >
                    Reset
                </Button>
            </Box>

            {/* Running executable path */}
            {currentExePath && (
                <Tooltip title={currentExePath} placement="bottom">
                    <Typography
                        variant="caption"
                        sx={{
                            mt: 0.5,
                            display: 'block',
                            color: theme.palette.text.secondary,
                            fontSize: '0.6rem',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                        }}
                    >
                        {t('runningPath', {path: currentExePath})}
                    </Typography>
                </Tooltip>
            )}

            {/* Error */}
            {error && (
                <Typography
                    variant="caption"
                    sx={{
                        mt: 0.5,
                        display: 'block',
                        color: theme.palette.error.main,
                        fontSize: '0.65rem',
                        wordBreak: 'break-word',
                    }}
                >
                    {error}
                </Typography>
            )}
        </Box>
    );
};
