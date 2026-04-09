import React, {createContext, useCallback, useEffect, useState} from 'react';
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
}

export const AutoUpdateContext = createContext<AutoUpdateState | null>(null);

export const AutoUpdateProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const { isElectron, api } = useElectronIPC();
    const [status, setStatus] = useState<UpdateStatus>('idle');
    const [version, setVersion] = useState<string | null>(null);
    const [progress, setProgress] = useState(0);
    const [errorMessage, setErrorMessage] = useState<string | null>(null);

    const checkForUpdate = useCallback(async () => {
        if (!isElectron || !api) return;

        setStatus('checking');
        setErrorMessage(null);
        try {
            const result = await api.app.checkForUpdate.mutate();
            if (result.available) {
                setStatus('available');
                setVersion(result.version ?? null);
            } else {
                setStatus('up-to-date');
            }
        } catch (err) {
            setStatus('error');
            setErrorMessage(err instanceof Error ? err.message : String(err));
        }
    }, [isElectron, api]);

    const installUpdate = useCallback(() => {
        if (!isElectron || !api) return;
        api.app.installUpdate.mutate();
    }, [isElectron, api]);

    // Listen for IPC update events from the main process (UpdateHandler)
    useEffect(() => {
        if (!isElectron || !window.electronAPI) return;

        const cleanups = [
            window.electronAPI.onUpdateAvailable((info) => {
                setStatus('available');
                setVersion(info.version);
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
    }, [isElectron]);

    // Listen for menu-triggered check-for-updates
    useEffect(() => {
        const handler = () => checkForUpdate();
        window.addEventListener('check-for-updates', handler);
        return () => window.removeEventListener('check-for-updates', handler);
    }, [checkForUpdate]);

    return (
        <AutoUpdateContext.Provider value={{ status, version, progress, errorMessage, checkForUpdate, installUpdate }}>
            {children}
        </AutoUpdateContext.Provider>
    );
};
