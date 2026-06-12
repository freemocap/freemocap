import React, {useState} from 'react';
import IconButton from '@/components/ui-components/IconButton';
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
                <div
                    className="pos-abs top-6 right-6 flex flex-col z-10 br-2"
                    style={{
                        gap: '5px',
                        backgroundColor: 'rgba(0,0,0,0.55)',
                        backdropFilter: 'blur(3px)',
                        border: '1px solid rgba(255,255,255,0.12)',
                        padding: '6px',
                    }}>
                    <div className="flex items-center" style={{gap: '6px'}}>
                        <IconButton
                            icon="rotate-icon"
                            title="Rotate 90° clockwise"
                            onClick={handleRotate}
                            disabled={isLoading}
                            className=""
                            iconSize=""
                            style={btnStyle}
                            iconStyle={{fontSize: 16}}
                        />
                        <span style={valueStyle}>{ROTATION_DEGREE_LABELS[rotation]}</span>
                    </div>

                    <div style={{height: '1px', backgroundColor: 'rgba(255,255,255,0.1)', margin: '0 -2px'}}/>

                    <div className="flex items-center gap-1">
                        <IconButton
                            icon="minus-icon"
                            title="Decrease exposure"
                            onClick={handleExposureDown}
                            disabled={isLoading || exposureMode !== 'MANUAL' || exposure <= EXPOSURE_MIN}
                            className=""
                            iconSize=""
                            style={btnStyle}
                            iconStyle={{fontSize: 16}}
                        />
                        <IconButton
                            icon="plus-icon"
                            title="Increase exposure"
                            onClick={handleExposureUp}
                            disabled={isLoading || exposureMode !== 'MANUAL' || exposure >= EXPOSURE_MAX}
                            className=""
                            iconSize=""
                            style={btnStyle}
                            iconStyle={{fontSize: 16}}
                        />
                        <span style={valueStyle}>{exposureLabel}</span>
                    </div>

                    <div className="flex items-center gap-1">
                        <IconButton
                            icon="settings-icon"
                            title={exposureMode === 'AUTO' ? 'Switch to manual exposure' : 'Switch to auto exposure'}
                            onClick={handleAutoExposure}
                            disabled={isLoading}
                            className=""
                            iconSize=""
                            style={exposureMode === 'AUTO' ? btnActiveStyle : btnStyle}
                            iconStyle={{fontSize: 16}}
                        />
                        <IconButton
                            icon="warning-icon"
                            title="Recommend exposure for this camera"
                            onClick={handleRecommendExposure}
                            disabled={isLoading}
                            className=""
                            iconSize=""
                            style={btnStyle}
                            iconStyle={{fontSize: 16}}
                        />
                    </div>

                    <div style={{height: '1px', backgroundColor: 'rgba(255,255,255,0.1)', margin: '0 -2px'}}/>

                    <div className="flex items-center gap-1">
                        <IconButton
                            icon="loop-icon"
                            title={isAutoApply ? 'Auto-apply on — changes send automatically' : 'Auto-apply off — click apply to send'}
                            onClick={() => dispatch(autoApplyToggled())}
                            className=""
                            iconSize=""
                            style={isAutoApply ? btnActiveStyle : btnStyle}
                            iconStyle={{fontSize: 16}}
                        />
                        {!isAutoApply && (
                            <IconButton
                                icon={isApplying ? 'loader-icon' : 'upToDate-icon'}
                                title="Apply changes to camera"
                                onClick={handleApply}
                                disabled={isApplying}
                                className=""
                                iconSize=""
                                style={btnStyle}
                                iconStyle={{fontSize: 16}}
                            />
                        )}
                    </div>
                </div>
            )}
        </div>
    );
};

const btnStyle: React.CSSProperties = {
    width: 24,
    height: 24,
    padding: '3px',
    color: 'rgba(255,255,255,0.8)',
    borderRadius: '5px',
    outline: 'none',
    background: 'none',
    border: 'none',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
};

const btnActiveStyle: React.CSSProperties = {
    ...btnStyle,
    color: '#fff',
    backgroundColor: 'rgba(255,255,255,0.2)',
};

const valueStyle: React.CSSProperties = {
    fontSize: 11,
    fontFamily: 'monospace',
    color: 'rgba(255,255,255,0.85)',
    minWidth: '28px',
    lineHeight: 1,
};
