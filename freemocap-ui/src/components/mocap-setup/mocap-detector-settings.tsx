import {DlcModelSettings} from '@/components/mocap-setup/dlc-model-settings';
import {useExecutionProviderOptions} from "@/hooks/useExecutionProviderOptions";
import {useAppDispatch, useAppSelector} from '@/store/hooks';
import {mocapCharucoTrackingChanged} from '@/store/slices/mocap';
import SettingRow from '@/components/common/settings-layout/setting-row';
import SettingsGroupHeading from '@/components/common/settings-layout/settings-group-heading';
import SettingToggleSwitch from '@/components/common/settings-layout/setting-toggle-switch';
import {useMocap} from '@/hooks/useMocap';
import {DETECTOR_OPTIONS} from './detector-options';
import {BOARD_GROUP_INFO, CHARUCO_INFO, DetectorSettingRows, type DetectorSettingsValue} from './detector-setting-rows';

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
    const value: DetectorSettingsValue = {
        detector,
        model: rtmPoseModelName ?? "rtmw-x-l_256x192",
        provider: executionProvider ?? null,
        confidence: rtmPoseConfidenceThreshold ?? 0.4,
        poseModelSize: mediapipeModelComplexity ?? "heavy",
        detectionConfidence: mediapipeDetectionConfidence ?? 0.5,
        presenceConfidence: mediapipePresenceConfidence ?? 0.5,
        trackingConfidence: mediapipeTrackingConfidence ?? 0.5,
    };
    /** Each field the rows report goes to its own setting in the store. */
    const applyChange = (change: Partial<DetectorSettingsValue>) => {
        // Posthoc offers DETECTOR_OPTIONS only, so the realtime-only ONNX hands preset never arrives here.
        if (change.detector === 'rtmw_onnx_hands') return;
        if (change.detector !== undefined) setDetectorType(change.detector);
        if (change.provider !== undefined) setExecutionProvider(change.provider);
        if (change.model !== undefined) setRtmPoseModelName(change.model);
        if (change.confidence !== undefined) setRtmPoseConfidenceThreshold(change.confidence);
        if (change.poseModelSize !== undefined) setMediapipeModelComplexity(change.poseModelSize);
        if (change.detectionConfidence !== undefined) setMediapipeDetectionConfidence(change.detectionConfidence);
        if (change.presenceConfidence !== undefined) setMediapipePresenceConfidence(change.presenceConfidence);
        if (change.trackingConfidence !== undefined) setMediapipeTrackingConfidence(change.trackingConfidence);
    };

    return <>
        <DetectorSettingRows value={value} onChange={applyChange} detectors={DETECTOR_OPTIONS}
            providerOptions={executionProviderOptions} dlcControl={<DlcModelSettings context="posthoc"/>}
            context="posthoc" rows="all"/>

        {detector !== "dlc" && <><SettingsGroupHeading text="Board" info={BOARD_GROUP_INFO}/>
        <SettingRow label="Detect and reconstruct Charuco board" info={CHARUCO_INFO}
            control={<SettingToggleSwitch label="Detect and reconstruct Charuco board" isToggled={detectBoard}
                onToggle={enabled => dispatch(mocapCharucoTrackingChanged(enabled))}/>}/></>}
    </>;
}
