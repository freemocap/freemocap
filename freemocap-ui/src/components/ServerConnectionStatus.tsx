import React, {useCallback, useEffect, useRef, useState} from 'react';
import {
    Box,
    Button,
    Chip,
    CircularProgress,
    Collapse,
    FormControl,
    FormControlLabel,
    IconButton,
    InputLabel,
    MenuItem,
    Select,
    Switch,
    TextField,
    Tooltip,
    Typography,
} from '@mui/material';
import {useTheme} from '@mui/material/styles';
import WifiIcon from '@mui/icons-material/Wifi';
import WifiOffIcon from '@mui/icons-material/WifiOff';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import StopIcon from '@mui/icons-material/Stop';
import RestartAltIcon from '@mui/icons-material/RestartAlt';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import RefreshIcon from '@mui/icons-material/Refresh';
import FolderOpenIcon from '@mui/icons-material/FolderOpen';
import {useServer} from '@/services/server/ServerContextProvider';
import {useTranslation} from "react-i18next";
import {useElectronIPC} from '@/services';
import {DEFAULT_HOST, DEFAULT_PORT} from '@/constants/server-urls';

interface ExecutableCandidate {
    name: string;
    path: string;
    description: string;
    isValid?: boolean;
    error?: string;
    resolvedPath?: string;
}

const AUTO_CONNECT_DELAY_MS = 2000;
const WS_RECONNECT_INTERVAL_MS = 3000;

const STORAGE_KEYS = {
    SELECTED_EXE_PATH: 'freemocap:selectedExePath',
    PANEL_EXPANDED: 'freemocap:serverPanelExpanded',
    AUTO_LAUNCH_SERVER: 'freemocap:autoLaunchServer',
    AUTO_CONNECT_WS: 'freemocap:autoConnectWs',
    SERVER_HOST: 'freemocap:serverHost',
    SERVER_PORT: 'freemocap:serverPort',
} as const;

function loadFromStorage<T>(key: string, fallback: T): T {
    try {
        const raw = localStorage.getItem(key);
        if (raw === null) return fallback;
        return JSON.parse(raw) as T;
    } catch {
        return fallback;
    }
}

function saveToStorage(key: string, value: unknown): void {
    try {
        localStorage.setItem(key, JSON.stringify(value));
    } catch (err) {
        console.error(`Failed to save ${key} to localStorage:`, err);
    }
}

export const ServerConnectionStatus: React.FC = () => {
    const theme = useTheme();
    const { isConnected, connect, disconnect, connectedCameraIds, updateServerConnection } = useServer();
    const { t } = useTranslation();
    const { isElectron, api } = useElectronIPC();

    // Persisted UI state
    const [expanded, setExpanded] = useState(() => loadFromStorage(STORAGE_KEYS.PANEL_EXPANDED, false));
    const [selectedExePath, setSelectedExePath] = useState(() => loadFromStorage(STORAGE_KEYS.SELECTED_EXE_PATH, ''));
    const [autoLaunchServer, setAutoLaunchServer] = useState(() => loadFromStorage(STORAGE_KEYS.AUTO_LAUNCH_SERVER, true));
    const [autoConnectWs, setAutoConnectWs] = useState(() => loadFromStorage(STORAGE_KEYS.AUTO_CONNECT_WS, true));
    const [serverHost, setServerHost] = useState(() => loadFromStorage(STORAGE_KEYS.SERVER_HOST, DEFAULT_HOST));
    const [serverPort, setServerPort] = useState(() => loadFromStorage(STORAGE_KEYS.SERVER_PORT, DEFAULT_PORT));

    // Text field drafts (applied on blur/enter so we don't reconnect on every keystroke)
    const [hostDraft, setHostDraft] = useState(serverHost);
    const [portDraft, setPortDraft] = useState(String(serverPort));

    // Transient state
    const [serverRunning, setServerRunning] = useState(false);
    const [serverLoading, setServerLoading] = useState(false);
    const [currentExePath, setCurrentExePath] = useState<string | null>(null);
    const [candidates, setCandidates] = useState<ExecutableCandidate[]>([]);
    const [candidatesLoading, setCandidatesLoading] = useState(false);
    const [processInfo, setProcessInfo] = useState<{ pid: number | undefined; killed: boolean } | null>(null);
    const [error, setError] = useState<string | null>(null);

    // Track whether the initial auto-launch has been attempted so we only fire once
    const autoLaunchFiredRef = useRef(false);
    // Guard against concurrent startServer calls from the auto-launch effect
    const serverLaunchingRef = useRef(false);

    // ── Persistence effects ──

    useEffect(() => { saveToStorage(STORAGE_KEYS.PANEL_EXPANDED, expanded); }, [expanded]);
    useEffect(() => { saveToStorage(STORAGE_KEYS.SELECTED_EXE_PATH, selectedExePath); }, [selectedExePath]);
    useEffect(() => { saveToStorage(STORAGE_KEYS.AUTO_LAUNCH_SERVER, autoLaunchServer); }, [autoLaunchServer]);
    useEffect(() => { saveToStorage(STORAGE_KEYS.AUTO_CONNECT_WS, autoConnectWs); }, [autoConnectWs]);
    useEffect(() => { saveToStorage(STORAGE_KEYS.SERVER_HOST, serverHost); }, [serverHost]);
    useEffect(() => { saveToStorage(STORAGE_KEYS.SERVER_PORT, serverPort); }, [serverPort]);

    // Apply persisted host/port to the server connection on mount
    useEffect(() => {
        updateServerConnection(serverHost, serverPort);
    }, []); // eslint-disable-line react-hooks/exhaustive-deps

    // ── Server status polling ──

    const pollServerStatus = useCallback(async () => {
        if (!isElectron || !api) return;
        try {
            const running = await api.pythonServer.isRunning.query();
            setServerRunning(running);
            const info = await api.pythonServer.getProcessInfo.query();
            setProcessInfo(info);
            const exePath = await api.pythonServer.getExecutablePath.query();
            setCurrentExePath(exePath);
        } catch (err) {
            console.error('Failed to poll server status:', err);
        }
    }, [isElectron, api]);

    // ── Candidate management ──

    const loadCandidates = useCallback(async () => {
        if (!isElectron || !api) return;
        setCandidatesLoading(true);
        try {
            const result = await api.pythonServer.getExecutableCandidates.query();
            const typed = result as ExecutableCandidate[];
            setCandidates(typed);
            if (!selectedExePath) {
                const firstValid = typed.find((c) => c.isValid);
                if (firstValid) {
                    setSelectedExePath(firstValid.path);
                }
            }
        } catch (err) {
            console.error('Failed to load executable candidates:', err);
            setError(`Failed to load candidates: ${err instanceof Error ? err.message : String(err)}`);
        } finally {
            setCandidatesLoading(false);
        }
    }, [isElectron, api, selectedExePath]);

    const refreshCandidates = useCallback(async () => {
        if (!isElectron || !api) return;
        setCandidatesLoading(true);
        setError(null);
        try {
            const result = await api.pythonServer.refreshCandidates.mutate();
            const typed = result as ExecutableCandidate[];
            setCandidates(typed);
            const firstValid = typed.find((c) => c.isValid);
            if (firstValid) {
                setSelectedExePath(firstValid.path);
            }
        } catch (err) {
            console.error('Failed to refresh candidates:', err);
            setError(`Failed to refresh: ${err instanceof Error ? err.message : String(err)}`);
        } finally {
            setCandidatesLoading(false);
        }
    }, [isElectron, api]);

    const browseForExecutable = useCallback(async () => {
        if (!isElectron || !api) return;
        try {
            const filePath = await api.fileSystem.selectExecutableFile.mutate();
            if (filePath) {
                setSelectedExePath(filePath);
            }
        } catch (err) {
            console.error('Failed to browse for executable:', err);
            setError(`Browse failed: ${err instanceof Error ? err.message : String(err)}`);
        }
    }, [isElectron, api]);

    // ── Server actions ──

    const startServer = useCallback(async () => {
        if (!isElectron || !api) return;
        if (serverLaunchingRef.current) return;
        serverLaunchingRef.current = true;
        setServerLoading(true);
        setError(null);
        try {
            const exePath = selectedExePath || null;
            await api.pythonServer.start.mutate({ exePath });
            await pollServerStatus();
        } catch (err) {
            console.error('Failed to start server:', err);
            setError(`Start failed: ${err instanceof Error ? err.message : String(err)}`);
        } finally {
            setServerLoading(false);
            serverLaunchingRef.current = false;
        }
    }, [isElectron, api, selectedExePath, pollServerStatus]);

    const stopServer = useCallback(async () => {
        if (!isElectron || !api) return;
        setServerLoading(true);
        setError(null);
        try {
            disconnect();
            await api.pythonServer.stop.mutate();
            await pollServerStatus();
        } catch (err) {
            console.error('Failed to stop server:', err);
            setError(`Stop failed: ${err instanceof Error ? err.message : String(err)}`);
        } finally {
            setServerLoading(false);
        }
    }, [isElectron, api, pollServerStatus, disconnect]);

    const resetServer = useCallback(async () => {
        if (!isElectron || !api) return;
        setServerLoading(true);
        setError(null);
        try {
            disconnect();
            await api.pythonServer.stop.mutate();
            await new Promise((resolve) => setTimeout(resolve, 500));
            const exePath = selectedExePath || null;
            await api.pythonServer.start.mutate({ exePath });
            await pollServerStatus();
        } catch (err) {
            console.error('Failed to reset server:', err);
            setError(`Reset failed: ${err instanceof Error ? err.message : String(err)}`);
        } finally {
            setServerLoading(false);
        }
    }, [isElectron, api, selectedExePath, pollServerStatus, disconnect]);

    // ── Initial load: poll status + load candidates ──

    useEffect(() => {
        if (isElectron && api) {
            pollServerStatus();
            loadCandidates();
        }
    }, [isElectron, api, pollServerStatus, loadCandidates]);

    // ── Poll server status periodically ──

    useEffect(() => {
        if (!isElectron || !api) return;
        const interval = setInterval(pollServerStatus, 5000);
        return () => clearInterval(interval);
    }, [isElectron, api, pollServerStatus]);

    // ── Auto-launch server on mount (once) ──
    // Waits for candidates to be loaded so selectedExePath is populated,
    // then fires a single launch attempt if the server is not already running.

    useEffect(() => {
        if (!isElectron || !api) return;
        if (!autoLaunchServer) return;
        if (autoLaunchFiredRef.current) return;
        if (candidatesLoading) return; // wait for candidates to load
        if (serverRunning || serverLoading) return;

        autoLaunchFiredRef.current = true;
        console.log('Auto-launching server...');
        startServer();
    }, [isElectron, api, autoLaunchServer, candidatesLoading, serverRunning, serverLoading, startServer]);

    // ── WebSocket auto-reconnect loop ──
    // When autoConnectWs is on and we're not connected, periodically call connect().
    // The underlying WebSocketConnection handles deduplication of CONNECTING state.

    useEffect(() => {
        if (!autoConnectWs) return;
        if (isConnected) return;

        // Fire one immediate attempt
        connect();

        const interval = setInterval(() => {
            if (!isConnected) {
                connect();
            }
        }, WS_RECONNECT_INTERVAL_MS);

        return () => clearInterval(interval);
    }, [autoConnectWs, isConnected, connect]);

    // ── Toggle handlers ──

    const handleToggleAutoLaunch = useCallback((e: React.MouseEvent) => {
        e.stopPropagation();
        setAutoLaunchServer((prev) => !prev);
    }, []);

    const handleToggleAutoConnectWs = useCallback((e: React.MouseEvent) => {
        e.stopPropagation();
        setAutoConnectWs((prev) => {
            const next = !prev;
            if (!next) {
                // User is turning off auto-connect — disconnect now
                disconnect();
            }
            return next;
        });
    }, [disconnect]);

    const handleToggleServerRunning = useCallback((e: React.MouseEvent) => {
        e.stopPropagation();
        if (serverRunning) {
            stopServer();
        } else {
            startServer();
        }
    }, [serverRunning, startServer, stopServer]);

    const handleToggleWsConnected = useCallback((e: React.MouseEvent) => {
        e.stopPropagation();
        if (isConnected) {
            // Turn off auto-connect so it doesn't immediately reconnect
            setAutoConnectWs(false);
            disconnect();
        } else {
            setAutoConnectWs(true);
            connect();
        }
    }, [isConnected, connect, disconnect]);

    const applyHostPort = useCallback(() => {
        const trimmedHost = hostDraft.trim();
        const parsedPort = parseInt(portDraft, 10);
        if (!trimmedHost) return;
        if (isNaN(parsedPort) || parsedPort < 1 || parsedPort > 65535) return;

        setServerHost(trimmedHost);
        setServerPort(parsedPort);
        updateServerConnection(trimmedHost, parsedPort);
    }, [hostDraft, portDraft, updateServerConnection]);

    const handleHostPortKeyDown = useCallback((e: React.KeyboardEvent) => {
        if (e.key === 'Enter') {
            applyHostPort();
        }
    }, [applyHostPort]);

    // ── Derived values ──

    const wsStatusColor = isConnected ? '#00ffff' : '#f44336';
    const serverStatusColor = serverRunning ? theme.palette.success.main : theme.palette.text.disabled;

    const validCandidates = candidates.filter((c) => c.isValid);
    const invalidCandidates = candidates.filter((c) => !c.isValid);

    // ── Render ──

    return (
        <Box
            sx={{
                borderBottom: `1px solid ${theme.palette.divider}`,
                backgroundColor: theme.palette.mode === 'dark'
                    ? 'rgba(0, 0, 0, 0.2)'
                    : 'rgba(0, 0, 0, 0.02)',
            }}
        >
            {/* ── Collapsed summary row ── */}
            <Box
                onClick={() => setExpanded((prev) => !prev)}
                sx={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 0.5,
                    px: 1.5,
                    py: 0.5,
                    cursor: 'pointer',
                    '&:hover': { backgroundColor: 'rgba(255,255,255,0.03)' },
                }}
            >
                {/* Status labels */}
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, flex: 1, minWidth: 0 }}>
                    {/* WS toggle button */}
                    <Tooltip title={isConnected ? t('disconnectWebSocket') : t('connectWebSocket')}>
                        <IconButton
                            size="small"
                            onClick={handleToggleWsConnected}
                            sx={{ p: 0.25, color: wsStatusColor }}
                        >
                            {isConnected ? (
                                <WifiIcon sx={{ fontSize: 16 }} />
                            ) : (
                                <WifiOffIcon sx={{ fontSize: 16 }} />
                            )}
                        </IconButton>
                    </Tooltip>

                    <Typography
                        variant="caption"
                        sx={{ fontWeight: 500, color: wsStatusColor, whiteSpace: 'nowrap', fontSize: '0.7rem' }}
                    >
                        {isConnected ? t('connected') : autoConnectWs ? t('connecting') : t('off')}
                    </Typography>

                    {isElectron && (
                        <>
                            <Box sx={{ mx: 0.25, color: theme.palette.text.disabled, fontSize: '0.7rem' }}>|</Box>

                            {/* Server toggle button */}
                            <Tooltip title={serverRunning ? t('stopServer') : t('launchServer')}>
                                <IconButton
                                    size="small"
                                    onClick={handleToggleServerRunning}
                                    disabled={serverLoading}
                                    sx={{ p: 0.25, color: serverStatusColor }}
                                >
                                    {serverLoading ? (
                                        <CircularProgress size={14} />
                                    ) : serverRunning ? (
                                        <StopIcon sx={{ fontSize: 16 }} />
                                    ) : (
                                        <PlayArrowIcon sx={{ fontSize: 16 }} />
                                    )}
                                </IconButton>
                            </Tooltip>

                            <Typography
                                variant="caption"
                                sx={{ fontWeight: 500, color: serverStatusColor, whiteSpace: 'nowrap', fontSize: '0.7rem' }}
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
                    <ExpandLessIcon sx={{ fontSize: 16, color: theme.palette.text.secondary }} />
                ) : (
                    <ExpandMoreIcon sx={{ fontSize: 16, color: theme.palette.text.secondary }} />
                )}
            </Box>

            {/* ── Expanded panel ── */}
            <Collapse in={expanded}>
                <Box sx={{ px: 1.5, pb: 1.5, display: 'flex', flexDirection: 'column', gap: 1.5 }}>
                    {/* ── Server Process Section (Electron only) ── */}
                    {isElectron && (
                        <Box sx={{ border: `1px solid ${theme.palette.divider}`, borderRadius: 1, p: 1 }}>
                            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 0.5 }}>
                                <Typography
                                    variant="caption"
                                    sx={{ fontWeight: 600, color: theme.palette.text.secondary }}
                                >
                                    SERVER PROCESS
                                </Typography>
                                <FormControlLabel
                                    control={
                                        <Switch
                                            size="small"
                                            checked={autoLaunchServer}
                                            onClick={handleToggleAutoLaunch}
                                            onChange={() => {}} // controlled via onClick with stopPropagation
                                        />
                                    }
                                    label={
                                        <Typography variant="caption" sx={{ fontSize: '0.65rem', color: theme.palette.text.secondary }}>
                                            {t('autoLaunch')}
                                        </Typography>
                                    }
                                    sx={{ mr: 0, ml: 0, height: 24 }}
                                    labelPlacement="start"
                                />
                            </Box>

                            {/* Status line */}
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 1 }}>
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
                                <Typography variant="caption" sx={{ color: theme.palette.text.primary }}>
                                    {serverRunning ? t('running') : t('stopped')}
                                    {processInfo?.pid && ` (PID: ${processInfo.pid})`}
                                </Typography>
                            </Box>

                            {/* Executable selector */}
                            <FormControl fullWidth size="small" sx={{ mb: 1 }}>
                                <InputLabel sx={{ fontSize: '0.75rem' }}>{t('executable')}</InputLabel>
                                <Select
                                    value={selectedExePath}
                                    onChange={(e) => setSelectedExePath(e.target.value)}
                                    label={t("executable")}
                                    disabled={serverRunning || serverLoading}
                                    sx={{ fontSize: '0.75rem' }}
                                >
                                    {validCandidates.map((candidate) => (
                                        <MenuItem key={candidate.path} value={candidate.path} sx={{ fontSize: '0.75rem' }}>
                                            <Box>
                                                <Typography variant="caption" sx={{ fontWeight: 600 }}>
                                                    {candidate.name}
                                                </Typography>
                                                <Typography
                                                    variant="caption"
                                                    sx={{
                                                        display: 'block',
                                                        color: theme.palette.text.secondary,
                                                        fontSize: '0.65rem',
                                                        overflow: 'hidden',
                                                        textOverflow: 'ellipsis',
                                                        whiteSpace: 'nowrap',
                                                        maxWidth: 250,
                                                    }}
                                                >
                                                    {candidate.path}
                                                </Typography>
                                            </Box>
                                        </MenuItem>
                                    ))}
                                    {invalidCandidates.length > 0 && validCandidates.length > 0 && (
                                        <MenuItem disabled divider sx={{ fontSize: '0.65rem', opacity: 0.5 }}>
                                            — invalid —
                                        </MenuItem>
                                    )}
                                    {invalidCandidates.map((candidate) => (
                                        <MenuItem
                                            key={candidate.path}
                                            value={candidate.path}
                                            disabled
                                            sx={{ fontSize: '0.75rem', opacity: 0.4 }}
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

                            {/* Browse + Refresh row */}
                            <Box sx={{ display: 'flex', gap: 0.5, mb: 1 }}>
                                <Tooltip title={t('browseForExecutable')}>
                                    <IconButton
                                        size="small"
                                        onClick={browseForExecutable}
                                        disabled={serverRunning || serverLoading}
                                        sx={{ border: `1px solid ${theme.palette.divider}`, borderRadius: 1 }}
                                    >
                                        <FolderOpenIcon sx={{ fontSize: 16 }} />
                                    </IconButton>
                                </Tooltip>
                                <Tooltip title={t('refreshCandidates')}>
                                    <IconButton
                                        size="small"
                                        onClick={refreshCandidates}
                                        disabled={serverRunning || candidatesLoading}
                                        sx={{ border: `1px solid ${theme.palette.divider}`, borderRadius: 1 }}
                                    >
                                        {candidatesLoading ? (
                                            <CircularProgress size={14} />
                                        ) : (
                                            <RefreshIcon sx={{ fontSize: 16 }} />
                                        )}
                                    </IconButton>
                                </Tooltip>
                            </Box>

                            {/* Action buttons */}
                            <Box sx={{ display: 'flex', gap: 0.5 }}>
                                <Button
                                    variant="contained"
                                    size="small"
                                    color="success"
                                    startIcon={serverLoading ? <CircularProgress size={14} color="inherit" /> : <PlayArrowIcon />}
                                    onClick={() => startServer()}
                                    disabled={serverRunning || serverLoading}
                                    sx={{ flex: 1, fontSize: '0.7rem', textTransform: 'none' }}
                                >
                                    Launch
                                </Button>
                                <Button
                                    variant="contained"
                                    size="small"
                                    color="error"
                                    startIcon={serverLoading ? <CircularProgress size={14} color="inherit" /> : <StopIcon />}
                                    onClick={() => stopServer()}
                                    disabled={!serverRunning || serverLoading}
                                    sx={{ flex: 1, fontSize: '0.7rem', textTransform: 'none' }}
                                >
                                    Stop
                                </Button>
                                <Button
                                    variant="outlined"
                                    size="small"
                                    startIcon={serverLoading ? <CircularProgress size={14} /> : <RestartAltIcon />}
                                    onClick={() => resetServer()}
                                    disabled={!serverRunning || serverLoading}
                                    sx={{ flex: 1, fontSize: '0.7rem', textTransform: 'none' }}
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
                                        {t('runningPath', { path: currentExePath })}
                                    </Typography>
                                </Tooltip>
                            )}

                            {/* Error display */}
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
                    )}

                    {/* ── WebSocket Section ── */}
                    <Box sx={{ border: `1px solid ${theme.palette.divider}`, borderRadius: 1, p: 1 }}>
                        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 0.5 }}>
                            <Typography
                                variant="caption"
                                sx={{ fontWeight: 600, color: theme.palette.text.secondary }}
                            >
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
                                    <Typography variant="caption" sx={{ fontSize: '0.65rem', color: theme.palette.text.secondary }}>
                                        {t('autoConnect')}
                                    </Typography>
                                }
                                sx={{ mr: 0, ml: 0, height: 24 }}
                                labelPlacement="start"
                            />
                        </Box>

                        {/* Host / Port inputs */}
                        <Box sx={{ display: 'flex', gap: 0.5, mb: 1 }}>
                            <TextField
                                size="small"
                                label={t("host")}
                                value={hostDraft}
                                onChange={(e) => setHostDraft(e.target.value)}
                                onBlur={applyHostPort}
                                onKeyDown={handleHostPortKeyDown}
                                disabled={isConnected}
                                slotProps={{ inputLabel: { sx: { fontSize: '0.7rem' } }, input: { sx: { fontSize: '0.75rem' } } }}
                                sx={{ flex: 3 }}
                            />
                            <TextField
                                size="small"
                                label={t("port")}
                                type="number"
                                value={portDraft}
                                onChange={(e) => setPortDraft(e.target.value)}
                                onBlur={applyHostPort}
                                onKeyDown={handleHostPortKeyDown}
                                disabled={isConnected}
                                slotProps={{
                                    inputLabel: { sx: { fontSize: '0.7rem' } },
                                    input: { sx: { fontSize: '0.75rem' } },
                                    htmlInput: { min: 1, max: 65535 },
                                }}
                                sx={{ flex: 1 }}
                            />
                        </Box>

                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            <Box
                                sx={{
                                    width: 8,
                                    height: 8,
                                    borderRadius: '50%',
                                    backgroundColor: isConnected ? '#00ffff' : theme.palette.error.main,
                                }}
                            />
                            <Typography variant="caption" sx={{ color: theme.palette.text.primary, flex: 1 }}>
                                {isConnected ? t('connected') : autoConnectWs ? t('connecting') : t('disconnected')}
                                {isConnected && connectedCameraIds.length > 0
                                    ? ` — ${connectedCameraIds.length} camera${connectedCameraIds.length !== 1 ? 's' : ''}`
                                    : ''}
                            </Typography>

                            <Button
                                variant={isConnected ? 'outlined' : 'contained'}
                                size="small"
                                color={isConnected ? 'error' : 'info'}
                                startIcon={isConnected ? <WifiOffIcon /> : <WifiIcon />}
                                onClick={(e) => {
                                    e.stopPropagation();
                                    handleToggleWsConnected(e);
                                }}
                                sx={{ fontSize: '0.7rem', textTransform: 'none' }}
                            >
                                {isConnected ? t('disconnect') : t('connect')}
                            </Button>
                        </Box>
                    </Box>
                </Box>
            </Collapse>
        </Box>
    );
};
