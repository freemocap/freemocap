import type {DetectorType} from '@/store/slices/mocap';

// Shared presentation choices for the capture popup, pipeline tree and post-hoc setup.
export const DETECTOR_OPTIONS: {label: string; value: DetectorType}[] = [
    {label: 'RTMW', value: 'rtmpose'},
    {label: 'MediaPipe', value: 'mediapipe'},
    {label: 'RTMW + MediaPipe hands', value: 'rtmw_mediapipe_hands'},
    {label: 'DLC', value: 'dlc'},
];
