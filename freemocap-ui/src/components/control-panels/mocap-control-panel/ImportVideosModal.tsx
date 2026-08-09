import React, {useCallback, useEffect, useState} from 'react';
import {useElectronIPC} from '@/services';
import {useAppDispatch} from '@/store';
import {importVideos} from '@/store/slices/mocap';
import {activeRecordingSet, splitParentAndName} from '@/store/slices/active-recording/active-recording-slice';
import ButtonSm from '@/components/ui-components/ButtonSm';
import SubactionHeader from '@/components/ui-components/SubactionHeader';

interface ImportVideosModalProps {
    open: boolean;
    onClose: () => void;
}

export const ImportVideosModal: React.FC<ImportVideosModalProps> = ({open, onClose}) => {
    const {isElectron, api} = useElectronIPC();
    const dispatch = useAppDispatch();

    const [videoPaths, setVideoPaths] = useState<string[]>([]);
    const [recordingName, setRecordingName] = useState('');
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (!open) return;
        setVideoPaths([]);
        setRecordingName('');
        setBusy(false);
        setError(null);
    }, [open]);

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

    const handleImport = useCallback(async () => {
        if (videoPaths.length === 0 || busy) return;
        setBusy(true);
        setError(null);
        try {
            const result = await dispatch(importVideos({
                videoPaths,
                recordingName: recordingName.trim() || undefined,
            })).unwrap();

            const parsed = splitParentAndName(result.recordingPath);
            dispatch(activeRecordingSet({
                recordingName: result.recordingName,
                baseDirectory: parsed?.baseDirectory,
                origin: 'browsed',
            }));
            onClose();
        } catch (err) {
            setError(typeof err === 'string' ? err : 'Failed to import videos');
        } finally {
            setBusy(false);
        }
    }, [videoPaths, recordingName, busy, dispatch, onClose]);

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
                        <ButtonSm
                            text="Choose Video Files..."
                            buttonType="quaternary"
                            onClick={handleChooseFiles}
                            disabled={!isElectron || busy}
                        />
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
                        <input
                            className="input-field text md"
                            value={recordingName}
                            onChange={(e) => setRecordingName(e.target.value)}
                            placeholder="Leave blank for auto-generated name"
                            disabled={busy}
                        />
                    </div>

                    {error && (
                        <div className="toast-notification error">
                            <p className="text sm">{error}</p>
                        </div>
                    )}

                    <div className="flex flex-row gap-2" style={{justifyContent: 'flex-end'}}>
                        <ButtonSm text="Cancel" buttonType="quaternary" onClick={onClose} disabled={busy}/>
                        <ButtonSm
                            text={busy ? 'Importing…' : 'Import'}
                            textColor="text-white"
                            className="primary accent"
                            onClick={handleImport}
                            disabled={videoPaths.length === 0 || busy}
                        />
                    </div>
                </div>
            </div>
        </>
    );
};

export default ImportVideosModal;
