import React, { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import ToggleComponent from './ui-components/ToggleComponent';
import NameDropdownSelector from './ui-components/NameDropdownSelector';
import SubactionHeader from './ui-components/SubactionHeader';
import type { ExecutableCandidate } from './ServerConnectionStatus';
import IconButton from './ui-components/IconButton';
import ButtonSm from './ui-components/ButtonSm';

interface ConnectionSettingsModalProps {
    open: boolean;
    onClose: () => void;
    isElectron: boolean;
    // Server process
    autoLaunchServer: boolean;
    handleToggleAutoLaunch: (newState: boolean) => void;
    serverRunning: boolean;
    serverLoading: boolean;
    processInfo: { pid: number | undefined; killed: boolean } | null;
    candidates: ExecutableCandidate[];
    candidatesLoading: boolean;
    selectedExePath: string;
    setSelectedExePath: (path: string) => void;
    browseForExecutable: () => void;
    refreshCandidates: () => void;
    startServer: () => void;
    stopServer: () => void;
    resetServer: () => void;
    currentExePath: string | null;
    error: string | null;
    // WebSocket
    isConnected: boolean;
    autoConnectWs: boolean;
    handleToggleAutoConnectWs: (newState: boolean) => void;
    connectedCameraIds: string[];
    hostDraft: string;
    portDraft: string;
    setHostDraft: (v: string) => void;
    setPortDraft: (v: string) => void;
    applyHostPort: () => void;
    handleHostPortKeyDown: (e: React.KeyboardEvent) => void;
    handleToggleWsConnected: () => void;
}

export const ConnectionSettingsModal: React.FC<ConnectionSettingsModalProps> = (props) => {
    const {
        open, onClose, isElectron,
        autoLaunchServer, handleToggleAutoLaunch, serverRunning, serverLoading,
        processInfo, candidates, candidatesLoading, selectedExePath, setSelectedExePath,
        browseForExecutable, refreshCandidates, startServer, stopServer, resetServer,
        currentExePath, error,
        isConnected, autoConnectWs, handleToggleAutoConnectWs, connectedCameraIds,
        hostDraft, portDraft, setHostDraft, setPortDraft, applyHostPort,
        handleHostPortKeyDown, handleToggleWsConnected,
    } = props;

    const { t } = useTranslation();

    // Close on Escape key
    useEffect(() => {
        if (!open) return;
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === 'Escape') onClose();
        };
        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [open, onClose]);

    if (!open) return null;

    const validCandidates = candidates.filter((c) => c.isValid);
    const allCandidateNames = [
        ...validCandidates.map((c) => c.name),
        ...candidates.filter((c) => !c.isValid).map((c) => `${c.name} (invalid)`),
    ];
    const selectedName = selectedExePath
        ? (candidates.find((c) => c.path === selectedExePath)?.name ?? '')
        : '';

    const handleExeChange = (name: string) => {
        const match = candidates.find((c) => c.name === name || `${c.name} (invalid)` === name);
        if (match) setSelectedExePath(match.path);
    };

    const serverStatusColor = serverRunning ? 'bg-pink' : 'bg-red';
    const wsStatusColor = isConnected ? 'bg-pink' : 'bg-red';

    return (
        <div
            className="splash-overlay inset-0 reveal fadeIn"
            style={{ position: 'fixed', zIndex: 50 }}
            onClick={onClose}
        >
            <div
                className="bg-dark br-2 border-1 border-black elevated-sharp flex flex-col p-2 gap-2"
                style={{ minWidth: 320, maxWidth: 420, maxHeight: '80vh', overflowY: 'auto' }}
                onClick={(e) => e.stopPropagation()}
            >
                {/* Header */}
                <div className="flex justify-content-space-between items-center">
                    <p className="text bg text-white">Connection Settings</p>
                    <IconButton
                        icon="close-icon"
                        onClick={onClose}
                     />
                </div>

                {/* ── Server Process Section (Electron only) ── */}
                {isElectron && (
                    <div className="flex flex-col gap-1 bg-middark br-1 p-1">
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
                        <div className="toggle-button gap-1 p-1 br-1 flex justify-content-space-between items-center h-25">
                            <p className="text md text-nowrap">{t('executable')}</p>
                            <NameDropdownSelector
                                options={allCandidateNames}
                                initialValue={selectedName}
                                onChange={handleExeChange}
                            />
                        </div>

                        {/* Browse + Refresh */}
                        <div className="flex gap-1">
                            <IconButton
                                icon="import-icon"
                                onClick={browseForExecutable}
                                disabled={serverRunning || serverLoading}
                                title={t('browseForExecutable')}
                            />
                            <IconButton
                                icon="rotate-icon"
                                onClick={refreshCandidates}
                                disabled={serverRunning || candidatesLoading}
                                title={t('refreshCandidates')}
                                className={candidatesLoading ? 'loader-icon' : ''}
                            />
                        </div>

                        {/* Launch / Stop / Reset */}
                        <div className="flex gap-1">
                            <ButtonSm
                                text="Launch"
                                onClick={() => startServer()}
                                disabled={serverRunning || serverLoading}
                                className="flex-1 justify-center primary"
                                title={t('Launch')}
                            />
                            <ButtonSm
                                text="Stop"
                                onClick={() => stopServer()}
                                disabled={!serverRunning || serverLoading}
                                className="flex-1 justify-center secondary"
                                title={t('Stop')}
                            />
                            <ButtonSm
                                text="Reset"
                                onClick={() => resetServer()}
                                disabled={!serverRunning || serverLoading}
                                className="flex-1 justify-center"
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
                            <p className="text sm text-warning">{error}</p>
                        )}
                    </div>
                )}

                {/* ── WebSocket Section ── */}
                <div className="flex flex-col gap-1 bg-middark br-1 p-1">
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

                    {/* Status + connect/disconnect */}
                    <div className="flex items-center gap-1 p-1 justify-content-space-between">
                        <div className="flex items-center gap-1">
                            <div
                                className={`${wsStatusColor} br-5`}
                                style={{ width: 8, height: 8, flexShrink: 0 }}
                            />
                            <p className="text sm text-gray">
                                {isConnected
                                    ? `${t('connected')}${connectedCameraIds.length > 0 ? ` — ${connectedCameraIds.length} cam${connectedCameraIds.length !== 1 ? 's' : ''}` : ''}`
                                    : autoConnectWs ? t('connecting') : t('disconnected')}
                            </p>
                        </div>
                        <ButtonSm
                            text={isConnected ? t('disconnect') : t('connect')}
                            onClick={handleToggleWsConnected}
                            className={isConnected ? 'secondary' : 'primary'}
                            title={isConnected ? t('disconnect') : t('connect')}
                        />
                    </div>
                </div>

            </div>
        </div>
    );
};
