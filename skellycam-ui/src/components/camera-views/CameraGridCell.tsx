import React, { useState, useRef } from 'react';
import ReactDOM from 'react-dom';
import clsx from 'clsx';
import { useAppDispatch, useAppSelector } from '@/store';
import { cameraSelectionToggled } from '@/store/slices/cameras/cameras-slice';
import { selectCameraById } from '@/store/slices/cameras/cameras-selectors';
import { CameraView } from './CameraView';
import { CameraGridSettingsModal } from './CameraGridSettingsModal';
import Checkbox from '@/components/ui-components/Checkbox';
import IconButton from '@/components/ui-components/IconButton';

interface CameraGridCellProps {
    cameraId: string;
}

export const CameraGridCell: React.FC<CameraGridCellProps> = ({ cameraId }) => {
    const dispatch = useAppDispatch();
    const camera = useAppSelector(state => selectCameraById(state, cameraId));
    const [settingsOpen, setSettingsOpen] = useState(false);
    const [modalPos, setModalPos] = useState<{ top: number; left: number }>({ top: 80, left: 40 });
    const settingsBtnRef = useRef<HTMLButtonElement>(null);

    if (!camera) return <CameraView cameraId={cameraId} />;

    const handleOpenSettings = () => {
        if (!settingsOpen && settingsBtnRef.current) {
            const rect = settingsBtnRef.current.getBoundingClientRect();
            setModalPos({
                top: rect.bottom + 8,
                left: rect.left - 320 - 8,
            });
        }
        setSettingsOpen(prev => !prev);
    };

    return (
        <div style={{ position: 'relative', width: '100%', height: '100%' }}>
            <CameraView cameraId={cameraId} />

            {/* Overlay header — fades in on hover */}
            <div className="camera-cell-overlay p-1">
                <Checkbox
                    label=""
                    checked={camera.selected}
                    onChange={(e) => {
                        e.stopPropagation();
                        dispatch(cameraSelectionToggled(cameraId));
                    }}
                />

                <div className="flex-1" />

                <IconButton
                    ref={settingsBtnRef}
                    icon={settingsOpen ? 'close-icon' : 'settings-icon'}
                    onClick={handleOpenSettings}
                    className={clsx('icon-size-25', settingsOpen && 'activated')}

                    tooltip={true}
                    tooltipText="Camera settings"
                    tooltipPosition="pos-left"

                    onMouseDown={(e: React.MouseEvent) => e.stopPropagation()}
                />
            </div>

            {/* Portal — renders outside the transformed grid cell */}
            {settingsOpen && ReactDOM.createPortal(
                <CameraGridSettingsModal
                    camera={camera}
                    initialPos={modalPos}
                    onClose={() => setSettingsOpen(false)}
                />,
                document.body
            )}
        </div>
    );
};
