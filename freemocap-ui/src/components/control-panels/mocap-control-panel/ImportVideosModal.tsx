import React, {useCallback, useEffect, useState} from 'react';
import {useElectronIPC} from '@/services';
import {useAppDispatch, useAppSelector} from '@/store';
import {
    checkVideoSync,
    getSyncResult,
    importVideos,
    startVideoSync,
    SyncMethod,
    SyncResult,
    VideoSyncInfo,
} from '@/store/slices/mocap';
import {selectActivePipelines} from '@/store/slices/pipelines';
import {activeRecordingSet, splitParentAndName} from '@/store/slices/active-recording/active-recording-slice';
import {useFfmpeg} from '@/hooks/useFfmpeg';
import ButtonSm from '@/components/ui-components/ButtonSm';
import SubactionHeader from '@/components/ui-components/SubactionHeader';
import Checkbox from '@/components/ui-components/Checkbox';

interface ImportVideosModalProps {
    open: boolean;
    onClose: () => void;
    onImported?: (result: { recordingPath: string; recordingName: string }) => void;
    /** Suffix appended to the auto-generated recording name. Defaults to "imported". */
    defaultNameTag?: string;
}

// Mirrors the backend's `default_recording_name` (freemocap/system/default_paths.py) —
// a filename-friendly ISO-8601 timestamp with GMT offset, tagged with the given suffix.
function generateDefaultRecordingName(tag: string): string {
    const now = new Date();
    const pad = (n: number) => String(n).padStart(2, '0');
    const isoTimestamp = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}` +
        `T${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;

    const offsetHours = -now.getTimezoneOffset() / 60;
    const gmtOffset = `${offsetHours >= 0 ? '+' : '-'}${Math.abs(offsetHours)}`;

    return `${isoTimestamp}_gmt${gmtOffset}`.replace(/:/g, '_') + `_${tag}`;
}

export const ImportVideosModal: React.FC<ImportVideosModalProps> = ({open, onClose, onImported, defaultNameTag = 'imported'}) => {
    const {isElectron, api} = useElectronIPC();
    const dispatch = useAppDispatch();

    const [videoPaths, setVideoPaths] = useState<string[]>([]);
    const [recordingName, setRecordingName] = useState('');
    const [defaultRecordingName, setDefaultRecordingName] = useState('');
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [checkingSync, setCheckingSync] = useState(false);
    const [syncCheck, setSyncCheck] = useState<{ synchronized: boolean; videos: VideoSyncInfo[]; detail: string | null } | null>(null);

    const [syncEnabled, setSyncEnabled] = useState(false);
    const [syncMethod, setSyncMethod] = useState<SyncMethod>(SyncMethod.AUDIO);
    const [brightnessRatioThreshold, setBrightnessRatioThreshold] = useState('1000');
    const [syncing, setSyncing] = useState(false);
    const [syncJobId, setSyncJobId] = useState<string | null>(null);
    const [syncError, setSyncError] = useState<string | null>(null);

    const ffmpeg = useFfmpeg();
    const ffmpegMissing = ffmpeg.found === false;

    const activePipelines = useAppSelector(selectActivePipelines);
    const syncProgress = syncJobId ? activePipelines[syncJobId] : undefined;

    useEffect(() => {
        if (!open) return;
        setVideoPaths([]);
        setRecordingName('');
        setDefaultRecordingName(generateDefaultRecordingName(defaultNameTag));
        setBusy(false);
        setError(null);
        setCheckingSync(false);
        setSyncCheck(null);
    }, [open, defaultNameTag]);

    useEffect(() => {
        if (!open) return;
        if (videoPaths.length === 0) {
            setSyncCheck(null);
            return;
        }
        let cancelled = false;
        setCheckingSync(true);
        dispatch(checkVideoSync({videoPaths}))
            .unwrap()
            .then((result) => {
                if (!cancelled) {
                    setSyncCheck(result);
                    if (!result.synchronized && ffmpeg.found !== false) setSyncEnabled(true);
                }
            })
            .catch((err) => {
                if (!cancelled) {
                    setSyncCheck(null);
                    setError(typeof err === 'string' ? err : 'Failed to check video synchronization');
                }
            })
            .finally(() => {
                if (!cancelled) setCheckingSync(false);
            });
        return () => {
            cancelled = true;
        };
    }, [open, videoPaths, dispatch]);

    // A new file selection invalidates any previous synchronize run.
    useEffect(() => {
        setSyncEnabled(false);
        setSyncJobId(null);
        setSyncError(null);
        setSyncing(false);
    }, [videoPaths]);

    useEffect(() => {
        if (!open) return;
        const onKeyDown = (e: KeyboardEvent) => {
            if (e.key === 'Escape') onClose();
        };
        window.addEventListener('keydown', onKeyDown);
        return () => window.removeEventListener('keydown', onKeyDown);
    }, [open, onClose]);

    const handleChooseFiles = useCallback(async () => {
        if (!isElectron || !api) return;
        try {
            const result: string[] = await api.fileSystem.selectVideoFiles.mutate();
            if (result.length > 0) {
                setVideoPaths(result);
                setError(null);
            }
        } catch (err) {
            console.error('Failed to select video files:', err);
            setError('Failed to select video files');
        }
    }, [isElectron, api]);

    const handleClearSelection = useCallback(() => {
        setVideoPaths([]);
        setSyncCheck(null);
        setError(null);
    }, []);

    // Poll the sync job until it finishes (HTTP 425 while running, 200 once done).
    const pollSyncResult = useCallback(async (jobId: string): Promise<SyncResult> => {
        for (;;) {
            const action = await dispatch(getSyncResult({jobId}));
            if (getSyncResult.fulfilled.match(action)) {
                if (action.payload.status === 'done') return action.payload.result;
            } else {
                throw new Error(typeof action.payload === 'string' ? action.payload : 'Synchronization failed');
            }
            await new Promise((resolve) => setTimeout(resolve, 500));
        }
    }, [dispatch]);

    const handleImport = useCallback(async () => {
        if (videoPaths.length === 0 || busy) return;
        setBusy(true);
        setError(null);
        setSyncError(null);
        try {
            let jobId: string | undefined;
            if (syncEnabled) {
                setSyncing(true);
                const started = await dispatch(startVideoSync({
                    videoPaths,
                    method: syncMethod,
                    brightnessRatioThreshold: syncMethod === SyncMethod.BRIGHTNESS
                        ? Number(brightnessRatioThreshold)
                        : undefined,
                })).unwrap();
                setSyncJobId(started.jobId);
                await pollSyncResult(started.jobId);
                jobId = started.jobId;
                setSyncing(false);
            }

            const result = await dispatch(importVideos({
                videoPaths,
                recordingName: recordingName.trim() || defaultRecordingName,
                syncJobId: jobId,
            })).unwrap();

            const parsed = splitParentAndName(result.recordingPath);
            dispatch(activeRecordingSet({
                recordingName: result.recordingName,
                baseDirectory: parsed?.baseDirectory,
                origin: 'browsed',
            }));
            onImported?.(result);
            onClose();
        } catch (err) {
            setError(err instanceof Error ? err.message : typeof err === 'string' ? err : 'Failed to import videos');
            setSyncing(false);
        } finally {
            setBusy(false);
        }
    }, [videoPaths, recordingName, defaultRecordingName, busy, syncEnabled, syncMethod, brightnessRatioThreshold, pollSyncResult, dispatch, onClose, onImported]);

    const importDisabledReason = busy
        ? (syncing ? 'Synchronizing…' : 'Importing…')
        : videoPaths.length === 0
            ? 'Select video files to import'
            : checkingSync
                ? 'Checking synchronization…'
                : (syncCheck && !syncCheck.synchronized && (!syncEnabled || ffmpegMissing))
                    ? (ffmpegMissing ? 'Selected videos are not synchronized and ffmpeg is required to synchronize them' : 'Selected videos are not synchronized')
                    : null;

    if (!open) return null;

    return (
        <>
            {/* Backdrop */}
            <div className="pos-fixed inset-0 bg-surface-overlay z-10" onClick={onClose}/>

            {/* Modal */}
            <div className="settings-modal bg-primary border-1 border-black pos-fixed elevated-sharp p-1 flex flex-col br-2">
                <div className="flex flex-col p-2 gap-2 bg-middark br-1">
                    <div className="flex justify-content-space-between items-center">
                        <SubactionHeader text="Import Videos"/>
                    </div>

                    <p className="text sm text-gray">
                        Select pre-synchronized video files recorded outside FreeMoCap. A new recording
                        folder will be created and the videos copied into it.
                    </p>

                    <div className="flex flex-col gap-2 bg-secondary p-2 br-1">
                        <SubactionHeader text="Video files" className="text-gray"/>
                        <div className="flex flex-row gap-2">
                            <ButtonSm
                                text="Choose Video Files..."
                                buttonType="quaternary"
                                onClick={handleChooseFiles}
                                disabled={!isElectron || busy}
                            />
                            <ButtonSm
                                text="Clear Selection"
                                buttonType="quaternary"
                                onClick={handleClearSelection}
                                disabled={videoPaths.length === 0 || busy}
                                tooltip={videoPaths.length === 0}
                                tooltipText="No video files selected"
                                tooltipPosition="pos-top"
                            />
                        </div>
                        {videoPaths.length > 0 ? (
                            <div className="flex flex-col gap-1">
                                {videoPaths.map((path) => (
                                    <p key={path} className="text sm text-white"
                                       style={{fontFamily: 'monospace', wordBreak: 'break-all'}}>
                                        {path.replace(/\\/g, '/').split('/').pop()}
                                    </p>
                                ))}
                            </div>
                        ) : (
                            <p className="text sm text-darkgray">No video files selected</p>
                        )}
                    </div>

                    <div className="flex flex-col gap-1 bg-secondary p-2 br-1">
                        <SubactionHeader text="Recording name" className="text-gray"/>
                        <div className="input-with-string" style={{width: '100%'}}>
                            <input
                                className="input-field text md w-full"
                                value={recordingName}
                                onChange={(e) => setRecordingName(e.target.value)}
                                placeholder={defaultRecordingName}
                                disabled={busy}
                            />
                        </div>
                    </div>

                    {checkingSync && (
                        <p className="text sm text-gray">Checking synchronization…</p>
                    )}

                    {videoPaths.length > 0 && (
                        <div className="flex flex-col gap-2 p-2 br-1 bg-secondary">
                            <div className="flex flex-row gap-2 items-center">
                                <SubactionHeader text="Synchronization" className="text-gray"/>
                                {syncCheck && !syncCheck.synchronized && (
                                    <div className="flex flex-row gap-1 items-center">
                                        <span className="icon warning-icon icon-size-20"/>
                                        <p className="text sm text-gray">frame counts differ — synchronization required</p>
                                    </div>
                                )}
                            </div>

                            {ffmpegMissing && (
                                <div className="toast-notification error">
                                    <p className="text sm">
                                        {ffmpeg.message ?? 'ffmpeg was not found on your system PATH.'} Video
                                        synchronization requires ffmpeg - install it and restart FreeMoCap to
                                        enable this option.
                                    </p>
                                </div>
                            )}

                            {syncCheck && !syncCheck.synchronized && (
                                <div className="flex flex-col gap-1">
                                    {syncCheck.videos.map((video) => (
                                        <p key={video.filename} className="text sm"
                                           style={{fontFamily: 'monospace', wordBreak: 'break-all'}}>
                                            {video.filename}: {video.frameCount} frames ({video.fps.toFixed(2)} fps, {video.durationSeconds.toFixed(2)}s)
                                        </p>
                                    ))}
                                </div>
                            )}

                            <Checkbox
                                label="Synchronize videos on import"
                                checked={syncEnabled && !ffmpegMissing}
                                onChange={(e) => setSyncEnabled(e.target.checked)}
                                disabled={busy || ffmpegMissing || (syncCheck ? !syncCheck.synchronized : false)}
                            />

                            {syncEnabled && (
                                <div className="flex flex-row gap-2 items-center">
                                    <ButtonSm
                                        text="Audio"
                                        buttonType={syncMethod === SyncMethod.AUDIO ? 'activated' : 'idle'}
                                        className="quaternary"
                                        onClick={() => setSyncMethod(SyncMethod.AUDIO)}
                                        disabled={busy}
                                    />
                                    <ButtonSm
                                        text="Brightness flash"
                                        buttonType={syncMethod === SyncMethod.BRIGHTNESS ? 'activated' : 'idle'}
                                        className="quaternary"
                                        onClick={() => setSyncMethod(SyncMethod.BRIGHTNESS)}
                                        disabled={busy}
                                    />
                                </div>
                            )}

                            {syncEnabled && syncMethod === SyncMethod.BRIGHTNESS && (
                                <div className="flex flex-row gap-2 items-center">
                                    <p className="text sm text-gray">Brightness ratio threshold</p>
                                    <div className="input-with-unit" style={{width: '6rem'}}>
                                        <input
                                            className="input-field text md w-full text-center"
                                            type="number"
                                            min={0}
                                            step={100}
                                            value={brightnessRatioThreshold}
                                            onChange={(e) => setBrightnessRatioThreshold(e.target.value)}
                                            disabled={busy}
                                        />
                                    </div>
                                </div>
                            )}

                            {syncing && (
                                <p className="text sm text-gray">
                                    {syncProgress?.detail || 'Synchronizing…'}
                                    {syncProgress ? ` (${syncProgress.progress}%)` : ''}
                                </p>
                            )}
                            {syncError && (
                                <div className="toast-notification error">
                                    <p className="text sm">{syncError}</p>
                                </div>
                            )}
                        </div>
                    )}

                    {error && (
                        <div className="toast-notification error">
                            <p className="text sm">{error}</p>
                        </div>
                    )}

                    <div className="flex flex-row gap-2" style={{justifyContent: 'flex-end'}}>
                        <ButtonSm text="Cancel" buttonType="quaternary" onClick={onClose} disabled={busy}/>
                        <ButtonSm
                            text={busy ? (syncing ? 'Synchronizing…' : 'Importing…') : 'Import'}
                            textColor="text-white"
                            className="primary accent"
                            onClick={handleImport}
                            disabled={importDisabledReason !== null}
                            tooltip={importDisabledReason !== null}
                            tooltipText={importDisabledReason ?? undefined}
                            tooltipPosition="pos-top"
                        />
                    </div>
                </div>
            </div>
        </>
    );
};

export default ImportVideosModal;
