import React, {useEffect, useRef} from 'react';
import useDraggableTooltips from '@/hooks/useDraggableTooltips';
import SubactionHeader from '@/components/ui-components/SubactionHeader';
import IconButton from '@/components/ui-components/IconButton';
import {RecordingPathTreeItem} from './RecordingPathTreeItem';

interface RecordingPathModalProps {
    open: boolean;
    onClose: () => void;
    recordingDirectory: string;
    countdown: number | null;
    recordingTag: string;
    useTimestamp: boolean;
    baseName: string;
    useIncrement: boolean;
    currentIncrement: number;
    createSubfolder: boolean;
    customSubfolderName: string;
    isRecording: boolean;
    onTagChange: (value: string) => void;
    onNameChange: (value: string) => void;
    onUseTimestampChange: (value: boolean) => void;
    onBaseNameChange: (value: string) => void;
    onUseIncrementChange: (value: boolean) => void;
    onIncrementChange: (value: number) => void;
    onCreateSubfolderChange: (value: boolean) => void;
    onCustomSubfolderNameChange: (value: string) => void;
}

export const RecordingPathModal: React.FC<RecordingPathModalProps> = ({open, onClose, ...itemProps}) => {
    useDraggableTooltips();
    
    const modalRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (!open) return;

        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === 'Escape') onClose();
        };

        const handleClickOutside = (e: MouseEvent) => {
            if (modalRef.current && !modalRef.current.contains(e.target as Node)) {
                onClose();
            }
        };

        window.addEventListener('keydown', handleKeyDown);
        document.addEventListener('mousedown', handleClickOutside);

        return () => {
            window.removeEventListener('keydown', handleKeyDown);
            document.removeEventListener('mousedown', handleClickOutside);
        };
    }, [open, onClose]);

    if (!open) return null;

    return (
        <div
            ref={modalRef}
            className="file-directory-settings-container draggable border-1 border-black elevated-sharp flex flex-col p-1 bg-dark br-2 reveal fadeIn gap-1"
        >
            <div className="flex flex-col right-0 p-2 gap-1 bg-middark br-1 z-1">
                <div className="flex justify-content-space-between items-center">
                    <SubactionHeader text="Recording Path &amp; Settings" />
                    <IconButton icon="close-icon" onClick={onClose} />
                </div>
                <RecordingPathTreeItem {...itemProps} />
            </div>
        </div>
    );
};
