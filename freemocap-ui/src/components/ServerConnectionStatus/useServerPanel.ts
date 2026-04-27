import React, {useCallback, useEffect, useRef, useState} from 'react';
import {Theme, useTheme} from '@mui/material/styles';
import {useServer} from '@/services/server/ServerContextProvider';
import {useTranslation} from 'react-i18next';
import {useElectronIPC} from '@/services';
import {DEFAULT_HOST, DEFAULT_PORT} from '@/constants/server-urls';
import {ExecutableCandidate, WS_RECONNECT_INTERVAL_MS} from './types';
import {STORAGE_KEYS, loadFromStorage, saveToStorage} from './storage';

export interface ServerPanelState {
    // theme
    theme: Theme;
    // server context
    isConnected: boolean;
    connectedCameraIds: string[];
    // electron
    isElectron: boolean;
    // persisted UI
    expanded: boolean;
    setExpanded: React.Dispatch<React.SetStateAction<boolean>>;
    selectedExePath: string;
    setSelectedExePath: React.Dispatch<React.SetStateAction<string>>;
    autoLaunchServer: boolean;
    autoConnectWs: boolean;
    serverHost: string;
    serverPort: number;
    // drafts
    hostDraft: string;
    setHostDraft: React.Dispatch<React.SetStateAction<string>>;
    portDraft: string;
    setPortDraft: React.Dispatch<React.SetStateAction<string>>;
    // transient
    serverRunning: boolean;
    serverLoading: boolean;
    currentExePath: string | null;
    candidates: ExecutableCandidate[];
    candidatesLoading: boolean;
    processInfo: { pid: number | undefined; killed: boolean } | null;
    error: string | null;
    // actions
    startServer: () => Promise<void>;
    stopServer: () => Promise<void>;
    resetServer: () => Promise<void>;
    refreshCandidates: () => Promise<void>;
    browseForExecutable: () => Promise<void>;
    // toggle handlers
    handleToggleAutoLaunch: (e: React.MouseEvent) => void;
    handleToggleAutoConnectWs: (e: React.MouseEvent) => void;
    handleToggleServerRunning: (e: React.MouseEvent) => void;
    handleToggleWsConnected: (e: React.MouseEvent) => void;
    // host/port
    applyHostPort: () => void;
    handleHostPortKeyDown: (e: React.KeyboardEvent) => void;
    // derived
    wsStatusColor: string;
    serverStatusColor: string;
    validCandidates: ExecutableCandidate[];
    invalidCandidates: ExecutableCandidate[];
}

export function useServerPanel(): ServerPanelState {
    const theme = useTheme();
    const {isConnected, connect, disconnect, connectedCameraIds, updateServerConnection} = useServer();
    const {t} = useTranslation();
    const {isElectron, api} = useElectronIPC();

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

    const autoLaunchFiredRef = useRef(false);
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
                if (firstValid) setSelectedExePath(firstValid.path);
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
            if (firstValid) setSelectedExePath(firstValid.path);
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
            if (filePath) setSelectedExePath(filePath);
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
            await api.pythonServer.start.mutate({ exePath: selectedExePath || null });
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
            await api.pythonServer.start.mutate({ exePath: selectedExePath || null });
            await pollServerStatus();
        } catch (err) {
            console.error('Failed to reset server:', err);
            setError(`Reset failed: ${err instanceof Error ? err.message : String(err)}`);
        } finally {
            setServerLoading(false);
        }
    }, [isElectron, api, selectedExePath, pollServerStatus, disconnect]);

    // ── Initial load + polling ──

    useEffect(() => {
        if (isElectron && api) {
            pollServerStatus();
            loadCandidates();
        }
    }, [isElectron, api, pollServerStatus, loadCandidates]);

    useEffect(() => {
        if (!isElectron || !api) return;
        const interval = setInterval(pollServerStatus, 5000);
        return () => clearInterval(interval);
    }, [isElectron, api, pollServerStatus]);

    // ── Auto-launch server (once) ──

    useEffect(() => {
        if (!isElectron || !api) return;
        if (!autoLaunchServer) return;
        if (autoLaunchFiredRef.current) return;
        if (candidatesLoading) return;
        if (serverRunning || serverLoading) return;

        autoLaunchFiredRef.current = true;
        console.log('Auto-launching server...');
        startServer();
    }, [isElectron, api, autoLaunchServer, candidatesLoading, serverRunning, serverLoading, startServer]);

    // ── WebSocket auto-reconnect ──

    useEffect(() => {
        if (!autoConnectWs) return;
        if (isConnected) return;

        connect();

        const interval = setInterval(() => {
            if (!isConnected) connect();
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
            if (!next) disconnect();
            return next;
        });
    }, [disconnect]);

    const handleToggleServerRunning = useCallback((e: React.MouseEvent) => {
        e.stopPropagation();
        if (serverRunning) stopServer();
        else startServer();
    }, [serverRunning, startServer, stopServer]);

    const handleToggleWsConnected = useCallback((e: React.MouseEvent) => {
        e.stopPropagation();
        if (isConnected) {
            setAutoConnectWs(false);
            disconnect();
        } else {
            setAutoConnectWs(true);
            connect();
        }
    }, [isConnected, connect, disconnect]);

    // ── Host / port ──

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
        if (e.key === 'Enter') applyHostPort();
    }, [applyHostPort]);

    // ── Derived values ──

    const wsStatusColor = isConnected ? '#00ffff' : '#f44336';
    const serverStatusColor = serverRunning ? theme.palette.success.main : theme.palette.text.disabled;
    const validCandidates = candidates.filter((c) => c.isValid);
    const invalidCandidates = candidates.filter((c) => !c.isValid);

    return {
        theme,
        isConnected,
        connectedCameraIds,
        isElectron,
        expanded,
        setExpanded,
        selectedExePath,
        setSelectedExePath,
        autoLaunchServer,
        autoConnectWs,
        serverHost,
        serverPort,
        hostDraft,
        setHostDraft,
        portDraft,
        setPortDraft,
        serverRunning,
        serverLoading,
        currentExePath,
        candidates,
        candidatesLoading,
        processInfo,
        error,
        startServer,
        stopServer,
        resetServer,
        refreshCandidates,
        browseForExecutable,
        handleToggleAutoLaunch,
        handleToggleAutoConnectWs,
        handleToggleServerRunning,
        handleToggleWsConnected,
        applyHostPort,
        handleHostPortKeyDown,
        wsStatusColor,
        serverStatusColor,
        validCandidates,
        invalidCandidates,
    };
}
