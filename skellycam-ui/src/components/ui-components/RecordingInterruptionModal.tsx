import React, { useEffect } from 'react';
import ButtonSm from '@/components/ui-components/ButtonSm';

interface RecordingInterruptionModalProps {
    open: boolean;
    message: string;
    confirmLabel: string;
    onConfirm: () => void;
    onCancel: () => void;
}

export const RecordingInterruptionModal: React.FC<RecordingInterruptionModalProps> = ({
    open,
    message,
    confirmLabel,
    onConfirm,
    onCancel,
}) => {
    useEffect(() => {
        if (!open) return;
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === 'Escape') onCancel();
        };
        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [open, onCancel]);

    if (!open) return null;

    return (
        <div
            className="splash-overlay inset-0"
            style={{ position: 'fixed', zIndex: 9999 }}
            onClick={onCancel}
        >
            <div
                className="bg-dark br-2 border-1 border-black elevated-sharp flex flex-col p-2 gap-2"
                style={{ minWidth: 320, maxWidth: 480 }}
                onClick={(e) => e.stopPropagation()}
            >
                <div className="flex items-center gap-1">
                    <span className="icon warning-icon icon-size-20" style={{ color: 'var(--color-warning)' }} />
                    <p className="text bg text-white">Recording in Progress</p>
                </div>
                <p className="text sm text-gray">{message}</p>
                <div className="flex gap-1 justify-content-space-between">
                    <ButtonSm
                        text="Cancel"
                        buttonType="secondary"
                        textColor="text-white"
                        onClick={onCancel}
                    />
                    <ButtonSm
                        text={confirmLabel}
                        textColor="text-white"
                        onClick={onConfirm}
                        className="btn-danger"
                    />
                </div>
            </div>
        </div>
    );
};
