
import { contextBridge, ipcRenderer } from 'electron';

// Expose a simple tRPC bridge
contextBridge.exposeInMainWorld('electronAPI', {
    invoke: (path: string, input?: any) =>
        ipcRenderer.invoke('trpc', { path, input })
});
