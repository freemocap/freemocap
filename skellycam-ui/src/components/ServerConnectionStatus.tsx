import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useServer } from '@/services/server/ServerContextProvider';
import { useTranslation } from "react-i18next";
import { useElectronIPC } from '@/services';
import { useRecordingGuard } from '@/components/RecordingGuardProvider';
import { DEFAULT_HOST, DEFAULT_PORT } from '@/services/server/server-helpers/server-urls';
import DropdownButton from './ui-components/DropdownButton';
import ToggleButtonComponent from './ui-components/ToggleButtonComponent';
import ToggleComponent from './ui-components/ToggleComponent';
import SubactionHeader from './ui-components/SubactionHeader';
import { STATES } from './ui-components/states';
import IconButton from './ui-components/IconButton';
import ButtonSm from './ui-components/ButtonSm';
import NameDropdownSelector from '@/components/ui-components/NameDropdownSelector';


export interface ExecutableCandidate {
    name: string;
    path: string;
    description: string;
    isValid?: boolean;
    error?: string;
    resolvedPath?: string;
}

const WS_RECONNECT_INTERVAL_MS = 3000;

const STORAGE_KEYS = {
    SELECTED_EXE_PATH: 'skellycam:selectedExePath',
    AUTO_LAUNCH_SERVER: 'skellycam:autoLaunchServer',
    AUTO_CONNECT_WS: 'skellycam:autoConnectWs',
    SERVER_HOST: 'skellycam:serverHost',
    SERVER_PORT: 'skellycam:serverPort',
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

export const ServerConnectionStatus: React.FC<{ compact?: boolean }> = ({ compact = false }) => {
    const { isConnected, connect, disconnect, connectedCameraIds, updateServerConnection } = useServer();
    const { t } = useTranslation();
    const { isElectron, api } = useElectronIPC();
    const { requestGuardedAction } = useRecordingGuard();

    // Persisted UI state
    const [selectedExePath, setSelectedExePath] = useState(() => loadFromStorage(STORAGE_KEYS.SELECTED_EXE_PATH, ''));
    const [autoLaunchServer, setAutoLaunchServer] = useState(() => loadFromStorage(STORAGE_KEYS.AUTO_LAUNCH_SERVER, true));
    const [autoConnectWs, setAutoConnectWs] = useState(() => loadFromStorage(STORAGE_KEYS.AUTO_CONNECT_WS, true));
    const [serverHost, setServerHost] = useState(() => loadFromStorage(STORAGE_KEYS.SERVER_HOST, DEFAULT_HOST));
    const [serverPort, setServerPort] = useState(() => loadFromStorage(STORAGE_KEYS.SERVER_PORT, DEFAULT_PORT));

    const [hostDraft, setHostDraft] = useState(serverHost);
    const [portDraft, setPortDraft] = useState(String(serverPort));

    // Transient state
    const [showAdvancedSettings, setShowAdvancedSettings] = useState(false);
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

    useEffect(() => { if (compact) return; saveToStorage(STORAGE_KEYS.SELECTED_EXE_PATH, selectedExePath); }, [selectedExePath, compact]);
    useEffect(() => { if (compact) return; saveToStorage(STORAGE_KEYS.AUTO_LAUNCH_SERVER, autoLaunchServer); }, [autoLaunchServer, compact]);
    useEffect(() => { if (compact) return; saveToStorage(STORAGE_KEYS.AUTO_CONNECT_WS, autoConnectWs); }, [autoConnectWs, compact]);
    useEffect(() => { if (compact) return; saveToStorage(STORAGE_KEYS.SERVER_HOST, serverHost); }, [serverHost, compact]);
    useEffect(() => { if (compact) return; saveToStorage(STORAGE_KEYS.SERVER_PORT, serverPort); }, [serverPort, compact]);

    useEffect(() => {
        if (compact) return;
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
            try {
                await api.pythonServer.start.mutate({ exePath: selectedExePath || null });
            } catch (err) {
                if (selectedExePath) {
                    // Stored path is stale (e.g. old onefile binary replaced by onedir bundle).
                    // Clear it and retry with auto-detection.
                    console.warn('Stored executable path failed, clearing and retrying:', err);
                    setSelectedExePath('');
                    await api.pythonServer.start.mutate({ exePath: null });
                } else {
                    throw err;
                }
            }
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

    // ── Effects ──

    useEffect(() => {
        if (compact) return;
        if (isElectron && api) {
            pollServerStatus();
            loadCandidates();
        }
    }, [compact, isElectron, api, pollServerStatus, loadCandidates]);

    useEffect(() => {
        if (compact) return;
        if (!isElectron || !api) return;
        const interval = setInterval(pollServerStatus, 5000);
        return () => clearInterval(interval);
    }, [compact, isElectron, api, pollServerStatus]);

    useEffect(() => {
        if (compact) return;
        if (!isElectron || !api) return;
        if (!autoLaunchServer) return;
        if (autoLaunchFiredRef.current) return;
        if (candidatesLoading) return;
        if (serverRunning || serverLoading) return;
        autoLaunchFiredRef.current = true;
        console.log('Auto-launching server...');
        startServer();
    }, [compact, isElectron, api, autoLaunchServer, candidatesLoading, serverRunning, serverLoading, startServer]);

    useEffect(() => {
        if (compact) return;
        if (!autoConnectWs) return;
        if (isConnected) return;
        connect();
        const interval = setInterval(() => {
            if (!isConnected) connect();
        }, WS_RECONNECT_INTERVAL_MS);
        return () => clearInterval(interval);
    }, [compact, autoConnectWs, isConnected, connect]);

    // ── Toggle handlers ──

    const handleToggleAutoLaunch = useCallback((newState: boolean) => {
        setAutoLaunchServer(newState);
    }, []);

    const handleToggleAutoConnectWs = useCallback((newState: boolean) => {
        setAutoConnectWs(newState);
        if (!newState) requestGuardedAction('Stop Recording & Disconnect', () => disconnect());
    }, [disconnect, requestGuardedAction]);

    const handleToggleWsConnected = useCallback(() => {
        if (isConnected) {
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
        if (e.key === 'Enter') applyHostPort();
    }, [applyHostPort]);

    // ── Derived connection states ──

    const serverState = serverRunning ? STATES.CONNECTED : serverLoading ? STATES.CONNECTING : STATES.DISCONNECTED;
    const wsState = isConnected ? STATES.CONNECTED : autoConnectWs ? STATES.CONNECTING : STATES.DISCONNECTED;

    const getOverallStatus = () => {
        const states = isElectron ? [serverState, wsState] : [wsState];
        if (states.every((s) => s === STATES.CONNECTED)) return { text: t('connected'), iconClass: 'connected-icon' };
        if (states.some((s) => s === STATES.CONNECTING)) return { text: t('connecting'), iconClass: 'loader-icon' };
        if (states.some((s) => s === STATES.CONNECTED)) return { text: 'Connected', iconClass: 'connected-icon' };
        return { text: 'Not Connected', iconClass: 'warning-icon' };
    };

    const overallStatus = getOverallStatus();
    const cameraCountSuffix = isConnected && connectedCameraIds.length > 0
        ? ` (${connectedCameraIds.length} cam${connectedCameraIds.length !== 1 ? 's' : ''})`
        : '';

    const rowIconClass = (state: string) => {
        if (state === STATES.CONNECTED) return 'connected-icon';
        if (state === STATES.CONNECTING) return 'loader-icon';
        return 'warning-icon';
    };

    const toggleConfig = {
        connectConfig: { text: 'Connect', extraClasses: '' },
        connectingConfig: { text: 'Connecting...', extraClasses: 'loading disabled' },
        connectedConfig: { text: 'Connected', extraClasses: 'activated' },
    };

    // ── Render ──

    if (compact) {
        return (
            <IconButton
                icon={overallStatus.iconClass}
            />
        );
    }

    const validCandidates = candidates.filter((c) => c.isValid);
    const executableOptions = [
        ...validCandidates.map((c) => ({ label: c.name, value: c.path })),
        ...candidates.filter((c) => !c.isValid).map((c) => ({ label: `${c.name} (invalid)`, value: c.path })),
    ];

    const serverStatusColor = serverRunning ? 'bg-pink' : 'bg-red';
    const wsStatusColor = isConnected ? 'bg-pink' : 'bg-red';

    return (
        <DropdownButton
            buttonProps={{
                text: overallStatus.text + cameraCountSuffix,
                iconClass: overallStatus.iconClass,
                rightSideIcon: 'dropdown',
                textColor: 'text-gray',
                className: 'connection-status-button-opener full-width',
                
            }}
            dropdownItems={
                <div className="connection-container flex flex-col p-1 gap-2 br-1 bg-darkgray border-1 border-mid-black">
                     <div className="group-0 connection-group flex flex-col gap-1 bg-middark br-1 p-1">
                    {/* ── Quick Toggle Rows ── */}
                    {/* Python server row (Electron only) */}
                    {isElectron && (
                       
                                    <div className="row-1 gap-1 p-1 br-1 flex justify-content-space-between items-center h-25">
                                        <div className="text-container overflow-hidden flex items-center gap-1">
                                            <span className={`icon icon-size-20 ${rowIconClass(serverState)}`} />
                                            <p className="text text-nowrap text-left bg">Python server</p>
                                        </div>
                                        <ToggleButtonComponent
                                            state={serverState}
                                            {...toggleConfig}
                                            textColor="text-white"
                                            onConnect={startServer}
                                            onDisconnect={stopServer}
                                        />
                                    </div>
                                )}

                                    {/* WebSocket row */}
                                    <div className="row-2 gap-1 p-1 br-1 flex justify-content-space-between items-center h-25">
                                        <div className="text-container overflow-hidden flex items-center gap-1">
                                            <span className={`icon icon-size-20 ${rowIconClass(wsState)}`} />
                                            <p className="text text-nowrap text-left bg">Websocket</p>
                                        </div>
                                        <ToggleButtonComponent
                                            state={wsState}
                                            {...toggleConfig}
                                            textColor="text-white"
                                            onConnect={() => { setAutoConnectWs(true); connect(); }}
                                            onDisconnect={() => requestGuardedAction('Stop Recording & Disconnect', () => { setAutoConnectWs(false); disconnect(); })}
                                        />
                                    </div>
                        </div>

                    {/* ── Advanced Settings Toggle ── */}
                    <div className="open-advanced-settings-button-container flex flex-row flex-wrap justify-content-center pl-1 pr-1 ">
                        <ButtonSm
                            text={showAdvancedSettings ? 'Hide settings and preferences' : 'Show settings and preferences'}
                            onClick={() => setShowAdvancedSettings((prev) => !prev)}
                            iconClass="settings-icon"
                            
                            className="full-width text-center"
                            rightSideIcon = "dropdown"


                        />
                    </div>

                    {/* ── Detailed Settings Sections ── */}
                    {showAdvancedSettings && (
                    <>
                    {/* ── Server Process Section (Electron only) ── */}
                    {isElectron && (
                        <div className="server-process-section bg-middark flex flex-col gap-1 br-1 p-2">
                            <SubactionHeader text="Server Process" />

                            <ToggleComponent
                                text={t('autoLaunch')}
                                isToggled={autoLaunchServer}
                                onToggle={handleToggleAutoLaunch}
                            />

                            {/* Status */}
                            <div className="flex items-center gap-1 p-1">
                                <div
                                    className={`${serverStatusColor} br-5`}
                                    style={{ width: 8, height: 8, flexShrink: 0 }}
                                />
                                <p className="text sm text-gray">
                                    {serverRunning ? t('running') : t('stopped')}
                                    {processInfo?.pid ? ` (PID: ${processInfo.pid})` : ''}
                                </p>
                            </div>

                            {/* Executable selector */}
                            <div className="executable-selector-container flex flex-col gap-1 p-1">
                                
                                <div className="flex flex-row items-center justify-content-space-between">
                                <p className="text md text-nowrap">{t('executable')}
                                    
                                </p>

                                {/* Browse + Refresh */}
                            <div className="executable-actions flex gap-1">
                                <IconButton
                                    icon="subfolder-icon"
                                    onClick={browseForExecutable}
                                    disabled={serverRunning || serverLoading}
                                    title={t('browseForExecutable')}
                                    className="icon-size-28"

                                    tooltip={true}
                                    tooltipText={t('browseForExecutable')}
                                    tooltipPosition="pos-bottom"
                                />
                                <IconButton
                                    icon="rotate-icon"
                                    onClick={refreshCandidates}
                                    disabled={serverRunning || candidatesLoading}
                                    title={t('refreshCandidates')}
                                    className={`icon-size-28${candidatesLoading ? ' loader-icon' : ''}`}
                                    tooltip={true}
                                    tooltipText={t('refreshCandidates')}
                                    tooltipPosition="pos-bottom"
                                />
                            </div>
                                </div>
                                <NameDropdownSelector
                                    options={executableOptions.map(o => o.value)}
                                    initialValue={selectedExePath}
                                    onChange={setSelectedExePath}
                                    className="flex flex-row"
                                    
                                />
                            </div>

                            

                            {/* Launch / Stop / Reset */}
                            <div className="launch-section flex flex-row flex-wrap gap-2 flex-end">
                                <ButtonSm
                                    text="Launch"
                                    onClick={() => startServer()}
                                    disabled={serverRunning || serverLoading}
                                    className="primary flex-1"
                                    title={t('Launch')}
                                />
                                <ButtonSm
                                    text="Stop"
                                    onClick={() => stopServer()}
                                    disabled={!serverRunning || serverLoading}
                                    className="secondary flex-1"
                                    title={t('Stop')}
                                />
                                <ButtonSm
                                    text="Reset"
                                    onClick={() => resetServer()}
                                    disabled={!serverRunning || serverLoading}
                                    className="flex-1"
                                    title={t('Reset')}
                                />
                            </div>

                            {/* Running path */}
                            {currentExePath && (
                                <p className="text sm text-gray text-nowrap overflow-hidden" title={currentExePath}>
                                    {t('runningPath', { path: currentExePath })}
                                </p>
                            )}

                            {/* Error */}
                            {error && (
                                <p className="text sm text-warning p-2 mt-1 border-1 border-solid border-warning br-1 text-wrap ">{error}</p>
                            )}
                        </div>
                    )}

                    {/* ── WebSocket Section ── */}
                    <div className="websocket-section bg-middark flex flex-col gap-1 br-1 p-2">
                        <SubactionHeader text="Websocket Connection" />

                        <ToggleComponent
                            text={t('autoConnect')}
                            isToggled={autoConnectWs}
                            onToggle={handleToggleAutoConnectWs}
                        />

                        {/* Host / Port inputs */}
                        <div className="flex gap-1">
                            <div className="input-with-string flex-3">
                                <input
                                    className="input-field"
                                    placeholder={t('host')}
                                    value={hostDraft}
                                    onChange={(e) => setHostDraft(e.target.value)}
                                    onBlur={applyHostPort}
                                    onKeyDown={handleHostPortKeyDown}
                                    disabled={isConnected}
                                />
                            </div>
                            <div className="input-with-unit">
                                <input
                                    className="input-field numeric-input"
                                    type="number"
                                    placeholder={t('port')}
                                    value={portDraft}
                                    min={1}
                                    max={65535}
                                    onChange={(e) => setPortDraft(e.target.value)}
                                    onBlur={applyHostPort}
                                    onKeyDown={handleHostPortKeyDown}
                                    disabled={isConnected}
                                />
                            </div>
                        </div>
                    </div>
                    </>
                    )}

                </div>
            }
        />
    );
};
