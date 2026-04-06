// electron/main/ipc.ts
import { ipcMain } from 'electron';
import { api } from './api';
import superjson from 'superjson';

export function setupIPC(): void {
  ipcMain.handle('trpc', async (_event, { path, input }) => {
    try {
      const caller = api.createCaller({});

      const pathParts = path.split('.');
      let current: any = caller;

      for (let i = 0; i < pathParts.length - 1; i++) {
        current = current[pathParts[i]];
        if (!current) {
          throw new Error(`Router not found: ${pathParts.slice(0, i + 1).join('.')}`);
        }
      }

      const procedureName = pathParts[pathParts.length - 1];
      const fn = current[procedureName];

      if (typeof fn !== 'function') {
        throw new Error(`Procedure not found: ${path}`);
      }

      const result = await fn(input);
      return superjson.serialize(result);
    } catch (error) {
      console.error(`IPC Error for ${path}:`, error);
      throw error;
    }
  });
}
