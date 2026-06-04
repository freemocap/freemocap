import React from 'react';
import {useTranslation} from 'react-i18next';
import {ServerPanelState} from './useServerPanel';

type Props = Pick<
    ServerPanelState,
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
        <div
            onClick={() => setExpanded((prev) => !prev)}
            className="flex flex-row items-center"
            style={{gap: 4, padding: '4px 12px', cursor: 'pointer'}}
        >
            <div className="flex flex-row items-center" style={{gap: 4, flex: 1, minWidth: 0}}>
                <button
                    className="button icon-button"
                    onClick={handleToggleWsConnected}
                    title={isConnected ? t('disconnectWebSocket') : t('connectWebSocket')}
                    style={{padding: 2, color: wsStatusColor}}
                >
                    <span
                        className="icon icon-size-20"
                        style={{
                            backgroundImage: isConnected
                                ? 'var(--wifi-icon, none)'
                                : 'var(--wifi-off-icon, none)',
                            backgroundColor: wsStatusColor,
                            WebkitMaskImage: isConnected
                                ? 'var(--wifi-icon, none)'
                                : 'var(--wifi-off-icon, none)',
                        }}
                    />
                </button>

                <p className="text sm" style={{fontWeight: 500, color: wsStatusColor, whiteSpace: 'nowrap', fontSize: '0.7rem'}}>
                    {isConnected ? t('connected') : autoConnectWs ? t('connecting') : t('off')}
                </p>

                {isElectron && (
                    <>
                        <span style={{color: 'var(--color-text-muted)', fontSize: '0.7rem'}}>|</span>

                        <button
                            className="button icon-button"
                            onClick={handleToggleServerRunning}
                            disabled={serverLoading}
                            title={serverRunning ? t('stopServer') : t('launchServer')}
                            style={{padding: 2, color: serverStatusColor}}
                        >
                            {serverLoading ? (
                                <span className="icon loader-icon icon-size-20"/>
                            ) : serverRunning ? (
                                <span className="icon icon-size-20" style={{backgroundColor: serverStatusColor}}/>
                            ) : (
                                <span className="icon record-icon icon-size-20" style={{backgroundColor: serverStatusColor}}/>
                            )}
                        </button>

                        <p className="text sm" style={{fontWeight: 500, color: serverStatusColor, whiteSpace: 'nowrap', fontSize: '0.7rem'}}>
                            {serverLoading ? t('working') : serverRunning ? t('running') : t('stopped')}
                        </p>
                    </>
                )}

                {isConnected && connectedCameraIds.length > 0 && (
                    <span className="tag text sm" style={{marginLeft: 4, fontSize: '0.6rem', backgroundColor: 'rgba(0,255,255,0.1)', color: '#00ffff'}}>
                        {`${connectedCameraIds.length} cam${connectedCameraIds.length !== 1 ? 's' : ''}`}
                    </span>
                )}
            </div>

            <span
                className="icon icon-size-20"
                style={{color: 'var(--color-text-muted)', backgroundImage: expanded ? 'var(--collapse-icon)' : 'var(--expand-icon)'}}
            />
        </div>
    );
};
