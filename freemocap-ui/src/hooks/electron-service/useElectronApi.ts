// src/hooks/useElectronAPI.ts
import { useEffect, useState, useMemo } from 'react';
import {electronIpcClient, isElectron} from "@/hooks/electron-service/electron-ipc-client";

interface UseElectronAPIReturn {
    isElectron: boolean;
    isLoading: boolean;
    api: typeof electronIpcClient | null;
    // Helper methods for common operations
    pythonServer: {
        start: (exePath?: string | null) => Promise<void>;
        stop: () => Promise<void>;
        isRunning: () => Promise<boolean>;
        getStatus: () => Promise<{
            running: boolean;
            path: string | null;
            processInfo: any;
        }>;
    } | null;
    fileSystem: {
        selectDirectory: () => Promise<string | null>;
        selectExecutable: () => Promise<string | null>;
        openFolder: (path: string) => Promise<boolean>;
        getHomeDirectory: () => Promise<string>;
    } | null;
}

export function useElectronAPI(): UseElectronAPIReturn {
    const [isElectronEnv, setIsElectronEnv] = useState<boolean>(false);
    const [isLoading, setIsLoading] = useState<boolean>(true);

    useEffect(() => {
        // Check if we're in Electron environment
        const electronAvailable = isElectron();
        setIsElectronEnv(electronAvailable);
        setIsLoading(false);

        // Log the environment for debugging
        console.log('Electron environment detected:', electronAvailable);
    }, []);

    // Create memoized helper objects
    const pythonServer = useMemo(() => {
        if (!isElectronEnv) return null;

        return {
            start: async (exePath: string | null = null) => {
                try {
                    await electronIpcClient.pythonServer.start.mutate({ exePath });
                } catch (error) {
                    console.error('Failed to start Python server:', error);
                    throw error;
                }
            },
            stop: async () => {
                try {
                    await electronIpcClient.pythonServer.stop.mutate();
                } catch (error) {
                    console.error('Failed to stop Python server:', error);
                    throw error;
                }
            },
            isRunning: async () => {
                try {
                    return await electronIpcClient.pythonServer.isRunning.query();
                } catch (error) {
                    console.error('Failed to check Python server status:', error);
                    return false;
                }
            },
            getStatus: async () => {
                try {
                    const [running, path, processInfo] = await Promise.all([
                        electronIpcClient.pythonServer.isRunning.query(),
                        electronIpcClient.pythonServer.getExecutablePath.query(),
                        electronIpcClient.pythonServer.getProcessInfo.query(),
                    ]);
                    return { running, path, processInfo };
                } catch (error) {
                    console.error('Failed to get Python server status:', error);
                    return { running: false, path: null, processInfo: null };
                }
            },
        };
    }, [isElectronEnv]);

    const fileSystem = useMemo(() => {
        if (!isElectronEnv) return null;

        return {
            selectDirectory: async () => {
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

// Export a singleton instance for use outside of React components
export const electronAPI = isElectron() ? electronIpcClient : null;
