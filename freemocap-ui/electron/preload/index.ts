import {contextBridge, ipcRenderer} from 'electron';

// Expose a simple tRPC bridge + menu action listener + menu label updater
contextBridge.exposeInMainWorld('electronAPI', {
    invoke: (path: string, input?: unknown) =>
        ipcRenderer.invoke('trpc', { path, input }),

    onMenuAction: (callback: (action: string) => void) => {
        const handler = (_event: Electron.IpcRendererEvent, action: string) => {
            callback(action);
        };
        ipcRenderer.on('menu-action', handler);

        // Return a cleanup function to remove the listener
        return () => {
            ipcRenderer.removeListener('menu-action', handler);
        };
    },

    sendMenuLabels: (params: Record<string, unknown>) => {
        ipcRenderer.send('update-menu-labels', params);
    },

    // Auto-update event listeners
    onUpdateAvailable: (callback: (info: { version: string; currentVersion: string }) => void) => {
        const handler = (_event: Electron.IpcRendererEvent, info: { version: string; currentVersion: string }) => callback(info);
        ipcRenderer.on('update-available', handler);
        return () => { ipcRenderer.removeListener('update-available', handler); };
    },

    onDownloadProgress: (callback: (progress: { percent: number; bytesPerSecond: number; transferred: number; total: number }) => void) => {
        const handler = (_event: Electron.IpcRendererEvent, progress: any) => callback(progress);
        ipcRenderer.on('download-progress', handler);
        return () => { ipcRenderer.removeListener('download-progress', handler); };
    },

    onUpdateDownloaded: (callback: (info: { version: string }) => void) => {
        const handler = (_event: Electron.IpcRendererEvent, info: { version: string }) => callback(info);
        ipcRenderer.on('update-downloaded', handler);
        return () => { ipcRenderer.removeListener('update-downloaded', handler); };
    },

    onUpdateError: (callback: (error: { message: string }) => void) => {
        const handler = (_event: Electron.IpcRendererEvent, error: { message: string }) => callback(error);
        ipcRenderer.on('update-error', handler);
        return () => { ipcRenderer.removeListener('update-error', handler); };
    },
});
