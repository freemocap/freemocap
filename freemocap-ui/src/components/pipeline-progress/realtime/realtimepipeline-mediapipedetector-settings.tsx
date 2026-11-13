import {DlcModelSettings} from '@/components/mocap-setup/dlc-model-settings';
import React, {useCallback} from 'react';
import TrackerSettingsDialog from '@/components/mocap-setup/tracker-settings-dialog';
import ValueSelector from '@/components/ui-components/ValueSelector';
import SettingRow from '@/components/common/settings-layout/setting-row';
import SettingSelectInput from '@/components/common/settings-layout/setting-select-input';
import {
    COMPLEXITY_INFO,
    CONFIDENCE_INFO,
    DETECTION_CONFIDENCE_INFO,
    MEDIAPIPE_COMPLEXITIES,
    MODEL_INFO,
    PRESENCE_CONFIDENCE_INFO,
    TRACKING_CONFIDENCE_INFO,
} from '@/components/mocap-setup/detector-setting-rows';
import { useRealtimePipelineSync } from '@/hooks/useRealtimePipelineSync';
import { useExecutionProviderOptions } from '@/hooks/useExecutionProviderOptions';
import { ExecutionProviderName, MediapipeModelComplexity, RTMPOSE_MODELS, RTMPoseModelName } from '@/store/slices/mocap';
import { CameraNodeConfig, RealtimeDetectorType } from '@/store/slices/realtime/realtime-types';
import { REALTIME_DETECTOR_OPTIONS } from '@/components/mocap-setup/detector-options';
import './realtime-settings.css';

interface RTPSkeletonSetupProps {
    open: boolean;
    onClose: () => void;
}

const DETECTOR_INFO = {
    title: 'Skeleton detector',
    text: <>
        <p><strong>RTMW</strong> — 133 keypoints (body, hands, face) via YOLOX + RTMW. Uses GPU batched inference when available.</p>
        <p><strong>MediaPipe</strong> — body, hands and face. CPU only; runs per camera without GPU batching.</p>
        <p><strong>RTMW + MediaPipe hands</strong> — RTMW body and face with cropped MediaPipe hands.</p>
        <p><strong>DLC</strong> — a DeepLabCut model, prepared and selected below.</p>
        <p><strong>RTMW + ONNX hands (experimental)</strong> — RTMW body and face with ONNX palm and hand models.
            Compare hand quality with the MediaPipe hands option.</p>
        <p><em>The detector decides which settings below apply.</em></p>
    </>,
};

const PROVIDER_NOTE: Partial<Record<RealtimeDetectorType, string>> = {
    rtmw_mediapipe_hands: 'The execution provider applies to RTMW; MediaPipe hands run on CPU.',
    rtmw_onnx_hands: 'RTMW and the ONNX hand models run on CUDA; CPU is also supported.',
};

const providerInfo = (detector: RealtimeDetectorType) => ({
    title: 'Execution provider',
    text: <>
        <p>Auto retains the pipeline default. Choices are advertised by the server runtime; session startup
            verifies the selected provider can load.</p>
        {PROVIDER_NOTE[detector] && <p><em>{PROVIDER_NOTE[detector]}</em></p>}
    </>,
});

const RTMW_DETECTORS: readonly RealtimeDetectorType[] = ['rtmpose', 'rtmw_mediapipe_hands', 'rtmw_onnx_hands'];
const MEDIAPIPE_DETECTORS: readonly RealtimeDetectorType[] = ['mediapipe', 'rtmw_mediapipe_hands', 'rtmw_onnx_hands'];

const RTPSkeletonSetup: React.FC<RTPSkeletonSetupProps> = ({ open, onClose }) => {
    const { pipelineConfig, cameraNodeConfig, applyOrUpdatePipelineConfig } = useRealtimePipelineSync();

    const executionProvider = pipelineConfig.skeleton_inference_node_config?.execution_provider ?? null;
    const availableProviderOptions = useExecutionProviderOptions(executionProvider);
    const executionProviderOptions = cameraNodeConfig.detector_type === 'rtmw_onnx_hands'
        ? availableProviderOptions.filter(({value}) => value === 'cpu' || value === 'cuda')
        : availableProviderOptions;

    const handleExecutionProviderChange = useCallback(
        (provider: ExecutionProviderName | null) => {
            applyOrUpdatePipelineConfig({
                ...pipelineConfig,
                skeleton_inference_node_config: { ...pipelineConfig.skeleton_inference_node_config, execution_provider: provider },
            });
        },
        [applyOrUpdatePipelineConfig, pipelineConfig]
    );

    const detectorType: RealtimeDetectorType = cameraNodeConfig.detector_type ?? "rtmpose";

    const handleCameraNodeUpdate = useCallback(
        (updates: Partial<CameraNodeConfig>) => {
            applyOrUpdatePipelineConfig({
                ...pipelineConfig,
                camera_node_config: { ...cameraNodeConfig, ...updates },
                skeleton_inference_node_config: updates.detector_type === 'rtmw_onnx_hands'
                    ? {...pipelineConfig.skeleton_inference_node_config, execution_provider: 'cuda'}
                    : pipelineConfig.skeleton_inference_node_config,
            });
        },
        [applyOrUpdatePipelineConfig, pipelineConfig, cameraNodeConfig]
    );

    if (!open) return null;

    return (
        <TrackerSettingsDialog title="Skeleton Setup" onClose={onClose}>
            <div className="realtime-skeleton-setup">
                {/* The detector reframes every row beneath it, so it leads. */}
                <SettingRow promoted label="Skeleton detector" info={DETECTOR_INFO}
                    control={<SettingSelectInput label="Skeleton detector" value={detectorType}
                        options={REALTIME_DETECTOR_OPTIONS}
                        onChange={(value: RealtimeDetectorType) => handleCameraNodeUpdate({ detector_type: value })}/>}/>

                {RTMW_DETECTORS.includes(detectorType) && <>
                    <SettingRow label="Execution provider" info={providerInfo(detectorType)}
                        control={<SettingSelectInput label="Execution provider" value={executionProvider ?? 'auto'}
                            options={executionProviderOptions.map(option => ({...option, value: option.value ?? 'auto' as const}))}
                            onChange={(value: ExecutionProviderName | 'auto') => handleExecutionProviderChange(value === 'auto' ? null : value)}/>}/>
                    <SettingRow label="Model" info={MODEL_INFO}
                        control={<SettingSelectInput label="RTMPose model" value={cameraNodeConfig.rtmpose_model_name ?? "rtmw-x-l_256x192"}
                            options={RTMPOSE_MODELS}
                            onChange={(value: RTMPoseModelName) => handleCameraNodeUpdate({ rtmpose_model_name: value })}/>}/>
                    <SettingRow label="Confidence threshold" info={CONFIDENCE_INFO}
                        control={<ValueSelector ariaLabel="Confidence threshold" value={cameraNodeConfig.rtmpose_confidence_threshold ?? 0.0025}
                            min={0} max={1} step={0.0005} unit=""
                            onChange={(v) => handleCameraNodeUpdate({ rtmpose_confidence_threshold: v })}/>}/>
                </>}

                {MEDIAPIPE_DETECTORS.includes(detectorType) && <>
                    {detectorType === 'mediapipe' && <SettingRow label="Pose model size" info={COMPLEXITY_INFO}
                        control={<SettingSelectInput label="Pose model size" value={cameraNodeConfig.mediapipe_model_complexity ?? "lite"}
                            options={MEDIAPIPE_COMPLEXITIES}
                            onChange={(value: MediapipeModelComplexity) => handleCameraNodeUpdate({ mediapipe_model_complexity: value })}/>}/>}
                    <SettingRow label="Detection confidence" info={DETECTION_CONFIDENCE_INFO}
                        control={<ValueSelector ariaLabel="Detection confidence" value={cameraNodeConfig.mediapipe_detection_confidence ?? 0.5}
                            min={0} max={1} step={0.05} unit=""
                            onChange={(v) => handleCameraNodeUpdate({ mediapipe_detection_confidence: v })}/>}/>
                    <SettingRow label="Presence confidence" info={PRESENCE_CONFIDENCE_INFO}
                        control={<ValueSelector ariaLabel="Presence confidence" value={cameraNodeConfig.mediapipe_presence_confidence ?? 0.5}
                            min={0} max={1} step={0.05} unit=""
                            onChange={(v) => handleCameraNodeUpdate({ mediapipe_presence_confidence: v })}/>}/>
                    {detectorType !== 'rtmw_onnx_hands' && <SettingRow label="Tracking confidence" info={TRACKING_CONFIDENCE_INFO}
                        control={<ValueSelector ariaLabel="Tracking confidence" value={cameraNodeConfig.mediapipe_tracking_confidence ?? 0.5}
                            min={0} max={1} step={0.05} unit=""
                            onChange={(v) => handleCameraNodeUpdate({ mediapipe_tracking_confidence: v })}/>}/>}
                </>}
            </div>

            {detectorType === "dlc" && <DlcModelSettings context="realtime" embedded/>}
        </TrackerSettingsDialog>
    );
};

export default RTPSkeletonSetup;
