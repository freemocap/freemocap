// hooks/useFileSystem.ts
import { useCallback } from 'react';
import { useElectronIPC } from '@/services';

interface UseFileSystemReturn {
    isElectron: boolean;
    selectDirectory: () => Promise<string | null>;
    expandHomePath: (path: string) => Promise<string>;
}

export const useFileSystem = (): UseFileSystemReturn => {
    const { api, isElectron } = useElectronIPC();

    const selectDirectory = useCallback(async (): Promise<string | null> => {
        if (!isElectron || !api) {
            throw new Error('Directory selection is only available in the desktop app');
        }

        const result = await api.fileSystem.selectDirectory.mutate();
        return result;
    }, [isElectron, api]);

    const expandHomePath = useCallback(async (path: string): Promise<string> => {
        if (!path.includes('~')) {
            return path;
        }

        if (!isElectron || !api) {
            throw new Error('Path expansion requires Electron environment');
        }

        const home = await api.fileSystem.getHomeDirectory.query();
        return path.replace(/^~(\/|\\)?/, home ? `${home}$1` : '');
    }, [isElectron, api]);

    return {
        isElectron,
        selectDirectory,
        expandHomePath,
    };
};
