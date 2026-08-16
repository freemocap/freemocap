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
import {useTranslation} from 'react-i18next';

interface SettingsModalProps {
    open: boolean;
    onClose: () => void;
}

/**
 * Application settings, shown as a modal (mirrors the mocap-setup-modal pattern).
 * Exposes the base data folder (change / reset-to-default / open) and the usage-pings toggle.
 */
export const SettingsModal: React.FC<SettingsModalProps> = ({open, onClose}) => {
    const {t} = useTranslation();
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
        const selected = await api.fileSystem.selectDirectory.mutate({
            defaultPath: baseFolder || undefined,
        });
        if (!selected) return; // user canceled the picker
        setBusy(true);
        setStatus(t('settings.applyingDataFolder'));
        try {
            const {baseFolder: newBase, serverRestarted} = await api.fileSystem.setBaseDataFolder.mutate({path: selected});
            applyNewBaseFolder(newBase);
            setStatus(serverRestarted
                ? t('settings.folderUpdatedRestarted')
                : t('settings.folderSavedRestartRequired'));
        } catch (err) {
            console.error('Failed to set base data folder:', err);
            setStatus(t('settings.folderUpdateFailed'));
        } finally {
            setBusy(false);
        }
    }, [api, busy, isRecording, applyNewBaseFolder, t]);

    const handleReset = useCallback(async () => {
        if (!api || busy || isRecording) return;
        setBusy(true);
        setStatus(t('settings.resettingDataFolder'));
        try {
            const {baseFolder: newBase, serverRestarted} = await api.fileSystem.resetBaseDataFolder.mutate();
            applyNewBaseFolder(newBase);
            setStatus(serverRestarted
                ? t('settings.folderResetRestarted')
                : t('settings.folderResetRestartRequired'));
        } catch (err) {
            console.error('Failed to reset base data folder:', err);
            setStatus(t('settings.folderResetFailed'));
        } finally {
            setBusy(false);
        }
    }, [api, busy, isRecording, applyNewBaseFolder, t]);

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
                        <SubactionHeader text={t('settings.title')}/>
                        <IconButton icon="close-icon" onClick={onClose}/>
                    </div>

                    {/* Data folder */}
                    <div className="flex flex-col gap-2 bg-secondary p-2 br-1">
                        <SubactionHeader text={t('settings.dataFolder')} className="text-gray"/>
                        <p className="text sm text-gray">
                            {t('settings.dataFolderDescription')}
                        </p>
                        <p className="text sm text-white"
                           style={{fontFamily: 'monospace', wordBreak: 'break-all'}}>
                            {loaded ? (baseFolder || '—') : t('loading')}
                        </p>
                        <div className="flex flex-row gap-2 flex-wrap">
                            <ButtonSm
                                text={busy ? t('settings.applying') : t('settings.change')}
                                textColor="text-white"
                                buttonType=""
                                className="primary accent"
                                onClick={handleChangeFolder}
                                disabled={busy || isRecording}
                            />
                            <ButtonSm
                                text={t('settings.resetToDefault')}
                                buttonType="quaternary"
                                onClick={handleReset}
                                disabled={busy || isRecording}
                            />
                            <ButtonSm
                                text={t('openFolder')}
                                buttonType="quaternary"
                                onClick={handleOpenFolder}
                                disabled={!baseFolder}
                            />
                        </div>
                        {isRecording && (
                            <p className="text sm text-gray">{t('settings.stopRecordingToChangeFolder')}</p>
                        )}
                        {status && <p className="text sm text-gray">{status}</p>}
                        <p className="text sm text-darkgray">
                            {t('settings.changeFolderWarning')}
                        </p>
                    </div>

                    {/* Privacy */}
                    <div className="flex flex-col gap-1 bg-secondary p-2 br-1">
                        <SubactionHeader text={t('settings.privacy')} className="text-gray"/>
                        {loaded && (
                            <Checkbox
                                label={t('settings.telemetry')}
                                checked={telemetryEnabled}
                                onChange={(e) => handleTelemetryToggle(e.target.checked)}
                            />
                        )}
                    </div>

                    {/* Getting started */}
                    <div className="flex flex-col gap-2 bg-secondary p-2 br-1">
                        <SubactionHeader text={t('settings.gettingStarted')} className="text-gray"/>
                        <p className="text sm text-gray">{t('settings.replayTourDescription')}</p>
                        <div className="flex flex-row">
                            <ButtonSm
                                text={t('settings.replayTutorial')}
                                buttonType="quaternary"
                                onClick={handleReplayTour}
                            />
                        </div>
                    </div>

                    {/* Bottom actions */}
                    <div className="flex flex-row gap-2" style={{justifyContent: 'flex-end'}}>
                        <ButtonSm text={t('close')} buttonType="quaternary" onClick={onClose}/>
                    </div>
                </div>
            </div>
        </>
    );
};

export default SettingsModal;
