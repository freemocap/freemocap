import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useServerPanel } from './useServerPanel';
import DropdownButton from '@/components/ui-components/DropdownButton';
import ToggleButtonComponent from '@/components/ui-components/ToggleButtonComponent';
import ToggleComponent from '@/components/ui-components/ToggleComponent';
import SubactionHeader from '@/components/ui-components/SubactionHeader';
import NameDropdownSelector from '@/components/ui-components/NameDropdownSelector';
import IconButton from '@/components/ui-components/IconButton';
import ButtonSm from '@/components/ui-components/ButtonSm';
import { STATES } from '@/components/ui-components/states';

export const ServerConnectionStatus: React.FC<{ compact?: boolean }> = ({ compact = false }) => {
    const { t } = useTranslation();
    const panel = useServerPanel();
    const {
        isConnected, connectedCameraIds, isElectron,
        autoConnectWs, autoLaunchServer,
        serverRunning, serverLoading, currentExePath,
        candidates, candidatesLoading, processInfo, error,
        selectedExePath, setSelectedExePath,
        hostDraft, setHostDraft, portDraft, setPortDraft,
        startServer, stopServer, resetServer,
        refreshCandidates, browseForExecutable,
        handleToggleAutoLaunch, handleToggleAutoConnectWs,
        handleToggleServerRunning, handleToggleWsConnected,
        applyHostPort, handleHostPortKeyDown,
    } = panel;

    const [showAdvancedSettings, setShowAdvancedSettings] = useState(false);

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

    if (compact) {
        return <IconButton icon={overallStatus.iconClass} />;
    }

    const executableOptions = [
        ...candidates.filter((c) => c.isValid).map((c) => c.path),
        ...candidates.filter((c) => !c.isValid).map((c) => c.path),
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
            dropdownClassName="connection-status-dropdown bg-dark"
            dropdownItems={
                <div className="connection-container flex flex-col p-1 gap-2 br-1 bg-darkgray border-mid-black">
                    <div className="group-0 connection-group flex flex-col gap-1 bg-middark br-1 p-1">
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
                                onConnect={() => { handleToggleAutoConnectWs(true); }}
                                onDisconnect={() => { handleToggleAutoConnectWs(false); }}
                            />
                        </div>
                    </div>

                    {/* Advanced settings toggle */}
                    <div className="open-advanced-settings-button-container flex flex-row flex-wrap justify-content-center pl-1 pr-1">
                        <ButtonSm
                            text={showAdvancedSettings ? 'Hide settings and preferences' : 'Show settings and preferences'}
                            onClick={() => setShowAdvancedSettings((prev) => !prev)}
                            iconClass="settings-icon"
                            className="full-width text-center"
                            rightSideIcon="dropdown"
                        />
                    </div>

                    {/* Detailed settings */}
                    {showAdvancedSettings && (
                        <>
                            {/* Server Process Section (Electron only) */}
                            {isElectron && (
                                <div className="server-process-section bg-middark flex flex-col gap-1 br-1 p-2">
                                    <SubactionHeader text="Server Process" />

                                    <ToggleComponent
                                        text={t('autoLaunch')}
                                        isToggled={autoLaunchServer}
                                        onToggle={handleToggleAutoLaunch}
                                    />

                                    {/* Status dot */}
                                    <div className="flex items-center gap-1 p-1">
                                        <div
                                            className={`${serverStatusColor} br-5 flex-shrink-0`}
                                            style={{ width: 8, height: 8 }}
                                        />
                                        <p className="text sm text-gray">
                                            {serverRunning ? t('running') : t('stopped')}
                                            {processInfo?.pid ? ` (PID: ${processInfo.pid})` : ''}
                                        </p>
                                    </div>

                                    {/* Executable selector */}
                                    <div className="executable-selector-container flex flex-col gap-1 p-1">
                                        <div className="flex flex-row items-center justify-content-space-between">
                                            <p className="text md text-nowrap">{t('executable')}</p>
                                            <div className="executable-actions flex gap-1">
                                                <IconButton
                                                    icon="subfolder-icon"
                                                    onClick={browseForExecutable}
                                                    disabled={serverRunning || serverLoading}
                                                    title={t('browseForExecutable')}
                                                    className="icon-size-25"
                                                    tooltip={true}
                                                    tooltipText={t('browseForExecutable')}
                                                    tooltipPosition="pos-bottom"
                                                />
                                                <IconButton
                                                    icon="rotate-icon"
                                                    onClick={refreshCandidates}
                                                    disabled={serverRunning || candidatesLoading}
                                                    title={t('refreshCandidates')}
                                                    className={`icon-size-25${candidatesLoading ? ' loader-icon' : ''}`}
                                                    tooltip={true}
                                                    tooltipText={t('refreshCandidates')}
                                                    tooltipPosition="pos-bottom"
                                                />
                                            </div>
                                        </div>
                                        <NameDropdownSelector
                                            options={executableOptions}
                                            initialValue={selectedExePath}
                                            onChange={setSelectedExePath}
                                            className="flex flex-row"
                                        />
                                    </div>

                                    {/* Launch / Stop / Reset */}
                                    <div className="launch-section flex flex-row flex-wrap gap-2 flex-end">
                                        <ButtonSm
                                            text={t('launchServer')}
                                            onClick={startServer}
                                            disabled={serverRunning || serverLoading}
                                            className="secondary"
                                            
                                        />
                                        <ButtonSm
                                            text={t('stopServer')}
                                            onClick={stopServer}
                                            disabled={!serverRunning || serverLoading}
                                            className="secondary flex-1"
                                        />
                                        <ButtonSm
                                            text="Reset"
                                            onClick={resetServer}
                                            disabled={!serverRunning || serverLoading}
                                            className="flex-1"
                                            buttonType="button sm quaternary"
                                        />
                                    </div>

                                    {currentExePath && (
                                        <p className="text sm text-gray text-nowrap overflow-hidden" title={currentExePath}>
                                            {t('runningPath', { path: currentExePath })}
                                        </p>
                                    )}

                                    {error && (
                                        <p className="text sm text-warning p-2 mt-1 border-1 border-warning br-1 text-wrap">{error}</p>
                                    )}
                                </div>
                            )}

                            {/* WebSocket Section */}
                            <div className="websocket-section bg-middark flex flex-col gap-1 br-1 p-2">
                                <SubactionHeader text="Websocket Connection" />

                                <ToggleComponent
                                    text={t('autoConnect')}
                                    isToggled={autoConnectWs}
                                    onToggle={handleToggleAutoConnectWs}
                                />

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
