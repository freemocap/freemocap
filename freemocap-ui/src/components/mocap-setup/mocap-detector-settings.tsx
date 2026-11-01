import {useExecutionProviderOptions} from "@/hooks/useExecutionProviderOptions";
import {useAppDispatch, useAppSelector} from '@/store/hooks';
import {mocapCharucoTrackingChanged} from '@/store/slices/mocap';
import ValueSelector from '@/components/ui-components/ValueSelector';
import SettingRow from '@/components/common/settings-layout/setting-row';
import SettingsGroupHeading from '@/components/common/settings-layout/settings-group-heading';
import SettingSelectInput from '@/components/common/settings-layout/setting-select-input';
import SettingToggleSwitch from '@/components/common/settings-layout/setting-toggle-switch';
import {useMocap} from '@/hooks/useMocap';
import {DETECTOR_OPTIONS} from './detector-options';
import {
    DetectorType,
    MediapipeModelComplexity,
    RTMPOSE_MODELS,
    RTMPoseModelName,
    ExecutionProviderName,
} from '@/store/slices/mocap';

const MEDIAPIPE_COMPLEXITIES: { label: string; value: MediapipeModelComplexity }[] = [
    {label: "Heavy", value: "heavy"},
    {label: "Full", value: "full"},
    {label: "Lite", value: "lite"},
];

const DETECTOR_INFO = {
    title: "Skeleton detector",
    text: <>
        <p><strong>RTMW</strong> — body, hand and face keypoints from the wholebody model, following YOLOX person detection.</p>
        <p><strong>MediaPipe</strong> — separate pose, cropped hand and face detectors.</p>
        <p><strong>RTMW + MediaPipe hands</strong> — RTMW body and face with separately cropped MediaPipe hands. The confidence settings below apply to those hands.</p>
        <p><em>The detector decides which parameters below apply.</em></p>
    </>,
};

const MODEL_INFO = {
    title: "Model",
    text: <>
        <p><strong>High Res</strong> estimates from a larger input crop: more accurate on small or distant people, and slower.</p>
        <p><strong>Fast</strong> trades accuracy for runtime. <strong>Default</strong> sits between the two.</p>
    </>,
};

const COMPLEXITY_INFO = {
    title: "Pose model size",
    text: <>
        <p><strong>Heavy</strong> is the most accurate and the slowest; <strong>Lite</strong> is the fastest on CPU; <strong>Full</strong> sits between them.</p>
        <p><em>All three return the same keypoints — only the estimation quality and runtime change.</em></p>
    </>,
};

const CONFIDENCE_INFO = {
    title: "Confidence threshold",
    text: <>
        <p>Keypoints detected below this confidence are <strong>discarded before triangulation</strong>, so they never contribute to a 3D estimate.</p>
        <p><em>Raise it to reject noisy detections; lower it to keep sparse ones and rely on outlier rejection instead.</em></p>
    </>,
};

const DETECTION_CONFIDENCE_INFO = {
    title: "Detection confidence",
    text: <>
        <p>The detection confidence required by the selected MediaPipe detectors; for the combined preset this applies to hand detection.</p>
        <p><em>Raise it if it locks onto things that are not people; lower it if it fails to pick up a person who is partly out of frame.</em></p>
    </>,
};

const PRESENCE_CONFIDENCE_INFO = {
    title: "Presence confidence",
    text: <>
        <p>The presence confidence required by the selected MediaPipe pose or hand detector.</p>
        <p><em>Raise it to reject less certain detections; lower it to accept more uncertain detections.</em></p>
    </>,
};

const TRACKING_CONFIDENCE_INFO = {
    title: "Tracking confidence",
    text: <>
        <p>The tracking confidence required by the selected MediaPipe detectors before requesting detection again.</p>
        <p><em>Lower values hold the track through occlusions; higher values re-detect sooner when the track drifts.</em></p>
    </>,
};

const CHARUCO_INFO = {
    title: "Charuco board detection settings",
    text: <>
        <p><strong>Board layout and square size</strong> come from Charuco Board Settings.</p>
        <p><strong>AUTO</strong> selects the layout. You must still enter the <em>measured square size.</em></p>
    </>,
};

const BOARD_GROUP_INFO = {
    title: "Board",
    text: <>
        <p>A Charuco board detected alongside the skeleton, reconstructed as its own rigid object in the same capture volume.</p>
        <p><em>Useful as a known reference for the ground plane and for checking reconstruction accuracy against a real measured object.</em></p>
    </>,
};

export default function MocapDetectorSettings() {
    const dispatch = useAppDispatch();
    const detectBoard = useAppSelector(state => state.mocap.config.charucoTrackingEnabled);
    const {
        detectorType,
        rtmPoseModelName,
        rtmPoseConfidenceThreshold,
        executionProvider,
        mediapipeModelComplexity,
        mediapipeDetectionConfidence,
        mediapipePresenceConfidence,
        mediapipeTrackingConfidence,
        setDetectorType,
        setRtmPoseModelName,
        setRtmPoseConfidenceThreshold,
        setExecutionProvider,
        setMediapipeModelComplexity,
        setMediapipeDetectionConfidence,
        setMediapipePresenceConfidence,
        setMediapipeTrackingConfidence,
    } = useMocap();
    const executionProviderOptions = useExecutionProviderOptions(executionProvider);

    const detector = detectorType ?? "rtmpose";

    return <>
        {/* The detector reframes every row beneath it, so it leads the section. */}
        <SettingRow promoted label="Skeleton detector" info={DETECTOR_INFO}
            control={<SettingSelectInput label="Skeleton detector" value={detector} options={DETECTOR_OPTIONS}
                onChange={setDetectorType}/>}/>

        {detector !== "mediapipe" && <>
            <SettingRow label="Execution provider" info={{title: 'Execution provider', text: 'Auto retains the pipeline default. Choices are advertised by the server runtime; session startup verifies the selected provider can load.'}}
                control={<SettingSelectInput label="Execution provider" value={executionProvider ?? 'auto'}
                    options={executionProviderOptions.map(option => ({...option, value: option.value ?? 'auto' as const}))}
                    onChange={(value: ExecutionProviderName | 'auto') => setExecutionProvider(value === 'auto' ? null : value)}/>}/>
            <SettingRow label="Model" info={MODEL_INFO}
                control={<SettingSelectInput label="RTMPose model" value={rtmPoseModelName ?? "rtmw-x-l_256x192"}
                    options={RTMPOSE_MODELS} onChange={(value: RTMPoseModelName) => setRtmPoseModelName(value)}/>}/>
            <SettingRow label="Confidence threshold" info={CONFIDENCE_INFO}
                control={<ValueSelector value={rtmPoseConfidenceThreshold ?? 0.4} min={0} max={1} step={0.001}
                    unit="" onChange={setRtmPoseConfidenceThreshold}/>}/>
        </>}

        {detector !== "rtmpose" && <>
            {detector === "mediapipe" && <SettingRow label="Pose model size" info={COMPLEXITY_INFO}
                control={<SettingSelectInput label="Pose model size" value={mediapipeModelComplexity ?? "heavy"}
                    options={MEDIAPIPE_COMPLEXITIES} onChange={setMediapipeModelComplexity}/>}/>}
            <SettingRow label="Detection confidence" info={DETECTION_CONFIDENCE_INFO}
                control={<ValueSelector value={mediapipeDetectionConfidence ?? 0.5} min={0} max={1} step={0.05}
                    unit="" onChange={setMediapipeDetectionConfidence}/>}/>
            <SettingRow label="Presence confidence" info={PRESENCE_CONFIDENCE_INFO}
                control={<ValueSelector value={mediapipePresenceConfidence ?? 0.5} min={0} max={1} step={0.05}
                    unit="" onChange={setMediapipePresenceConfidence}/>}/>
            <SettingRow label="Tracking confidence" info={TRACKING_CONFIDENCE_INFO}
                control={<ValueSelector value={mediapipeTrackingConfidence ?? 0.5} min={0} max={1} step={0.05}
                    unit="" onChange={setMediapipeTrackingConfidence}/>}/>
        </>}

        <SettingsGroupHeading text="Board" info={BOARD_GROUP_INFO}/>
        <SettingRow label="Detect and reconstruct Charuco board" info={CHARUCO_INFO}
            control={<SettingToggleSwitch label="Detect and reconstruct Charuco board" isToggled={detectBoard}
                onToggle={enabled => dispatch(mocapCharucoTrackingChanged(enabled))}/>}/>
    </>;
}
