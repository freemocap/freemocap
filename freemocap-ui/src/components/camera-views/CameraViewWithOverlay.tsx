import React, {useState} from 'react';
import {Box, CircularProgress, IconButton, Tooltip, Typography} from '@mui/material';
import RotateRightIcon from '@mui/icons-material/RotateRight';
import BrightnessHighIcon from '@mui/icons-material/BrightnessHigh';
import BrightnessLowIcon from '@mui/icons-material/BrightnessLow';
import WbIncandescentIcon from '@mui/icons-material/WbIncandescent';
import BrightnessAutoIcon from '@mui/icons-material/BrightnessAuto';
import SyncIcon from '@mui/icons-material/Sync';
import SyncDisabledIcon from '@mui/icons-material/SyncDisabled';
import CheckIcon from '@mui/icons-material/Check';
import {useAppDispatch, useAppSelector} from '@/store/hooks';
import {selectCameraById, selectIsLoading, selectAutoApply} from '@/store/slices/cameras/cameras-selectors';
import {cameraDesiredConfigUpdated, autoApplyToggled} from '@/store/slices/cameras/cameras-slice';
import {camerasConnectOrUpdate} from '@/store/slices/cameras/cameras-thunks';
import {ROTATION_DEGREE_LABELS, ROTATION_OPTIONS, RotationValue} from '@/store/slices/cameras/cameras-types';
import {CameraView} from './CameraView';

const EXPOSURE_MIN = -13;
const EXPOSURE_MAX = -4;

interface CameraViewWithOverlayProps {
    cameraIndex: number;
    cameraId: string;
}

export const CameraViewWithOverlay: React.FC<CameraViewWithOverlayProps> = ({cameraIndex, cameraId}) => {
    const dispatch = useAppDispatch();
    const [hovered, setHovered] = useState(false);
    const [isApplying, setIsApplying] = useState(false);
    const camera = useAppSelector(state => selectCameraById(state, cameraId));
    const isLoading = useAppSelector(selectIsLoading);
    const isAutoApply = useAppSelector(selectAutoApply);
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
        // Server computes recommended exposure and returns MANUAL mode + value in the response.
        // The fulfilled handler in cameras-slice normalizes desiredConfig from the server response.
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
        <Box
            sx={{position: 'relative', width: '100%', height: '100%'}}
            onMouseEnter={() => setHovered(true)}
            onMouseLeave={() => setHovered(false)}
        >
            <CameraView cameraIndex={cameraIndex} cameraId={cameraId} maxWidth/>

            {hovered && (
                <Box
                    sx={{
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
                    }}
                >
                    {/* Rotation row */}
                    <Box sx={{display: 'flex', alignItems: 'center', gap: '6px'}}>
                        <Tooltip title="Rotate 90° clockwise" placement="left" disableInteractive enterDelay={600}>
                            <IconButton
                                size="small"
                                onClick={handleRotate}
                                disabled={isLoading}
                                sx={btnSx}
                            >
                                <RotateRightIcon sx={{fontSize: 16}}/>
                            </IconButton>
                        </Tooltip>
                        <Typography sx={valueSx}>{ROTATION_DEGREE_LABELS[rotation]}</Typography>
                    </Box>

                    <Box sx={dividerSx}/>

                    {/* Exposure +/- row */}
                    <Box sx={{display: 'flex', alignItems: 'center', gap: '4px'}}>
                        <Tooltip title="Decrease exposure" placement="left" disableInteractive enterDelay={600}>
                            <span>
                                <IconButton
                                    size="small"
                                    onClick={handleExposureDown}
                                    disabled={isLoading || exposureMode !== 'MANUAL' || exposure <= EXPOSURE_MIN}
                                    sx={btnSx}
                                >
                                    <BrightnessLowIcon sx={{fontSize: 16}}/>
                                </IconButton>
                            </span>
                        </Tooltip>
                        <Tooltip title="Increase exposure" placement="left" disableInteractive enterDelay={600}>
                            <span>
                                <IconButton
                                    size="small"
                                    onClick={handleExposureUp}
                                    disabled={isLoading || exposureMode !== 'MANUAL' || exposure >= EXPOSURE_MAX}
                                    sx={btnSx}
                                >
                                    <BrightnessHighIcon sx={{fontSize: 16}}/>
                                </IconButton>
                            </span>
                        </Tooltip>
                        <Typography sx={valueSx}>{exposureLabel}</Typography>
                    </Box>

                    {/* Exposure mode row */}
                    <Box sx={{display: 'flex', alignItems: 'center', gap: '4px'}}>
                        <Tooltip
                            title={exposureMode === 'AUTO' ? 'Switch to manual exposure' : 'Switch to auto exposure'}
                            placement="left"
                            disableInteractive
                            enterDelay={600}
                        >
                            <IconButton
                                size="small"
                                onClick={handleAutoExposure}
                                disabled={isLoading}
                                sx={exposureMode === 'AUTO' ? btnActiveSx : btnSx}
                            >
                                <BrightnessAutoIcon sx={{fontSize: 16}}/>
                            </IconButton>
                        </Tooltip>
                        <Tooltip
                            title="Recommend exposure for this camera"
                            placement="left"
                            disableInteractive
                            enterDelay={600}
                        >
                            <IconButton
                                size="small"
                                onClick={handleRecommendExposure}
                                disabled={isLoading}
                                sx={btnSx}
                            >
                                <WbIncandescentIcon sx={{fontSize: 16}}/>
                            </IconButton>
                        </Tooltip>
                    </Box>

                    <Box sx={dividerSx}/>

                    {/* Auto-apply row */}
                    <Box sx={{display: 'flex', alignItems: 'center', gap: '4px'}}>
                        <Tooltip
                            title={isAutoApply ? 'Auto-apply on — changes send automatically' : 'Auto-apply off — click apply to send'}
                            placement="left"
                            disableInteractive
                            enterDelay={600}
                        >
                            <IconButton
                                size="small"
                                onClick={() => dispatch(autoApplyToggled())}
                                sx={isAutoApply ? btnActiveSx : btnSx}
                            >
                                {isAutoApply ? <SyncIcon sx={{fontSize: 16}}/> : <SyncDisabledIcon sx={{fontSize: 16}}/>}
                            </IconButton>
                        </Tooltip>
                        {!isAutoApply && (
                            <Tooltip title="Apply changes to camera" placement="left" disableInteractive enterDelay={600}>
                                <span>
                                    <IconButton
                                        size="small"
                                        onClick={handleApply}
                                        disabled={isApplying}
                                        sx={btnSx}
                                    >
                                        {isApplying
                                            ? <CircularProgress size={16} sx={{color: 'inherit'}}/>
                                            : <CheckIcon sx={{fontSize: 16}}/>}
                                    </IconButton>
                                </span>
                            </Tooltip>
                        )}
                    </Box>
                </Box>
            )}
        </Box>
    );
};

const btnSx = {
    width: 24,
    height: 24,
    padding: '3px',
    color: 'rgba(255,255,255,0.8)',
    borderRadius: '5px',
    outline: 'none',
    '&:hover': {
        backgroundColor: 'rgba(255,255,255,0.18)',
        color: '#fff',
    },
    '&:focus': {
        outline: 'none',
    },
    '&.Mui-disabled': {
        color: 'rgba(255,255,255,0.2)',
    },
} as const;

const btnActiveSx = {
    ...btnSx,
    color: '#fff',
    backgroundColor: 'rgba(255,255,255,0.2)',
    '&:focus': {
        outline: 'none',
    },
} as const;

const valueSx = {
    fontSize: 11,
    fontFamily: 'monospace',
    color: 'rgba(255,255,255,0.85)',
    minWidth: '28px',
    lineHeight: 1,
} as const;

const dividerSx = {
    height: '1px',
    backgroundColor: 'rgba(255,255,255,0.1)',
    mx: '-2px',
} as const;
