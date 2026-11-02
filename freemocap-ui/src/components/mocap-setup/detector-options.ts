import type {DetectorType} from '@/store/slices/mocap';
import type {RealtimeDetectorType} from '@/store/slices/realtime/realtime-types';

// Shared presentation choices for the capture popup, pipeline tree and post-hoc setup.
export const DETECTOR_OPTIONS: {label: string; value: DetectorType}[] = [
    {label: 'RTMW', value: 'rtmpose'},
    {label: 'MediaPipe', value: 'mediapipe'},
    {label: 'RTMW + MediaPipe hands', value: 'rtmw_mediapipe_hands'},
    {label: 'DLC', value: 'dlc'},
];

// Experimental live comparison only; posthoc choices retain the supported presets.
export const REALTIME_DETECTOR_OPTIONS: {label: string; value: RealtimeDetectorType}[] = [
    ...DETECTOR_OPTIONS,
    {label: 'RTMW + ONNX hands (experimental)', value: 'rtmw_onnx_hands'},
];
