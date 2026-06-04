import React, {useState} from 'react';
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
            style={{position: 'relative', width: '100%', height: '100%'}}
            onMouseEnter={() => setHovered(true)}
            onMouseLeave={() => setHovered(false)}
        >
            <CameraView cameraIndex={cameraIndex} cameraId={cameraId} maxWidth/>

            {hovered && (
                <div style={{
                    position: 'absolute',
                    top: 6,
                    right: 6,
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '5px',
                    zIndex: 10,
                    backgroundColor: 'rgba(0,0,0,0.55)',
                    backdropFilter: 'blur(3px)',
                    border: '1px solid rgba(255,255,255,0.12)',
                    borderRadius: '8px',
                    padding: '6px',
                }}>
                    <div style={{display: 'flex', alignItems: 'center', gap: '6px'}}>
                        <button
                            title="Rotate 90° clockwise"
                            className="button icon-button"
                            onClick={handleRotate}
                            disabled={isLoading}
                            style={btnStyle}
                        >
                            <span className="icon rotate-icon" style={{fontSize: 16}}/>
                        </button>
                        <span style={valueStyle}>{ROTATION_DEGREE_LABELS[rotation]}</span>
                    </div>

                    <div style={{height: '1px', backgroundColor: 'rgba(255,255,255,0.1)', margin: '0 -2px'}}/>

                    <div style={{display: 'flex', alignItems: 'center', gap: '4px'}}>
                        <button
                            title="Decrease exposure"
                            className="button icon-button"
                            onClick={handleExposureDown}
                            disabled={isLoading || exposureMode !== 'MANUAL' || exposure <= EXPOSURE_MIN}
                            style={btnStyle}
                        >
                            <span className="icon minus-icon" style={{fontSize: 16}}/>
                        </button>
                        <button
                            title="Increase exposure"
                            className="button icon-button"
                            onClick={handleExposureUp}
                            disabled={isLoading || exposureMode !== 'MANUAL' || exposure >= EXPOSURE_MAX}
                            style={btnStyle}
                        >
                            <span className="icon plus-icon" style={{fontSize: 16}}/>
                        </button>
                        <span style={valueStyle}>{exposureLabel}</span>
                    </div>

                    <div style={{display: 'flex', alignItems: 'center', gap: '4px'}}>
                        <button
                            title={exposureMode === 'AUTO' ? 'Switch to manual exposure' : 'Switch to auto exposure'}
                            className="button icon-button"
                            onClick={handleAutoExposure}
                            disabled={isLoading}
                            style={exposureMode === 'AUTO' ? btnActiveStyle : btnStyle}
                        >
                            <span className="icon settings-icon" style={{fontSize: 16}}/>
                        </button>
                        <button
                            title="Recommend exposure for this camera"
                            className="button icon-button"
                            onClick={handleRecommendExposure}
                            disabled={isLoading}
                            style={btnStyle}
                        >
                            <span className="icon warning-icon" style={{fontSize: 16}}/>
                        </button>
                    </div>

                    <div style={{height: '1px', backgroundColor: 'rgba(255,255,255,0.1)', margin: '0 -2px'}}/>

                    <div style={{display: 'flex', alignItems: 'center', gap: '4px'}}>
                        <button
                            title={isAutoApply ? 'Auto-apply on — changes send automatically' : 'Auto-apply off — click apply to send'}
                            className="button icon-button"
                            onClick={() => dispatch(autoApplyToggled())}
                            style={isAutoApply ? btnActiveStyle : btnStyle}
                        >
                            <span className="icon loop-icon" style={{fontSize: 16}}/>
                        </button>
                        {!isAutoApply && (
                            <button
                                title="Apply changes to camera"
                                className="button icon-button"
                                onClick={handleApply}
                                disabled={isApplying}
                                style={btnStyle}
                            >
                                {isApplying
                                    ? <span className="icon loader-icon" style={{fontSize: 16}}/>
                                    : <span className="icon upToDate-icon" style={{fontSize: 16}}/>}
                            </button>
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
