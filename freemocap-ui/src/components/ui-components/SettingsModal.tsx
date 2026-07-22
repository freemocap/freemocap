import React, {useCallback, useEffect, useState} from 'react';
import {useElectronIPC} from '@/services';
import {useAppDispatch, useAppSelector} from '@/store';
import {recordingDirectoryChanged, selectIsAnyRecording} from '@/store/slices/recording';
import {activeRecordingBaseDirectoryChanged} from '@/store/slices/active-recording';
import {recordingsDirFromBaseFolder} from '@/utils/dataFolder';
import ButtonSm from '@/components/ui-components/ButtonSm';
import IconButton from '@/components/ui-components/IconButton';
import Checkbox from '@/components/ui-components/Checkbox';
import SubactionHeader from '@/components/ui-components/SubactionHeader';
import {useTutorial} from '@/components/tutorial';

interface SettingsModalProps {
    open: boolean;
    onClose: () => void;
}

/**
 * Application settings, shown as a modal (mirrors the mocap-setup-modal pattern).
 * Exposes the base data folder (change / reset-to-default / open) and the usage-pings toggle.
 */
export const SettingsModal: React.FC<SettingsModalProps> = ({open, onClose}) => {
    const {isElectron, api} = useElectronIPC();
    const dispatch = useAppDispatch();
    const isRecording = useAppSelector(selectIsAnyRecording);
    const {startTour} = useTutorial();

    const [baseFolder, setBaseFolder] = useState<string>('');
    const [telemetryEnabled, setTelemetryEnabled] = useState<boolean>(true);
    const [loaded, setLoaded] = useState<boolean>(false);
    const [busy, setBusy] = useState<boolean>(false);
    const [status, setStatus] = useState<string | null>(null);

    // Load current values whenever the modal opens
    useEffect(() => {
        if (!open) return;
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
    }, [open, isElectron, api]);

    // Close on Escape
    useEffect(() => {
        if (!open) return;
        const onKeyDown = (e: KeyboardEvent) => {
            if (e.key === 'Escape') onClose();
        };
        window.addEventListener('keydown', onKeyDown);
        return () => window.removeEventListener('keydown', onKeyDown);
    }, [open, onClose]);

    const applyNewBaseFolder = useCallback((newBase: string) => {
        setBaseFolder(newBase);
        const recordingsDir = recordingsDirFromBaseFolder(newBase);
        dispatch(recordingDirectoryChanged(recordingsDir));
        dispatch(activeRecordingBaseDirectoryChanged(recordingsDir));
    }, [dispatch]);

    const handleChangeFolder = useCallback(async () => {
        if (!api || busy || isRecording) return;
        const selected = await api.fileSystem.selectDirectory.mutate();
        if (!selected) return; // user canceled the picker
        setBusy(true);
        setStatus('Applying data folder…');
        try {
            const {baseFolder: newBase, serverRestarted} = await api.fileSystem.setBaseDataFolder.mutate({path: selected});
            applyNewBaseFolder(newBase);
            setStatus(serverRestarted
                ? 'Data folder updated and server restarted. Existing recordings were not moved.'
                : 'Data folder saved. Restart the FreeMoCap server to apply it. Existing recordings were not moved.');
        } catch (err) {
            console.error('Failed to set base data folder:', err);
            setStatus('Failed to update the data folder. See logs for details.');
        } finally {
            setBusy(false);
        }
    }, [api, busy, isRecording, applyNewBaseFolder]);

    const handleReset = useCallback(async () => {
        if (!api || busy || isRecording) return;
        setBusy(true);
        setStatus('Resetting data folder…');
        try {
            const {baseFolder: newBase, serverRestarted} = await api.fileSystem.resetBaseDataFolder.mutate();
            applyNewBaseFolder(newBase);
            setStatus(serverRestarted
                ? 'Reset to the default data folder and restarted the server.'
                : 'Reset to the default data folder. Restart the FreeMoCap server to apply it.');
        } catch (err) {
            console.error('Failed to reset base data folder:', err);
            setStatus('Failed to reset the data folder. See logs for details.');
        } finally {
            setBusy(false);
        }
    }, [api, busy, isRecording, applyNewBaseFolder]);

    const handleOpenFolder = useCallback(async () => {
        if (!api || !baseFolder) return;
        await api.fileSystem.openFolder.mutate({path: baseFolder});
    }, [api, baseFolder]);

    const handleReplayTour = useCallback(() => {
        startTour('getting-started');
        onClose();
    }, [startTour, onClose]);

    const handleTelemetryToggle = useCallback(async (checked: boolean) => {
        setTelemetryEnabled(checked);
        try {
            if (api) await api.telemetry.setEnabled.mutate({enabled: checked});
        } catch (err) {
            console.error('Failed to save telemetry preference:', err);
        }
    }, [api]);

    if (!open) return null;

    return (
        <>
            {/* Backdrop */}
            <div className="pos-fixed inset-0 bg-surface-overlay z-10" onClick={onClose}/>

            {/* Modal */}
            <div className="settings-modal bg-primary border-1 border-black pos-fixed elevated-sharp p-1 flex flex-col br-2">
                <div className="flex flex-col p-2 gap-2 bg-middark br-1">
                    <div className="flex justify-content-space-between items-center">
                        <SubactionHeader text="Settings"/>
                        <IconButton icon="close-icon" onClick={onClose}/>
                    </div>

                    {/* Data folder */}
                    <div className="flex flex-col gap-2 bg-secondary p-2 br-1">
                        <SubactionHeader text="Data folder" className="text-gray"/>
                        <p className="text sm text-gray">
                            Where FreeMoCap stores recordings, calibrations, and logs.
                        </p>
                        <p className="text sm text-white"
                           style={{fontFamily: 'monospace', wordBreak: 'break-all'}}>
                            {loaded ? (baseFolder || '—') : 'Loading…'}
                        </p>
                        <div className="flex flex-row gap-2 flex-wrap">
                            <ButtonSm
                                text={busy ? 'Applying…' : 'Change…'}
                                textColor="text-white"
                                buttonType=""
                                className="primary accent"
                                onClick={handleChangeFolder}
                                disabled={busy || isRecording}
                            />
                            <ButtonSm
                                text="Reset to default"
                                buttonType="quaternary"
                                onClick={handleReset}
                                disabled={busy || isRecording}
                            />
                            <ButtonSm
                                text="Open folder"
                                buttonType="quaternary"
                                onClick={handleOpenFolder}
                                disabled={!baseFolder}
                            />
                        </div>
                        {isRecording && (
                            <p className="text sm text-gray">Stop the active recording to change the data folder.</p>
                        )}
                        {status && <p className="text sm text-gray">{status}</p>}
                        <p className="text sm text-darkgray">
                            Changing the folder restarts the server. Existing recordings are not moved.
                        </p>
                    </div>

                    {/* Privacy */}
                    <div className="flex flex-col gap-1 bg-secondary p-2 br-1">
                        <SubactionHeader text="Privacy" className="text-gray"/>
                        {loaded && (
                            <Checkbox
                                label="Send anonymous usage pings to help improve FreeMoCap"
                                checked={telemetryEnabled}
                                onChange={(e) => handleTelemetryToggle(e.target.checked)}
                            />
                        )}
                    </div>

                    {/* Getting started */}
                    <div className="flex flex-col gap-2 bg-secondary p-2 br-1">
                        <SubactionHeader text="Getting started" className="text-gray"/>
                        <p className="text sm text-gray">Replay the guided tour of the basics.</p>
                        <div className="flex flex-row">
                            <ButtonSm
                                text="Replay tutorial"
                                buttonType="quaternary"
                                onClick={handleReplayTour}
                            />
                        </div>
                    </div>

                    {/* Bottom actions */}
                    <div className="flex flex-row gap-2" style={{justifyContent: 'flex-end'}}>
                        <ButtonSm text="Close" buttonType="quaternary" onClick={onClose}/>
                    </div>
                </div>
            </div>
        </>
    );
};

export default SettingsModal;
