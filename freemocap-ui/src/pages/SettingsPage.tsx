import React, {useCallback, useEffect, useState} from 'react';
import {useElectronIPC} from '@/services';
import {useAppDispatch, useAppSelector} from '@/store';
import {recordingDirectoryChanged, selectIsAnyRecording} from '@/store/slices/recording';
import {activeRecordingBaseDirectoryChanged} from '@/store/slices/active-recording';
import {recordingsDirFromBaseFolder} from '@/utils/dataFolder';
import ButtonSm from '@/components/ui-components/ButtonSm';
import Checkbox from '@/components/ui-components/Checkbox';

/**
 * Application settings. Currently exposes:
 *  - the base data folder (where FreeMoCap stores recordings, calibrations, logs, etc.)
 *  - the anonymous-usage-pings opt-in toggle
 */
export const SettingsPage: React.FC = () => {
    const {isElectron, api} = useElectronIPC();
    const dispatch = useAppDispatch();
    const isRecording = useAppSelector(selectIsAnyRecording);

    const [baseFolder, setBaseFolder] = useState<string>('');
    const [telemetryEnabled, setTelemetryEnabled] = useState<boolean>(true);
    const [loaded, setLoaded] = useState<boolean>(false);
    const [busy, setBusy] = useState<boolean>(false);
    const [status, setStatus] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;
        (async () => {
            if (!isElectron || !api) {
                setLoaded(true);
                return;
            }
            try {
                const [base, telemetry] = await Promise.all([
                    api.fileSystem.getBaseDataFolder.query(),
                    api.telemetry.getEnabled.query(),
                ]);
                if (cancelled) return;
                setBaseFolder(base);
                setTelemetryEnabled(telemetry);
            } catch (err) {
                console.error('Failed to load settings:', err);
            } finally {
                if (!cancelled) setLoaded(true);
            }
        })();
        return () => {
            cancelled = true;
        };
    }, [isElectron, api]);

    const handleChangeFolder = useCallback(async () => {
        if (!api || busy || isRecording) return;
        const selected = await api.fileSystem.selectDirectory.mutate();
        if (!selected) return; // user canceled the picker

        setBusy(true);
        setStatus('Applying new data folder and restarting the server…');
        try {
            const newBase = await api.fileSystem.setBaseDataFolder.mutate({path: selected});
            setBaseFolder(newBase);
            const recordingsDir = recordingsDirFromBaseFolder(newBase);
            dispatch(recordingDirectoryChanged(recordingsDir));
            dispatch(activeRecordingBaseDirectoryChanged(recordingsDir));
            setStatus('Data folder updated. Existing recordings were not moved to the new location.');
        } catch (err) {
            console.error('Failed to set base data folder:', err);
            setStatus('Failed to update the data folder. See logs for details.');
        } finally {
            setBusy(false);
        }
    }, [api, busy, isRecording, dispatch]);

    const handleOpenFolder = useCallback(async () => {
        if (!api || !baseFolder) return;
        await api.fileSystem.openFolder.mutate({path: baseFolder});
    }, [api, baseFolder]);

    const handleTelemetryToggle = useCallback(async (checked: boolean) => {
        setTelemetryEnabled(checked);
        try {
            if (api) await api.telemetry.setEnabled.mutate({enabled: checked});
        } catch (err) {
            console.error('Failed to save telemetry preference:', err);
        }
    }, [api]);

    if (!isElectron) {
        return (
            <div className="flex flex-col flex-1 h-full p-3 gap-2 overflow-auto">
                <h1 className="text-white">Settings</h1>
                <p className="text-gray text md">Settings are only available in the desktop app.</p>
            </div>
        );
    }

    return (
        <div className="flex flex-col flex-1 h-full p-3 gap-3 overflow-auto">
            <h1 className="text-white">Settings</h1>

            {/* Data folder */}
            <section className="flex flex-col gap-2 br-1 bg-middark p-3">
                <h2 className="text-white">Data folder</h2>
                <p className="text-gray text md">
                    Where FreeMoCap stores recordings, calibrations, logs, and settings.
                </p>
                <div className="flex flex-row items-center gap-2 flex-wrap">
                    <p className="text-white text md" style={{fontFamily: 'monospace', wordBreak: 'break-all'}}>
                        {loaded ? (baseFolder || '—') : 'Loading…'}
                    </p>
                </div>
                <div className="flex flex-row gap-2 flex-wrap">
                    <ButtonSm
                        text={busy ? 'Applying…' : 'Change…'}
                        onClick={handleChangeFolder}
                        disabled={busy || isRecording}
                        title={isRecording ? 'Stop recording before changing the data folder' : undefined}
                    />
                    <ButtonSm
                        text="Open folder"
                        onClick={handleOpenFolder}
                        disabled={!baseFolder}
                    />
                </div>
                {isRecording && (
                    <p className="text-gray text sm">Stop the active recording to change the data folder.</p>
                )}
                {status && <p className="text-gray text sm">{status}</p>}
                <p className="text-gray text sm">
                    Changing the folder restarts the FreeMoCap server. Existing recordings are not moved.
                </p>
            </section>

            {/* Privacy */}
            <section className="flex flex-col gap-2 br-1 bg-middark p-3">
                <h2 className="text-white">Privacy</h2>
                {loaded && (
                    <Checkbox
                        label="Send anonymous usage pings to help improve FreeMoCap"
                        checked={telemetryEnabled}
                        onChange={(e) => handleTelemetryToggle(e.target.checked)}
                    />
                )}
            </section>
        </div>
    );
};

export default SettingsPage;
