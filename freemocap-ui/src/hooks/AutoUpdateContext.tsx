import React, {createContext, useCallback, useEffect, useRef, useState} from 'react';
import {useElectronIPC} from '@/services';

export type UpdateStatus =
    | 'idle'
    | 'checking'
    | 'available'
    | 'downloading'
    | 'ready'
    | 'error'
    | 'up-to-date';

export interface AutoUpdateState {
    status: UpdateStatus;
    version: string | null;
    progress: number;
    errorMessage: string | null;
    checkForUpdate: () => void;
    installUpdate: () => void;
    dismissUpdate: () => void;
}

export const AutoUpdateContext = createContext<AutoUpdateState | null>(null);

const DISMISSED_UPDATE_VERSION_KEY = 'freemocap.dismissedUpdateVersion';

export const AutoUpdateProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const { isElectron, api } = useElectronIPC();
    const [status, setStatus] = useState<UpdateStatus>('idle');
    const [version, setVersion] = useState<string | null>(null);
    const [progress, setProgress] = useState(0);
    const [errorMessage, setErrorMessage] = useState<string | null>(null);
    const hasCheckedOnStartup = useRef(false);

    const isVersionDismissed = useCallback((candidateVersion: string | null | undefined) => {
        if (!candidateVersion) return false;
        return window.localStorage.getItem(DISMISSED_UPDATE_VERSION_KEY) === candidateVersion;
    }, []);

    const showAvailableUpdate = useCallback((
        candidateVersion: string | null | undefined,
        respectDismissal: boolean,
    ) => {
        const nextVersion = candidateVersion ?? null;

        if (respectDismissal && isVersionDismissed(nextVersion)) {
            setVersion(nextVersion);
            setStatus('idle');
            return;
        }

        setVersion(nextVersion);
        setStatus('available');
    }, [isVersionDismissed]);

    const runUpdateCheck = useCallback(async (
        respectDismissal: boolean,
        showUpToDate: boolean,
        showErrors: boolean,
    ) => {
        if (!isElectron || !api) return;

        setStatus('checking');
        setErrorMessage(null);

        try {
            // // TEMP ERROR MOCK:
            // throw new Error('Simulated update check failure');

            // TEMP TEST MOCK:
            const result = {

                available: false,
                version: '100.0.0-test',
                currentVersion: '2.0.0-alpha.25',
            };

            // REAL VERSION:
            // const result = await api.app.checkForUpdate.mutate();

            if (result.available) {
                showAvailableUpdate(result.version, respectDismissal);
            } else if (showUpToDate) {
                setVersion(result.currentVersion ?? null);
                setStatus('up-to-date');

                window.setTimeout(() => {
                    setStatus('idle');
                }, 4000);
            } else {
                setStatus('idle');
            }
        } catch (err) {
            if (showErrors) {
                setStatus('error');
                setErrorMessage(err instanceof Error ? err.message : String(err));
                window.setTimeout(() => {
                    setStatus('idle');
                }, 4000);

            } else {
                setStatus('idle');
            }
        }
    }, [isElectron, api, showAvailableUpdate]);

    // Manual checks always report the result.
    const checkForUpdate = useCallback(() => {
        void runUpdateCheck(false, true, true);
    }, [runUpdateCheck]);

    const installUpdate = useCallback(() => {
        if (!isElectron || !api) return;
        api.app.installUpdate.mutate();
    }, [isElectron, api]);

    const dismissUpdate = useCallback(() => {
        if (version) {
            window.localStorage.setItem(DISMISSED_UPDATE_VERSION_KEY, version);
        }
        setStatus('idle');
    }, [version]);

    // Listen for updater events from Electron.
    useEffect(() => {
        if (!isElectron || !window.electronAPI) return;

        const cleanups = [
            window.electronAPI.onUpdateAvailable((info) => {
                showAvailableUpdate(info.version, true);
            }),
            window.electronAPI.onDownloadProgress((prog) => {
                setStatus('downloading');
                setProgress(prog.percent);
            }),
            window.electronAPI.onUpdateDownloaded((info) => {
                setStatus('ready');
                setVersion(info.version);
            }),
            window.electronAPI.onUpdateError((error) => {
                setStatus('error');
                setErrorMessage(error.message);
            }),
        ];

        return () => {
            cleanups.forEach((cleanup) => cleanup());
        };
    }, [isElectron, showAvailableUpdate]);

    // Startup check:
    // - show update if one exists
    // - show nothing if already up to date
    // - show nothing if the check fails
    useEffect(() => {
        if (!isElectron || !api || hasCheckedOnStartup.current) return;

        hasCheckedOnStartup.current = true;
        void runUpdateCheck(true, false, false);
    }, [isElectron, api, runUpdateCheck]);

    // Manual Help > Check for Updates.
    useEffect(() => {
        const handler = () => checkForUpdate();
        window.addEventListener('check-for-updates', handler);

        return () => {
            window.removeEventListener('check-for-updates', handler);
        };
    }, [checkForUpdate]);

    return (
        <AutoUpdateContext.Provider
            value={{
                status,
                version,
                progress,
                errorMessage,
                checkForUpdate,
                installUpdate,
                dismissUpdate,
            }}
        >
            {children}
        </AutoUpdateContext.Provider>
    );
};