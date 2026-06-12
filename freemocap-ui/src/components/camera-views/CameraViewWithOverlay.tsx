import React, {useState} from 'react';
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
    const [hovered, setHovered] = useState(false);
    const [isApplying, setIsApplying] = useState(false);
    const camera = useAppSelector(state => selectCameraById(state, cameraId));
    const desiredConfig = camera?.desiredConfig;

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
        <div
            className="pos-rel w-full h-full"
            onMouseEnter={() => setHovered(true)}
            onMouseLeave={() => setHovered(false)}
        >
            <CameraView cameraIndex={cameraIndex} cameraId={cameraId} maxWidth/>

            {hovered && (
                <div className="pos-abs top-6 right-6 flex flex-col z-10 br-2 border-1 border-black elevated-sharp bg-dark p-1 gap-1">
                    <Row label="Rotate">
                        <IconButton
                            icon="rotate-icon"
                            title="Rotate 90° clockwise"
                            onClick={handleRotate}
                            disabled={isLoading}
                        />
                        <span className="text sm text-gray">{ROTATION_DEGREE_LABELS[rotation]}</span>
                    </Row>

                    <Row label="Exposure">
                        <IconButton
                            icon="minus-icon"
                            title="Decrease exposure"
                            onClick={handleExposureDown}
                            disabled={isLoading || exposureMode !== 'MANUAL' || exposure <= EXPOSURE_MIN}
                        />
                        <span className="text sm text-gray">{exposureLabel}</span>
                        <IconButton
                            icon="plus-icon"
                            title="Increase exposure"
                            onClick={handleExposureUp}
                            disabled={isLoading || exposureMode !== 'MANUAL' || exposure >= EXPOSURE_MAX}
                        />
                    </Row>

                    <Row label="Mode">
                        <IconButton
                            icon="settings-icon"
                            title={exposureMode === 'AUTO' ? 'Switch to manual exposure' : 'Switch to auto exposure'}
                            onClick={handleAutoExposure}
                            disabled={isLoading}
                            style={{color: exposureMode === 'AUTO' ? 'var(--color-accent)' : 'inherit', opacity: exposureMode === 'AUTO' ? 1 : 0.5}}
                        />
                        <IconButton
                            icon="warning-icon"
                            title="Recommend exposure for this camera"
                            onClick={handleRecommendExposure}
                            disabled={isLoading}
                        />
                    </Row>

                    <Row label="Auto-apply">
                        <IconButton
                            icon="loop-icon"
                            title={isAutoApply ? 'Auto-apply on — changes send automatically' : 'Auto-apply off — click apply to send'}
                            onClick={() => dispatch(autoApplyToggled())}
                            style={{color: isAutoApply ? 'var(--color-accent)' : 'inherit', opacity: isAutoApply ? 1 : 0.5}}
                        />
                        {!isAutoApply && (
                            <IconButton
                                icon={isApplying ? 'loader-icon' : 'upToDate-icon'}
                                title="Apply changes to camera"
                                onClick={handleApply}
                                disabled={isApplying}
                            />
                        )}
                    </Row>
                </div>
            )}
        </div>
    );
};
