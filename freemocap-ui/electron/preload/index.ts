import { contextBridge, ipcRenderer } from 'electron';

contextBridge.exposeInMainWorld('electronAPI', {
    // tRPC bridge
    invoke: (path: string, input?: any) =>
        ipcRenderer.invoke('trpc', { path, input }),

    // Menu-triggered navigation: main process sends 'navigate' with a route string
    onNavigate: (callback: (route: string) => void) => {
        const handler = (_event: Electron.IpcRendererEvent, route: string) => callback(route);
        ipcRenderer.on('navigate', handler);
        // Return cleanup function
        return () => {
            ipcRenderer.removeListener('navigate', handler);
        };
    },
});
