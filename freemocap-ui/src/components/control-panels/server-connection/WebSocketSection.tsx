import React from 'react';
import {useTranslation} from 'react-i18next';
import {ServerPanelState} from './useServerPanel';

type Props = Pick<
    ServerPanelState,
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
        <div style={{border: '1px solid var(--color-border-secondary)', borderRadius: 4, padding: 8}}>
            {/* Header */}
            <div className="flex flex-row items-center" style={{justifyContent: 'space-between', marginBottom: 4}}>
                <p className="text sm text-gray" style={{fontWeight: 600}}>WEBSOCKET CONNECTION</p>
                <label className="flex flex-row items-center gap-1" style={{height: 24}}>
                    <span className="text sm text-gray" style={{fontSize: '0.65rem'}}>{t('autoConnect')}</span>
                    <input
                        type="checkbox"
                        checked={autoConnectWs}
                        onClick={handleToggleAutoConnectWs}
                        onChange={() => {}}
                        style={{accentColor: 'var(--color-info)'}}
                    />
                </label>
            </div>

            {/* Host / Port inputs */}
            <div className="flex flex-row" style={{gap: 4, marginBottom: 8}}>
                <div className="input-with-string" style={{flex: 3}}>
                    <input
                        className="input-field text md"
                        placeholder={t('host')}
                        value={hostDraft}
                        onChange={(e) => setHostDraft(e.target.value)}
                        onBlur={applyHostPort}
                        onKeyDown={handleHostPortKeyDown}
                        disabled={isConnected}
                        style={{fontSize: '0.75rem', width: '100%'}}
                    />
                </div>
                <div className="input-with-string" style={{flex: 1}}>
                    <input
                        className="input-field text md"
                        placeholder={t('port')}
                        type="number"
                        value={portDraft}
                        onChange={(e) => setPortDraft(e.target.value)}
                        onBlur={applyHostPort}
                        onKeyDown={handleHostPortKeyDown}
                        disabled={isConnected}
                        min={1}
                        max={65535}
                        style={{fontSize: '0.75rem', width: '100%'}}
                    />
                </div>
            </div>

            {/* Status + connect button */}
            <div className="flex flex-row items-center" style={{gap: 8}}>
                <div
                    style={{
                        width: 8,
                        height: 8,
                        borderRadius: '50%',
                        backgroundColor: isConnected ? '#00ffff' : 'var(--color-danger)',
                        flexShrink: 0,
                    }}
                />
                <p className="text sm" style={{color: 'var(--color-text-primary)', flex: 1}}>
                    {isConnected ? t('connected') : autoConnectWs ? t('connecting') : t('disconnected')}
                    {isConnected && connectedCameraIds.length > 0
                        ? ` — ${connectedCameraIds.length} camera${connectedCameraIds.length !== 1 ? 's' : ''}`
                        : ''}
                </p>

                <button
                    className={isConnected ? 'button sm secondary' : 'button sm primary'}
                    onClick={(e) => {
                        e.stopPropagation();
                        handleToggleWsConnected(e);
                    }}
                    style={{fontSize: '0.7rem'}}
                >
                    {isConnected ? t('disconnect') : t('connect')}
                </button>
            </div>
        </div>
    );
};
