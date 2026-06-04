import React from 'react';
import {useTranslation} from 'react-i18next';
import {ServerPanelState} from './useServerPanel';

type Props = Pick<
    ServerPanelState,
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
        <div style={{border: '1px solid var(--color-border-secondary)', borderRadius: 4, padding: 8}}>
            {/* Header */}
            <div className="flex flex-row items-center" style={{justifyContent: 'space-between', marginBottom: 4}}>
                <p className="text sm text-gray" style={{fontWeight: 600}}>SERVER PROCESS</p>
                <label className="flex flex-row items-center gap-1" style={{height: 24}}>
                    <span className="text sm text-gray" style={{fontSize: '0.65rem'}}>{t('autoLaunch')}</span>
                    <input
                        type="checkbox"
                        checked={autoLaunchServer}
                        onClick={handleToggleAutoLaunch}
                        onChange={() => {}}
                        style={{accentColor: 'var(--color-info)'}}
                    />
                </label>
            </div>

            {/* Status dot */}
            <div className="flex flex-row items-center" style={{gap: 4, marginBottom: 8}}>
                <div
                    style={{
                        width: 8,
                        height: 8,
                        borderRadius: '50%',
                        backgroundColor: serverRunning ? 'var(--color-success)' : 'var(--color-danger)',
                        flexShrink: 0,
                    }}
                />
                <p className="text sm" style={{color: 'var(--color-text-primary)'}}>
                    {serverRunning ? t('running') : t('stopped')}
                    {processInfo?.pid && ` (PID: ${processInfo.pid})`}
                </p>
            </div>

            {/* Executable selector */}
            <div style={{marginBottom: 8}}>
                <select
                    className="input-field text md"
                    value={selectedExePath}
                    onChange={(e) => setSelectedExePath(e.target.value)}
                    disabled={serverRunning || serverLoading}
                    style={{width: '100%', fontSize: '0.75rem'}}
                >
                    {validCandidates.map((candidate) => (
                        <option key={candidate.path} value={candidate.path} title={candidate.path}>
                            {candidate.name} — {candidate.path}
                        </option>
                    ))}
                    {invalidCandidates.length > 0 && validCandidates.length > 0 && (
                        <option disabled>— invalid —</option>
                    )}
                    {invalidCandidates.map((candidate) => (
                        <option
                            key={candidate.path}
                            value={candidate.path}
                            disabled
                            title={candidate.error || t('invalid')}
                        >
                            {candidate.name} — {candidate.error || 'not found'}
                        </option>
                    ))}
                </select>
            </div>

            {/* Browse + Refresh */}
            <div className="flex flex-row" style={{gap: 4, marginBottom: 8}}>
                <button
                    className="button icon-button br-1"
                    onClick={browseForExecutable}
                    disabled={serverRunning || serverLoading}
                    title={t('browseForExecutable')}
                >
                    <span className="icon icon-size-20" style={{backgroundImage: 'var(--folder-open-icon, none)'}}/>
                </button>
                <button
                    className="button icon-button br-1"
                    onClick={refreshCandidates}
                    disabled={serverRunning || candidatesLoading}
                    title={t('refreshCandidates')}
                >
                    {candidatesLoading ? (
                        <span className="icon loader-icon icon-size-20"/>
                    ) : (
                        <span className="icon rotate-icon icon-size-20"/>
                    )}
                </button>
            </div>

            {/* Action buttons */}
            <div className="flex flex-row" style={{gap: 4}}>
                <button
                    className="button sm primary"
                    onClick={() => startServer()}
                    disabled={serverRunning || serverLoading}
                    style={{flex: 1, fontSize: '0.7rem'}}
                >
                    {serverLoading ? <span className="icon loader-icon icon-size-20"/> : null}
                    Launch
                </button>
                <button
                    className="button sm"
                    onClick={() => stopServer()}
                    disabled={!serverRunning || serverLoading}
                    style={{flex: 1, fontSize: '0.7rem', backgroundColor: 'var(--color-danger)', color: '#fff'}}
                >
                    {serverLoading ? <span className="icon loader-icon icon-size-20"/> : null}
                    Stop
                </button>
                <button
                    className="button sm secondary"
                    onClick={() => resetServer()}
                    disabled={!serverRunning || serverLoading}
                    style={{flex: 1, fontSize: '0.7rem'}}
                >
                    {serverLoading ? <span className="icon loader-icon icon-size-20"/> : null}
                    Reset
                </button>
            </div>

            {/* Running executable path */}
            {currentExePath && (
                <p
                    className="text sm text-gray"
                    title={currentExePath}
                    style={{
                        marginTop: 4,
                        display: 'block',
                        fontSize: '0.6rem',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                    }}
                >
                    {t('runningPath', {path: currentExePath})}
                </p>
            )}

            {/* Error */}
            {error && (
                <p
                    className="text sm text-error"
                    style={{marginTop: 4, display: 'block', fontSize: '0.65rem', wordBreak: 'break-word'}}
                >
                    {error}
                </p>
            )}
        </div>
    );
};
