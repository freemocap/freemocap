import React, {useEffect, useRef, useState} from 'react';
import ReactDOM from 'react-dom';
import {useAppDispatch, useAppSelector} from '@/store';
import {cameraDesiredConfigUpdated, configCopiedToAll, savedSettingsCleared} from '@/store/slices/cameras/cameras-slice';
import {camerasConnectOrUpdate} from '@/store/slices/cameras/cameras-thunks';
import {selectCameras} from '@/store/slices/cameras';
import {
    Camera,
    CameraConfig,
    ExposureMode,
    ROTATION_DEGREE_LABELS,
    ROTATION_OPTIONS,
    RotationValue,
} from '@/store/slices/cameras/cameras-types';
import ButtonSm from '@/components/ui-components/ButtonSm';
import IconButton from '@/components/ui-components/IconButton';
import NameDropdownSelector from '@/components/ui-components/NameDropdownSelector';
import {Row} from '@/components/ui-components/Row';
import SegmentedControl from '@/components/ui-components/SegmentedControl';
import ValueSelector from '@/components/ui-components/ValueSelector';

interface CameraSettingsModalProps {
    camera: Camera;
    initialPos: {top: number; left: number};
    onClose: () => void;
}

const PRESET_RESOLUTIONS = [
    {width: 640, height: 480, label: '640 × 480'},
    {width: 1280, height: 720, label: '1280 × 720'},
    {width: 1920, height: 1080, label: '1920 × 1080'},
];

const EXPOSURE_MIN = -13;
const EXPOSURE_MAX = -4;

const resolutionLabel = (config: CameraConfig): string => {
    const preset = PRESET_RESOLUTIONS.find(
        p => p.width === config.resolution.width && p.height === config.resolution.height,
    );
    return preset?.label ?? `${config.resolution.width} × ${config.resolution.height}`;
};

export const CameraSettingsModal: React.FC<CameraSettingsModalProps> = ({camera, initialPos, onClose}) => {
    const dispatch = useAppDispatch();
    const allCameras = useAppSelector(selectCameras);
    const otherCamerasCount = allCameras.length - 1;
    const [pos, setPos] = useState(initialPos);
    const dragRef = useRef<{startX: number; startY: number; startTop: number; startLeft: number} | null>(null);
    const modalRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        const handleKey = (e: KeyboardEvent) => {
            if (e.key === 'Escape') onClose();
        };
        window.addEventListener('keydown', handleKey);
        return () => window.removeEventListener('keydown', handleKey);
    }, [onClose]);

    useEffect(() => {
        const handleClickOutside = (e: MouseEvent) => {
            if (modalRef.current && !modalRef.current.contains(e.target as Node)) onClose();
        };
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, [onClose]);

    const handleConfigChange = (patch: Partial<CameraConfig>) => {
        dispatch(cameraDesiredConfigUpdated({cameraId: camera.id, config: {...camera.desiredConfig, ...patch}}));
    };

    const handlePointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
        if ((e.target as HTMLElement).closest('button, input, select')) return;
        e.currentTarget.setPointerCapture(e.pointerId);
        dragRef.current = {startX: e.clientX, startY: e.clientY, startTop: pos.top, startLeft: pos.left};
        e.currentTarget.style.cursor = 'grabbing';
    };

    const handlePointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
        if (!dragRef.current || !e.currentTarget.hasPointerCapture(e.pointerId)) return;
        setPos({
            top: dragRef.current.startTop + (e.clientY - dragRef.current.startY),
            left: dragRef.current.startLeft + (e.clientX - dragRef.current.startX),
        });
    };

    const handlePointerUp = (e: React.PointerEvent<HTMLDivElement>) => {
        if (dragRef.current) {
            e.currentTarget.releasePointerCapture(e.pointerId);
            e.currentTarget.style.cursor = 'grab';
            dragRef.current = null;
        }
    };

    const config = camera.desiredConfig;
    const isManual = config.exposure_mode === 'MANUAL';

    return ReactDOM.createPortal(
        <div
            ref={modalRef}
            className="camera-settings-container fit-content reveal slide-down camera-settings-modal modal draggable border-1 border-black elevated-sharp flex flex-col p-1 bg-dark br-2 fadeIn gap-1 z-2"
            style={{position: 'fixed', top: pos.top, left: pos.left, zIndex: 300, cursor: 'grab'}}
            onPointerDown={handlePointerDown}
            onPointerMove={handlePointerMove}
            onPointerUp={handlePointerUp}
            onClick={e => e.stopPropagation()}
        >
            <div className="fit-content flex flex-col right-0 p-2 gap-1 bg-middark br-1 z-1">
                {/* Header */}
                <div className="subaction-header-container justify-content-space-between gap-1 br-1 flex items-center h-25 p-1">
                    <p className="text-nowrap text-left bg-md text-darkgray">Camera settings</p>
                    <div className="flex flex-row gap-1">
                        <ButtonSm
                            text={
                                otherCamerasCount > 0
                                    ? `Copy to ${otherCamerasCount} other${otherCamerasCount > 1 ? 's' : ''}`
                                    : 'No other cameras'
                            }
                            iconClass="copyover-icon"
                            buttonType={otherCamerasCount === 0 ? 'disabled' : ''}
                            onClick={() => {
                                if (otherCamerasCount > 0) dispatch(configCopiedToAll(camera.id));
                            }}
                        />
                    </div>
                </div>

                {/* Rotate */}
                <Row label="Rotate">
                    <SegmentedControl
                        options={ROTATION_OPTIONS.map((o: RotationValue) => ({
                            label: ROTATION_DEGREE_LABELS[o],
                            value: String(o),
                        }))}
                        value={String(config.rotation ?? -1)}
                        onChange={v => handleConfigChange({rotation: Number(v) as RotationValue})}
                        size="sm"
                        className="segmented-control-sm bg-darkgray"
                    />
                </Row>

                {/* Resolution */}
                <Row label="Resolution">
                    <NameDropdownSelector
                        options={PRESET_RESOLUTIONS.map(p => p.label)}
                        initialValue={resolutionLabel(config)}
                        onChange={label => {
                            const preset = PRESET_RESOLUTIONS.find(p => p.label === label);
                            if (preset) handleConfigChange({resolution: {width: preset.width, height: preset.height}});
                        }}
                    />
                </Row>

                {/* Exposure mode */}
                <Row label="Exposure">
                    <NameDropdownSelector
                        options={['Manual', 'Auto']}
                        initialValue={config.exposure_mode === 'MANUAL' ? 'Manual' : 'Auto'}
                        onChange={v =>
                            handleConfigChange({exposure_mode: (v === 'Manual' ? 'MANUAL' : 'AUTO') as ExposureMode})
                        }
                    />
                </Row>

                {/* Exposure value — only when manual */}
                {isManual && (
                    <Row label="Change exposure" indent>
                        <ValueSelector
                            value={Math.max(EXPOSURE_MIN, Math.min(EXPOSURE_MAX, config.exposure ?? -7))}
                            min={EXPOSURE_MIN}
                            max={EXPOSURE_MAX}
                            unit=""
                            onChange={v => handleConfigChange({exposure: v})}
                        />
                    </Row>
                )}

                {/* Footer */}
                <div className="flex flex-row gap-1 pt-1">
                    <button
                        className="button sm br-1 flex-1"
                        style={{background: 'var(--color-text-primary)', color: 'var(--color-bg-primary)'}}
                        onClick={() => dispatch(camerasConnectOrUpdate())}
                        title="Update camera settings"
                    >
                        <p className="text md" style={{color: 'var(--color-bg-primary)'}}>Update Settings</p>
                    </button>
                    <IconButton
                        icon="clear-icon"
                        className="icon-size-25 gap-1 sm fit-content flex-inline text-left items-center"
                        onClick={() => dispatch(savedSettingsCleared())}
                        title="Reset all cameras to default settings"
                    />
                </div>
            </div>
        </div>,
        document.body,
    );
};
