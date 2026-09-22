import {useEffect} from 'react';
import {useAppSelector} from '@/store';
import type {CalibrationScene, LoadedCalibration} from '@/store/slices/calibration/calibration-types';

interface ReferenceFrameTarget {
    postMessage(message: {type: 'calibrationScene'; data: CalibrationScene}): void;
}

export function useReferenceFrameForwarder(
    target: ReferenceFrameTarget, isLive: boolean, calibration: LoadedCalibration | null,
): void {
    const transform = useAppSelector(state => state.realtime.pipelineConfig.aggregator_config.reference_transform);
    useEffect(() => {
        target.postMessage({
            type: 'calibrationScene',
            data: {calibration, referenceTransform: isLive ? transform?.matrix ?? null : null},
        });
    }, [target, isLive, transform, calibration]);
}
