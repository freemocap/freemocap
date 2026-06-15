import React, {useState, useRef, useEffect} from 'react';
import IconButton from '@/components/ui-components/IconButton';
import {Row} from '@/components/ui-components/Row';
import {useAppDispatch, useAppSelector} from '@/store/hooks';
import {selectCameraById} from '@/store/slices/cameras/cameras-selectors';
import {cameraDesiredConfigUpdated, autoApplyToggled} from '@/store/slices/cameras/cameras-slice';
import {camerasConnectOrUpdate} from '@/store/slices/cameras/cameras-thunks';
import {ROTATION_DEGREE_LABELS, ROTATION_OPTIONS, RotationValue} from '@/store/slices/cameras/cameras-types';
import {CameraView} from './CameraView';

const EXPOSURE_MIN = -13;
const EXPOSURE_MAX = -4;

interface CameraViewWithOverlayProps {
    cameraIndex: number;
    cameraId: string;
    isLoading: boolean;
    isAutoApply: boolean;
}

export const CameraViewWithOverlay: React.FC<CameraViewWithOverlayProps> = ({cameraIndex, cameraId, isLoading, isAutoApply}) => {
    const dispatch = useAppDispatch();
    const [showSettings, setShowSettings] = useState(false);
    const [isApplying, setIsApplying] = useState(false);
    const overlayRef = useRef<HTMLDivElement>(null);
    const camera = useAppSelector(state => selectCameraById(state, cameraId));
    const desiredConfig = camera?.desiredConfig;

    useEffect(() => {
        if (!showSettings) return;

        const handleClickOutside = (e: MouseEvent) => {
            if (overlayRef.current && !overlayRef.current.contains(e.target as Node)) {
                setShowSettings(false);
            }
        };

        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, [showSettings]);

    const rotation = desiredConfig?.rotation as RotationValue ?? -1;
    const exposure = desiredConfig?.exposure ?? -7;
    const exposureMode = desiredConfig?.exposure_mode ?? 'MANUAL';

    const handleRotate = () => {
        if (!desiredConfig) return;
        const idx = ROTATION_OPTIONS.indexOf(rotation);
        const next = ROTATION_OPTIONS[(idx + 1) % ROTATION_OPTIONS.length];
        dispatch(cameraDesiredConfigUpdated({cameraId, config: {rotation: next}}));
    };

    const handleExposureUp = () => {
        if (!desiredConfig) return;
        dispatch(cameraDesiredConfigUpdated({
            cameraId,
            config: {exposure: Math.min(EXPOSURE_MAX, exposure + 1), exposure_mode: 'MANUAL'},
        }));
    };

    const handleExposureDown = () => {
        if (!desiredConfig) return;
        dispatch(cameraDesiredConfigUpdated({
            cameraId,
            config: {exposure: Math.max(EXPOSURE_MIN, exposure - 1), exposure_mode: 'MANUAL'},
        }));
    };

    const handleRecommendExposure = () => {
        dispatch(cameraDesiredConfigUpdated({cameraId, config: {exposure_mode: 'RECOMMEND'}}));
    };

    const handleAutoExposure = () => {
        if (exposureMode === 'AUTO') {
            dispatch(cameraDesiredConfigUpdated({cameraId, config: {exposure_mode: 'MANUAL'}}));
        } else {
            dispatch(cameraDesiredConfigUpdated({cameraId, config: {exposure_mode: 'AUTO'}}));
        }
    };

    const handleApply = async () => {
        setIsApplying(true);
        try {
            await dispatch(camerasConnectOrUpdate()).unwrap();
        } catch {
            // error stored in redux state
        } finally {
            setIsApplying(false);
        }
    };

    const exposureLabel =
        exposureMode === 'AUTO'      ? 'auto' :
        exposureMode === 'RECOMMEND' ? '...'  :
        String(exposure);

    return (
        <div className="pos-rel w-full h-full">
            <CameraView cameraIndex={cameraIndex} cameraId={cameraId} maxWidth/>

            {/* Settings toggle button */}
            <div
                className="pos-abs top-6 right-6 z-10"
                ref={overlayRef}
            >
                <IconButton
                    icon="settings-icon"
                    title={showSettings ? 'Close settings' : 'Open settings'}
                    onClick={() => setShowSettings(prev => !prev)}
                />

                {showSettings && (
                    <div className="camera-settings-container camera-overylay-settings pos-abs top-6 right-6 flex flex-col z-10 br-2 border-1 border-black elevated-sharp bg-dark p-1 gap-1">
                        <div className="fit-content flex flex-col right-0 p-2 gap-1 bg-middark br-1 z-1">
                            {/* Header */}
                            <div className="subaction-header-container justify-content-space-between gap-1 br-1 flex items-center h-25 p-1">
                                <p className="text-nowrap text-left bg-md text-darkgray">Camera settings</p>
                            </div>

                            {/* Rotate */}
                            <Row label="Rotate">
                                <IconButton
                                    icon="rotate-icon"
                                    title="Rotate 90° clockwise"
                                    onClick={handleRotate}
                                    disabled={isLoading}
                                />
                                <span className="text sm text-gray">{ROTATION_DEGREE_LABELS[rotation]}</span>
                            </Row>

                            {/* Exposure mode */}
                            <Row label="Exposure">
                                <div className="flex flex-row gap-1 items-center">
                                    <IconButton
                                        icon="settings-icon"
                                        title={exposureMode === 'AUTO' ? 'Switch to manual exposure' : 'Switch to auto exposure'}
                                        onClick={handleAutoExposure}
                                        disabled={isLoading}
                                        style={{color: exposureMode === 'AUTO' ? 'var(--color-accent)' : 'inherit', opacity: exposureMode === 'AUTO' ? 1 : 0.5}}
                                    />
                                    <span className="text sm text-gray">{exposureLabel}</span>
                                    <IconButton
                                        icon="warning-icon"
                                        title="Recommend exposure for this camera"
                                        onClick={handleRecommendExposure}
                                        disabled={isLoading}
                                    />
                                </div>
                            </Row>

                            {/* Exposure value — only when manual */}
                            {exposureMode === 'MANUAL' && (
                                <Row label="Change exposure" indent>
                                    <div className="flex flex-row gap-1 items-center">
                                        <IconButton
                                            icon="minus-icon"
                                            title="Decrease exposure"
                                            onClick={handleExposureDown}
                                            disabled={isLoading || exposure <= EXPOSURE_MIN}
                                        />
                                        <span className="text sm text-gray">{exposure}</span>
                                        <IconButton
                                            icon="plus-icon"
                                            title="Increase exposure"
                                            onClick={handleExposureUp}
                                            disabled={isLoading || exposure >= EXPOSURE_MAX}
                                        />
                                    </div>
                                </Row>
                            )}

                            {/* Footer */}
                            <div className="flex flex-row gap-1 pt-1">
                                <IconButton
                                    icon="loop-icon"
                                    title={isAutoApply ? 'Auto-apply on — changes send automatically' : 'Auto-apply off — click apply to send'}
                                    onClick={() => dispatch(autoApplyToggled())}
                                    style={{color: isAutoApply ? 'var(--color-accent)' : 'inherit', opacity: isAutoApply ? 1 : 0.5}}
                                />
                                {!isAutoApply && (
                                    <button
                                        className="button sm br-1 flex-1"
                                        style={{background: 'var(--color-text-primary)', color: 'var(--color-bg-primary)'}}
                                        onClick={handleApply}
                                        disabled={isApplying}
                                        title="Apply changes to camera"
                                    >
                                        <p className="text md" style={{color: 'var(--color-bg-primary)'}}>
                                            {isApplying ? 'Applying...' : 'Apply'}
                                        </p>
                                    </button>
                                )}
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};
