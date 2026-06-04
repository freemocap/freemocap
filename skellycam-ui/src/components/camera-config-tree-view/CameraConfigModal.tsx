import React, { useEffect, useCallback } from 'react';
import { useAppDispatch, useAppSelector, selectCameras, selectConnectedCameras, selectIsLoading, detectCameras } from '@/store';
import { camerasConnectOrUpdate } from '@/store/slices/cameras/cameras-thunks';
import { savedSettingsCleared } from '@/store/slices/cameras/cameras-slice';
import { CameraTreeItem } from './CameraTreeItem';
import { NoCamerasPlaceholder } from './NoCamerasPlaceholder';
import { useServer } from '@/services/server/ServerContextProvider';
import { useRecordingGuard } from '@/components/RecordingGuardProvider';

interface CameraConfigModalProps {
    open: boolean;
    onClose: () => void;
}

export const CameraConfigModal: React.FC<CameraConfigModalProps> = ({ open, onClose }) => {
    const dispatch = useAppDispatch();
    const { isConnected } = useServer();
    const { requestGuardedAction } = useRecordingGuard();
    const cameras = useAppSelector(selectCameras);
    const connectedCameras = useAppSelector(selectConnectedCameras);
    const isLoading = useAppSelector(selectIsLoading);

    useEffect(() => {
        if (!open) return;
        const handleKeyDown = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [open, onClose]);

    useEffect(() => {
        if (open && isConnected && cameras.length === 0) {
            dispatch(detectCameras({ filterVirtual: true }));
        }
    }, [open, isConnected, cameras.length, dispatch]);

    const handleUpdate = useCallback(() => {
        requestGuardedAction('Stop Recording & Update Camera Config', () => dispatch(camerasConnectOrUpdate()));
    }, [dispatch, requestGuardedAction]);

    const handleDetect = useCallback(() => {
        dispatch(detectCameras({ filterVirtual: true }));
    }, [dispatch]);

    if (!open) return null;

    return (
        <div
            className="splash-overlay inset-0 reveal fadeIn"
            style={{ position: 'fixed', zIndex: 50 }}
            onClick={onClose}
        >
            <div
                className="bg-dark br-2 border-1 border-accent elevated-sharp flex flex-col"
                style={{ minWidth: 480, maxWidth: 640, maxHeight: '85vh' }}
                onClick={(e) => e.stopPropagation()}
            >
                {/* Header */}
                <div className="flex items-center gap-2 p-2" style={{ borderBottom: '1px solid var(--color-text-muted)' }}>
                    <p className="text md text-white text-nowrap">
                        {cameras.length} Cameras
                    </p>
                    {connectedCameras.length > 0 && (
                        <p className="text md text-nowrap" style={{ color: 'var(--color-success, #4ade80)' }}>
                            {connectedCameras.length} Streaming
                        </p>
                    )}
                    <button className="button icon-button" onClick={handleDetect} title="Detect cameras">
                        <span className={`icon icon-size-20 ${isLoading ? 'loader-icon' : 'scan-icon'}`} />
                    </button>

                    <div className="flex-1" />

                    <button className="button icon-button" onClick={() => requestGuardedAction('Stop Recording & Clear Camera Settings', () => dispatch(savedSettingsCleared()))} title="Reset all cameras to default settings">
                        <span className="icon icon-size-20 clear-icon" />
                    </button>

                    <button className="button sm br-1" onClick={handleUpdate} style={{ background: 'var(--color-text-primary)', color: 'var(--color-bg-primary)' }}>
                        <p className="text md" style={{ color: 'var(--color-bg-primary)' }}>Update</p>
                    </button>

                    <button className="button icon-button" onClick={onClose}>
                        <span className="icon close-icon icon-size-20" />
                    </button>
                </div>

                {/* Camera list */}
                <div className="flex flex-col overflow-y">
                    {cameras.length === 0 ? (
                        <NoCamerasPlaceholder />
                    ) : (
                        cameras
                            .slice()
                            .sort((a, b) => a.index - b.index)
                            .map(camera => (
                                <CameraTreeItem key={camera.id} camera={camera} />
                            ))
                    )}
                </div>
            </div>
        </div>
    );
};
