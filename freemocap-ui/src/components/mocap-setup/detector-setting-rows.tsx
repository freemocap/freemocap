// The skeleton detector's setting rows, shared by the posthoc Mocap processing window and the realtime processing
// controls. Everything arrives through props: the caller owns the store, the server's provider list and the DLC dialog.
import type {ReactNode} from 'react';
import SettingRow from '@/components/common/settings-layout/setting-row';
import SettingSelectInput from '@/components/common/settings-layout/setting-select-input';
import ValueSelector from '@/components/ui-components/ValueSelector';
import {type MediapipeModelComplexity, RTMPOSE_MODELS, type RTMPoseModelName} from '@/store/slices/mocap';
import type {RealtimeDetectorType} from '@/store/slices/realtime/realtime-types';
import type {ExecutionProviderName} from '@/types/execution-provider';

export const MEDIAPIPE_COMPLEXITIES: { label: string; value: MediapipeModelComplexity }[] = [
    {label: "Heavy", value: "heavy"},
    {label: "Full", value: "full"},
    {label: "Lite", value: "lite"},
];

export const DETECTOR_INFO = {
    title: "Skeleton detector",
    text: <>
        <p><strong>RTMW</strong> — body, hand and face keypoints from the wholebody model, following YOLOX person detection.</p>
        <p><strong>MediaPipe</strong> — separate pose, cropped hand and face detectors.</p>
        <p><strong>RTMW + MediaPipe hands</strong> — RTMW body and face with separately cropped MediaPipe hands. The confidence settings below apply to those hands.</p>
        <p><em>The detector decides which parameters below apply.</em></p>
    </>,
};

export const EXECUTION_PROVIDER_INFO = {
    title: 'Execution provider',
    text: 'Auto retains the pipeline default. Choices are advertised by the server runtime; session startup verifies the selected provider can load.',
};

export const MODEL_INFO = {
    title: "Model",
    text: <>
        <p><strong>High Res</strong> estimates from a larger input crop: more accurate on small or distant people, and slower.</p>
        <p><strong>Fast</strong> trades accuracy for runtime. <strong>Default</strong> sits between the two.</p>
    </>,
};

export const COMPLEXITY_INFO = {
    title: "Pose model size",
    text: <>
        <p><strong>Heavy</strong> is the most accurate and the slowest; <strong>Lite</strong> is the fastest on CPU; <strong>Full</strong> sits between them.</p>
        <p><em>All three return the same keypoints — only the estimation quality and runtime change.</em></p>
    </>,
};

const DLC_MODEL_INFO = {
    title: 'DLC model',
    text: <p>The exported DeepLabCut model to run on every camera frame.</p>,
};

export const CONFIDENCE_INFO = {
    title: "Confidence threshold",
    text: <>
        <p>Keypoints detected below this confidence are <strong>discarded before triangulation</strong>, so they never contribute to a 3D estimate.</p>
        <p><em>Raise it to reject noisy detections; lower it to keep sparse ones and rely on outlier rejection instead.</em></p>
    </>,
};

export const DETECTION_CONFIDENCE_INFO = {
    title: "Detection confidence",
    text: <>
        <p>The detection confidence required by the selected MediaPipe detectors; for the combined preset this applies to hand detection.</p>
        <p><em>Raise it if it locks onto things that are not people; lower it if it fails to pick up a person who is partly out of frame.</em></p>
    </>,
};

export const PRESENCE_CONFIDENCE_INFO = {
    title: "Presence confidence",
    text: <>
        <p>The presence confidence required by the selected MediaPipe pose or hand detector.</p>
        <p><em>Raise it to reject less certain detections; lower it to accept more uncertain detections.</em></p>
    </>,
};

export const TRACKING_CONFIDENCE_INFO = {
    title: "Tracking confidence",
    text: <>
        <p>The tracking confidence required by the selected MediaPipe detectors before requesting detection again.</p>
        <p><em>Lower values hold the track through occlusions; higher values re-detect sooner when the track drifts.</em></p>
    </>,
};

export const CHARUCO_INFO = {
    title: "Charuco board detection settings",
    text: <>
        <p><strong>Board layout and square size</strong> come from Charuco Board Settings.</p>
        <p><strong>AUTO</strong> selects the layout. You must still enter the <em>measured square size.</em></p>
    </>,
};

export const BOARD_GROUP_INFO = {
    title: "Board",
    text: <>
        <p>A Charuco board detected alongside the skeleton, reconstructed as its own rigid object in the same capture volume.</p>
        <p><em>Useful as a known reference for the ground plane and for checking reconstruction accuracy against a real measured object.</em></p>
    </>,
};

interface Info {title: string; text: ReactNode}

/**
 * What the realtime Skeleton Setup dialog said under its detector choice, word for word. The realtime rows show the
 * selected detector's note in the explanations of the rows it is about: the detector and, where the detector has one,
 * the execution provider. The posthoc explanations stay as they are.
 */
const REALTIME_DETECTOR_NOTES = {
    rtmpose: '133 keypoints (body, hands, face) via YOLOX + RTMW. Uses GPU batched inference when available.',
    mediapipe: 'Body + hands + face via MediaPipe. CPU-only; runs per-camera without GPU batching.',
    rtmw_mediapipe_hands: 'RTMW body and face with cropped MediaPipe hands. The execution provider applies to RTMW; MediaPipe hands run on CPU.',
    rtmw_onnx_hands: 'Experimental RTMW body and face with ONNX palm and hand models. Uses CUDA; CPU is also supported. Compare hand quality with the MediaPipe hands option.',
} satisfies Partial<Record<RealtimeDetectorType, string>>;
/** And what it said above the confidences of the two presets that add hand detectors to RTMW. */
const REALTIME_HANDS_NOTE = 'The confidence settings below apply to the hands.';

/** An explanation with a note as one more paragraph after its own. */
const withNote = (info: Info, note: string): Info =>
    ({title: info.title, text: <>{typeof info.text === 'string' ? <p>{info.text}</p> : info.text}<p>{note}</p></>});
/** An explanation with each detector's note, by detector. */
const withDetectorNotes = (info: Info): Map<string, Info> =>
    new Map(Object.entries(REALTIME_DETECTOR_NOTES).map(([detector, note]) => [detector, withNote(info, note)]));

// Built once, so a row's explanation is the same object on every render.
const REALTIME_DETECTOR_INFO = withDetectorNotes(DETECTOR_INFO);
const REALTIME_PROVIDER_INFO = withDetectorNotes(EXECUTION_PROVIDER_INFO);
const REALTIME_HANDS_INFO = {
    detection: withNote(DETECTION_CONFIDENCE_INFO, REALTIME_HANDS_NOTE),
    presence: withNote(PRESENCE_CONFIDENCE_INFO, REALTIME_HANDS_NOTE),
    tracking: withNote(TRACKING_CONFIDENCE_INFO, REALTIME_HANDS_NOTE),
};

export interface DetectorSettingsValue {
    detector: RealtimeDetectorType; model: RTMPoseModelName; provider: ExecutionProviderName | null; confidence: number;
    poseModelSize: MediapipeModelComplexity; detectionConfidence: number; presenceConfidence: number; trackingConfidence: number;
}

interface DetectorSettingRowsProps {
    value: DetectorSettingsValue;
    /** Receives only the fields a control changes. */
    onChange: (change: Partial<DetectorSettingsValue>) => void;
    detectors: readonly {label: string; value: RealtimeDetectorType}[];
    /** The execution providers to offer; the one with no value is Auto. */
    providerOptions: readonly {label: string; value: ExecutionProviderName | null}[];
    /** The control of the "DLC model" row: the caller's way into the DLC settings. */
    dlcControl: ReactNode;
    context: 'posthoc' | 'realtime';
    /** 'key' is the detector and its model row: two rows whatever the detector. 'all' is every row the detector has. */
    rows: 'all' | 'key';
    /** What the rows belong to is switched off: they stay on screen, dimmed. */
    inactive?: boolean;
}

export function DetectorSettingRows({value, onChange, detectors, providerOptions, dlcControl, context, rows, inactive = false}: DetectorSettingRowsProps) {
    const {detector} = value;
    const all = rows === 'all';
    const rtmw = detector === 'rtmpose' || detector === 'rtmw_mediapipe_hands' || detector === 'rtmw_onnx_hands';
    // MediaPipe's confidences; the two hybrid presets take them for their hand detectors.
    const mediapipe = detector === 'mediapipe' || detector === 'rtmw_mediapipe_hands' || detector === 'rtmw_onnx_hands';
    // The ONNX hand models run on CUDA or CPU only, so selecting their preset also selects CUDA.
    const providers = detector === 'rtmw_onnx_hands'
        ? providerOptions.filter(option => option.value === 'cuda' || option.value === 'cpu') : providerOptions;
    const realtime = context === 'realtime';
    const detectorInfo = (realtime && REALTIME_DETECTOR_INFO.get(detector)) || DETECTOR_INFO;
    const providerInfo = (realtime && REALTIME_PROVIDER_INFO.get(detector)) || EXECUTION_PROVIDER_INFO;
    // The presets that add hand detectors to RTMW pass these confidences to the hands, and realtime says so.
    const handsNote = realtime && rtmw && mediapipe;

    return <>
        {/* In the posthoc section the detector reframes every row beneath it, so it leads the section. */}
        <SettingRow promoted={context === 'posthoc'} inactive={inactive} label="Skeleton detector" info={detectorInfo}
            control={<SettingSelectInput label="Skeleton detector" value={detector} options={detectors}
                onChange={(selected: RealtimeDetectorType) =>
                    onChange(selected === 'rtmw_onnx_hands' ? {detector: selected, provider: 'cuda'} : {detector: selected})}/>}/>

        {all && rtmw && <SettingRow inactive={inactive} label="Execution provider" info={providerInfo}
            control={<SettingSelectInput label="Execution provider" value={value.provider ?? 'auto'}
                options={providers.map(option => ({...option, value: option.value ?? 'auto' as const}))}
                onChange={(provider: ExecutionProviderName | 'auto') => onChange({provider: provider === 'auto' ? null : provider})}/>}/>}

        {/* Every detector has one model row, so the key rows are two rows whatever the detector. */}
        {rtmw && <SettingRow inactive={inactive} label="Model" info={MODEL_INFO}
            control={<SettingSelectInput label="RTMPose model" value={value.model}
                options={RTMPOSE_MODELS} onChange={(model: RTMPoseModelName) => onChange({model})}/>}/>}
        {detector === 'mediapipe' && <SettingRow inactive={inactive} label="Pose model size" info={COMPLEXITY_INFO}
            control={<SettingSelectInput label="Pose model size" value={value.poseModelSize}
                options={MEDIAPIPE_COMPLEXITIES} onChange={(poseModelSize: MediapipeModelComplexity) => onChange({poseModelSize})}/>}/>}
        {detector === 'dlc' && <SettingRow inactive={inactive} label="DLC model" info={DLC_MODEL_INFO} control={dlcControl}/>}

        {all && rtmw && <SettingRow inactive={inactive} label="Confidence threshold" info={CONFIDENCE_INFO}
            control={<ValueSelector ariaLabel="Confidence threshold" value={value.confidence} min={0} max={1}
                step={realtime ? 0.0005 : 0.001} unit="" onChange={confidence => onChange({confidence})}/>}/>}

        {all && mediapipe && <>
            <SettingRow inactive={inactive} label="Detection confidence"
                info={handsNote ? REALTIME_HANDS_INFO.detection : DETECTION_CONFIDENCE_INFO}
                control={<ValueSelector ariaLabel="Detection confidence" value={value.detectionConfidence} min={0} max={1} step={0.05}
                    unit="" onChange={detectionConfidence => onChange({detectionConfidence})}/>}/>
            <SettingRow inactive={inactive} label="Presence confidence"
                info={handsNote ? REALTIME_HANDS_INFO.presence : PRESENCE_CONFIDENCE_INFO}
                control={<ValueSelector ariaLabel="Presence confidence" value={value.presenceConfidence} min={0} max={1} step={0.05}
                    unit="" onChange={presenceConfidence => onChange({presenceConfidence})}/>}/>
            {/* The ONNX hand detector takes no tracking confidence. */}
            {detector !== 'rtmw_onnx_hands' && <SettingRow inactive={inactive} label="Tracking confidence"
                info={handsNote ? REALTIME_HANDS_INFO.tracking : TRACKING_CONFIDENCE_INFO}
                control={<ValueSelector ariaLabel="Tracking confidence" value={value.trackingConfidence} min={0} max={1} step={0.05}
                    unit="" onChange={trackingConfidence => onChange({trackingConfidence})}/>}/>}
        </>}
    </>;
}
