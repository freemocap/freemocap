import {useEffect, useRef} from 'react';
import {useElectronIPC} from '@/services/electron-ipc/electron-ipc';
import {useAppDispatch, useAppSelector} from '@/store';
import {recordingDirectoryChanged} from '@/store/slices/recording';
import {activeRecordingBaseDirectoryChanged} from '@/store/slices/active-recording';
import {recordingsDirFromBaseFolder} from '@/utils/dataFolder';

/**
 * On startup, resolve the base data folder from the Electron main process and seed the recording
 * directories with `<baseFolder>/recordings`. Only fills in directories the user has not already
 * chosen (persisted values are left untouched). Runs once per app launch.
 */
export function useHydrateDataFolder(): void {
    const {isElectron, api} = useElectronIPC();
    const dispatch = useAppDispatch();
    const recordingDirectory = useAppSelector((s) => s.recording.recordingDirectory);
    const activeBaseDirectory = useAppSelector((s) => s.activeRecording.baseDirectory);
    const hasRun = useRef(false);

    useEffect(() => {
        if (hasRun.current || !isElectron || !api) return;
        hasRun.current = true;

        let cancelled = false;
        (async () => {
            try {
                const baseFolder = await api.fileSystem.getBaseDataFolder.query();
                if (cancelled || !baseFolder) return;
                const recordingsDir = recordingsDirFromBaseFolder(baseFolder);
                if (!recordingDirectory) dispatch(recordingDirectoryChanged(recordingsDir));
                if (!activeBaseDirectory) dispatch(activeRecordingBaseDirectoryChanged(recordingsDir));
            } catch (err) {
                console.error('Failed to hydrate data folder from base folder:', err);
            }
        })();

        return () => {
            cancelled = true;
        };
    }, [isElectron, api, dispatch, recordingDirectory, activeBaseDirectory]);
}
