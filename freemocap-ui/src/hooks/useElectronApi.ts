// src/hooks/useElectronAPI.ts
import {useEffect, useMemo, useState} from 'react';
import {electronIpcClient, isElectron} from "@/services";
import {serverUrls} from "@/hooks/server-urls";

interface UseElectronAPIReturn {
    isElectron: boolean;
    isLoading: boolean;
    api: typeof electronIpcClient | null;
    pythonServer: {
        start: (exePath?: string | null) => Promise<number>;
        stop: () => Promise<void>;
        isRunning: () => Promise<boolean>;
        getPort: () => Promise<number>;
        getStatus: () => Promise<{
            running: boolean;
            path: string | null;
            processInfo: any;
        }>;
    } | null;
    fileSystem: {
        openSelectDirectoryDialog: () => Promise<string | null>;
        selectExecutable: () => Promise<string | null>;
        openFolder: (path: string) => Promise<boolean>;
        getHomeDirectory: () => Promise<string>;
    } | null;
}

export function useElectronAPI(): UseElectronAPIReturn {
    const [isElectronEnv, setIsElectronEnv] = useState<boolean>(false);
    const [isLoading, setIsLoading] = useState<boolean>(true);

    useEffect(() => {
        const electronAvailable = isElectron();
        setIsElectronEnv(electronAvailable);
        setIsLoading(false);

        console.log('Electron environment detected:', electronAvailable);
    }, []);

    const pythonServer = useMemo(() => {
        if (!isElectronEnv) return null;

        return {
            /**
             * Start the Python server. Returns the port the server bound to.
             * Also updates the global serverUrls singleton so all HTTP/WS
             * connections automatically use the correct port.
             */
            start: async (exePath: string | null = null): Promise<number> => {
                const port: number = await electronIpcClient.pythonServer.start.mutate({ exePath });
                serverUrls.setPort(port);
                return port;
            },
            stop: async () => {
                await electronIpcClient.pythonServer.stop.mutate();
            },
            isRunning: async () => {
                return await electronIpcClient.pythonServer.isRunning.query();
            },
            getPort: async (): Promise<number> => {
                const port: number = await electronIpcClient.pythonServer.getPort.query();
                serverUrls.setPort(port);
                return port;
            },
            getStatus: async () => {
                const [running, path, processInfo] = await Promise.all([
                    electronIpcClient.pythonServer.isRunning.query(),
                    electronIpcClient.pythonServer.getExecutablePath.query(),
                    electronIpcClient.pythonServer.getProcessInfo.query(),
                ]);
                return { running, path, processInfo };
            },
        };
    }, [isElectronEnv]);

    const fileSystem = useMemo(() => {
        if (!isElectronEnv) return null;

        return {
            openSelectDirectoryDialog: async () => {
                try {
                    return await electronIpcClient.fileSystem.selectDirectory.mutate();
                } catch (error) {
                    console.error('Failed to select directory:', error);
                    return null;
                }
            },
            selectExecutable: async () => {
                try {
                    return await electronIpcClient.fileSystem.selectExecutableFile.mutate();
                } catch (error) {
                    console.error('Failed to select executable:', error);
                    return null;
                }
            },
            openFolder: async (path: string) => {
                try {
                    return await electronIpcClient.fileSystem.openFolder.mutate({ path });
                } catch (error) {
                    console.error('Failed to open folder:', error);
                    return false;
                }
            },
            getHomeDirectory: async () => {
                try {
                    return await electronIpcClient.fileSystem.getHomeDirectory.query();
                } catch (error) {
                    console.error('Failed to get home directory:', error);
                    return '';
                }
            },
        };
    }, [isElectronEnv]);

    return {
        isElectron: isElectronEnv,
        isLoading,
        api: isElectronEnv ? electronIpcClient : null,
        pythonServer,
        fileSystem,
    };
}

export const electronAPI = isElectron() ? electronIpcClient : null;