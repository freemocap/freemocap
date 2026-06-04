import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { useAppDispatch, useAppSelector } from '@/store';
import { stopRecording } from '@/store/slices/recording';
import { RecordingInterruptionModal } from '@/components/ui-components/RecordingInterruptionModal';
import { isElectron } from '@/services/electron-ipc/electron-ipc';

interface RecordingGuardContextValue {
    requestGuardedAction: (confirmLabel: string, onConfirm: () => void) => void;
}

const RecordingGuardContext = createContext<RecordingGuardContextValue | null>(null);

export const useRecordingGuard = (): RecordingGuardContextValue => {
    const ctx = useContext(RecordingGuardContext);
    if (!ctx) throw new Error('useRecordingGuard must be used within RecordingGuardProvider');
    return ctx;
};

interface ModalState {
    open: boolean;
    message: string;
    confirmLabel: string;
    onConfirm: () => void;
    onCancel: () => void;
}

const CLOSED_MODAL: ModalState = {
    open: false,
    message: '',
    confirmLabel: '',
    onConfirm: () => {},
    onCancel: () => {},
};

export const RecordingGuardProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const dispatch = useAppDispatch();
    const isRecording = useAppSelector((state) => state.recording.isRecording);
    const recordingName = useAppSelector((state) => state.recording.recordingName);
    const [modalState, setModalState] = useState<ModalState>(CLOSED_MODAL);

    // Refs prevent stale closures in the Electron close listener
    const isRecordingRef = useRef(isRecording);
    const recordingNameRef = useRef(recordingName);
    useEffect(() => { isRecordingRef.current = isRecording; }, [isRecording]);
    useEffect(() => { recordingNameRef.current = recordingName; }, [recordingName]);

    const closeModal = useCallback(() => setModalState(CLOSED_MODAL), []);

    const buildMessage = (suffix: string) => {
        const name = recordingNameRef.current;
        return `Recording${name ? ` "${name}"` : ''} is in progress. ${suffix}`;
    };

    const requestGuardedAction = useCallback((confirmLabel: string, onConfirm: () => void): void => {
        if (!isRecordingRef.current) {
            onConfirm();
            return;
        }
        setModalState({
            open: true,
            message: buildMessage('This action will interrupt the session.'),
            confirmLabel,
            onConfirm: () => {
                closeModal();
                dispatch(stopRecording()).finally(() => onConfirm());
            },
            onCancel: closeModal,
        });
    // buildMessage uses refs so it's safe to omit from deps
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [closeModal, dispatch]);

    // Intercept Electron window close/quit when recording is active
    useEffect(() => {
        if (!isElectron() || !window.electronAPI?.onRequestCloseConfirmation) return;

        const cleanup = window.electronAPI.onRequestCloseConfirmation(() => {
            if (!isRecordingRef.current) {
                window.electronAPI.sendCloseConfirmationResult(true);
                return;
            }
            const name = recordingNameRef.current;
            const message = `Recording${name ? ` "${name}"` : ''} is in progress. Closing will stop the recording.`;
            setModalState({
                open: true,
                message,
                confirmLabel: 'Stop Recording & Quit',
                onConfirm: () => {
                    closeModal();
                    window.electronAPI.sendCloseConfirmationResult(true);
                },
                onCancel: () => {
                    closeModal();
                    window.electronAPI.sendCloseConfirmationResult(false);
                },
            });
        });

        return cleanup;
    }, [closeModal]);

    return (
        <RecordingGuardContext.Provider value={{ requestGuardedAction }}>
            {children}
            <RecordingInterruptionModal
                open={modalState.open}
                message={modalState.message}
                confirmLabel={modalState.confirmLabel}
                onConfirm={modalState.onConfirm}
                onCancel={modalState.onCancel}
            />
        </RecordingGuardContext.Provider>
    );
};
