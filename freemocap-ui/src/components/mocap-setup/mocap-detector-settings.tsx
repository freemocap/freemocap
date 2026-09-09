import {useAppDispatch, useAppSelector} from '@/store/hooks';
import {mocapCharucoTrackingChanged} from '@/store/slices/mocap';
import ValueSelector from '@/components/ui-components/ValueSelector';
import SettingRow from '@/components/common/settings-layout/setting-row';
import SettingsGroupHeading from '@/components/common/settings-layout/settings-group-heading';
import SettingSelectInput from '@/components/common/settings-layout/setting-select-input';
import SettingToggleSwitch from '@/components/common/settings-layout/setting-toggle-switch';
import {useMocap} from '@/hooks/useMocap';
import {
    DetectorType,
    MediapipeModelComplexity,
    RTMPOSE_MODELS,
    RTMPoseModelName,
} from '@/store/slices/mocap';

const DETECTORS: { label: string; value: DetectorType }[] = [
    {label: "RTMPose", value: "rtmpose"},
    {label: "MediaPipe Holistic", value: "mediapipe"},
];

const MEDIAPIPE_COMPLEXITIES: { label: string; value: MediapipeModelComplexity }[] = [
    {label: "Heavy", value: "heavy"},
    {label: "Full", value: "full"},
    {label: "Lite", value: "lite"},
];

const DETECTOR_INFO = {
    title: "Skeleton detector",
    text: <>
        <p><strong>RTMPose</strong> — 133 keypoints (body, hands, face) via YOLOX person detection followed by RTMPose estimation. Recommended for best accuracy.</p>
        <p><strong>MediaPipe Holistic</strong> — body (33) + hands (21 each) + face (60) in a single pass. Faster on CPU, fewer total keypoints.</p>
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
        <p>How confident MediaPipe must be that it has found a person before it starts estimating landmarks for that frame.</p>
        <p><em>Raise it if it locks onto things that are not people; lower it if it fails to pick up a person who is partly out of frame.</em></p>
    </>,
};

const PRESENCE_CONFIDENCE_INFO = {
    title: "Presence confidence",
    text: <>
        <p>How confident MediaPipe must be that an individual landmark is actually present before reporting it.</p>
        <p><em>This governs single points rather than the whole person, so it is what thins out occluded hands and feet.</em></p>
    </>,
};

const TRACKING_CONFIDENCE_INFO = {
    title: "Tracking confidence",
    text: <>
        <p>How confident MediaPipe must be that it is still following the same person from the previous frame. Below this it stops tracking and runs person detection again.</p>
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
        mediapipeModelComplexity,
        mediapipeDetectionConfidence,
        mediapipePresenceConfidence,
        mediapipeTrackingConfidence,
        setDetectorType,
        setRtmPoseModelName,
        setRtmPoseConfidenceThreshold,
        setMediapipeModelComplexity,
        setMediapipeDetectionConfidence,
        setMediapipePresenceConfidence,
        setMediapipeTrackingConfidence,
    } = useMocap();

    const detector = detectorType ?? "rtmpose";

    return <>
        {/* The detector reframes every row beneath it, so it leads the section. */}
        <SettingRow promoted label="Skeleton detector" info={DETECTOR_INFO}
            control={<SettingSelectInput label="Skeleton detector" value={detector} options={DETECTORS}
                onChange={setDetectorType}/>}/>

        {detector === "rtmpose" && <>
            <SettingRow label="Model" info={MODEL_INFO}
                control={<SettingSelectInput label="RTMPose model" value={rtmPoseModelName ?? "rtmw-x-l_384x288"}
                    options={RTMPOSE_MODELS} onChange={(value: RTMPoseModelName) => setRtmPoseModelName(value)}/>}/>
            <SettingRow label="Confidence threshold" info={CONFIDENCE_INFO}
                control={<ValueSelector value={rtmPoseConfidenceThreshold ?? 0.004} min={0} max={1} step={0.001}
                    unit="" onChange={setRtmPoseConfidenceThreshold}/>}/>
        </>}

        {detector === "mediapipe" && <>
            <SettingRow label="Pose model size" info={COMPLEXITY_INFO}
                control={<SettingSelectInput label="Pose model size" value={mediapipeModelComplexity ?? "heavy"}
                    options={MEDIAPIPE_COMPLEXITIES} onChange={setMediapipeModelComplexity}/>}/>
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
