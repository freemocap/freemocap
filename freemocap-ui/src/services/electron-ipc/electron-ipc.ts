// Check if running in Electron
import {electronIpcClient} from "@/services/electron-ipc/electron-ipc-client";
// Type-safe wrapper hook for React components
import {useMemo} from 'react';

export const isElectron = (): boolean => {
    return typeof window !== 'undefined' && !!window.electronAPI;
};

// Export the API client or null if not in Electron
export const electronIpc = isElectron() ? electronIpcClient : null;

export function useElectronIPC() {
    const api = useMemo(() => {
        if (!isElectron()) return null;
        return electronIpcClient;
    }, []);

    return {
        isElectron: isElectron(),
        api,
    };
}
