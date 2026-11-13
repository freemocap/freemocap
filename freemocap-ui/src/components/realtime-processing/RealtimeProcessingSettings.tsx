import {useState} from 'react';
import {useRealtimePipelineSync} from '@/hooks/useRealtimePipelineSync';
import {useExecutionProviderOptions} from '@/hooks/useExecutionProviderOptions';
import {DetectorSettingRows, type DetectorSettingsValue} from '@/components/mocap-setup/detector-setting-rows';
import {REALTIME_DETECTOR_OPTIONS} from '@/components/mocap-setup/detector-options';
import {DlcModelSettings} from '@/components/mocap-setup/dlc-model-settings';
import TrackerSettingsDialog from '@/components/mocap-setup/tracker-settings-dialog';
import ProcessingOutline from '@/components/mocap-setup/processing-outline';
import StageSection from '@/components/mocap-setup/stage-section';
import type {ProcessingSection} from '@/components/mocap-setup/processing-sections';
import SkeletonAnchorSetting from '@/components/mocap-setup/skeleton-anchor-setting';
import SettingRow from '@/components/common/settings-layout/setting-row';
import SettingToggleSwitch from '@/components/common/settings-layout/setting-toggle-switch';
import {TemporalFilterControls} from '@/components/control-panels/realtime-panel/TemporalFilterControls';
import {StreamingOutputsPanel} from '@/components/control-panels/streaming-outputs/StreamingOutputsPanel';
import './realtime-processing.css';
import '@/components/mocap-setup/mocap-processing.css';

type Section = 'tracking' | 'triangulation' | 'filtering' | 'reconstruction' | 'outputs';

/** Presentation reuses posthoc sections; all commands and observations use the existing realtime interfaces. */
export default function RealtimeProcessingSettings({onClose}: {onClose: () => void}) {
    const [active, setActive] = useState<Section>('tracking');
    const {pipelineConfig, cameraNodeConfig: camera, aggregatorConfig: aggregator, applyOrUpdatePipelineConfig} = useRealtimePipelineSync();
    const provider = pipelineConfig.skeleton_inference_node_config.execution_provider ?? null;
    const providers = useExecutionProviderOptions(provider);
    const value: DetectorSettingsValue = {
        detector: camera.detector_type ?? 'rtmpose', model: camera.rtmpose_model_name ?? 'rtmw-x-l_256x192',
        provider, confidence: camera.rtmpose_confidence_threshold ?? 0.0025,
        poseModelSize: camera.mediapipe_model_complexity ?? 'lite',
        detectionConfidence: camera.mediapipe_detection_confidence ?? 0.5,
        presenceConfidence: camera.mediapipe_presence_confidence ?? 0.5,
        trackingConfidence: camera.mediapipe_tracking_confidence ?? 0.5,
    };
    const changeDetector = (change: Partial<DetectorSettingsValue>) => applyOrUpdatePipelineConfig({
        ...pipelineConfig,
        camera_node_config: {...camera,
            detector_type: change.detector ?? camera.detector_type,
            rtmpose_model_name: change.model ?? camera.rtmpose_model_name,
            rtmpose_confidence_threshold: change.confidence ?? camera.rtmpose_confidence_threshold,
            mediapipe_model_complexity: change.poseModelSize ?? camera.mediapipe_model_complexity,
            mediapipe_detection_confidence: change.detectionConfidence ?? camera.mediapipe_detection_confidence,
            mediapipe_presence_confidence: change.presenceConfidence ?? camera.mediapipe_presence_confidence,
            mediapipe_tracking_confidence: change.trackingConfidence ?? camera.mediapipe_tracking_confidence},
        skeleton_inference_node_config: {...pipelineConfig.skeleton_inference_node_config,
            execution_provider: change.provider !== undefined ? change.provider : provider},
    });
    const toggle = (label: string, enabled: boolean, update: (enabled: boolean) => void) =>
        <SettingToggleSwitch label={label} isToggled={enabled} onToggle={update}/>;
    const sections: ProcessingSection<Section>[] = [
        {id: 'tracking', number: 1, title: '2D tracking', stage: null, summary: null,
            content: <>
                <SettingRow label="Track person" info={{title: 'Track person', text: 'Run the selected person detector on camera images.'}} control={toggle('Track person', camera.skeleton_tracking_enabled,
                    enabled => applyOrUpdatePipelineConfig({...pipelineConfig, camera_node_config: {...camera, skeleton_tracking_enabled: enabled}}))}/>
                <DetectorSettingRows value={value} onChange={changeDetector} detectors={REALTIME_DETECTOR_OPTIONS}
                    providerOptions={providers} dlcControl={<DlcModelSettings context="realtime"/>} context="realtime" rows="all"/>
                <SettingRow label="Track Charuco board" info={{title: 'Track Charuco board', text: 'Detect the configured Charuco board alongside the person tracker.'}} control={toggle('Track Charuco board', camera.charuco_tracking_enabled,
                    enabled => applyOrUpdatePipelineConfig({...pipelineConfig, camera_node_config: {...camera, charuco_tracking_enabled: enabled}}))}/>
            </>},
        {id: 'triangulation', number: 2, title: 'Triangulation', stage: null, summary: null,
            toggle: toggle('Triangulation', aggregator.triangulation_enabled, enabled => applyOrUpdatePipelineConfig({
                ...pipelineConfig, aggregator_config: {...aggregator, triangulation_enabled: enabled}})),
            content: <p className="settings-note">Reconstruct 3D points from matching camera observations using the capture-volume calibration. Configure the calibration in the camera sidebar.</p>},
        {id: 'filtering', number: 3, title: 'Filtering and gap recovery', stage: null, summary: null,
            content: <TemporalFilterControls/>},
        {id: 'reconstruction', number: 4, title: 'Skeleton reconstruction', stage: null, summary: null,
            toggle: toggle('Fit skeleton', aggregator.skeleton_fitting_enabled, enabled => applyOrUpdatePipelineConfig({
                ...pipelineConfig, aggregator_config: {...aggregator, skeleton_fitting_enabled: enabled}})),
            content: <SkeletonAnchorSetting value={aggregator.anchor_segment_name} onChange={anchor_segment_name =>
                applyOrUpdatePipelineConfig({...pipelineConfig, aggregator_config: {...aggregator, anchor_segment_name}})}/>},
        {id: 'outputs', number: null, title: 'Streaming outputs', stage: null, after: true, summary: null,
            content: active === 'outputs' ? <StreamingOutputsPanel/> : null},
    ];
    const selected = sections.find(section => section.id === active)!;
    return <TrackerSettingsDialog title="Real-time processing settings" onClose={onClose}>
        <div className="realtime-processing-layout">
            <ProcessingOutline sections={sections} active={active} playback={false} states={null}
                label="Real-time processing stages" afterTitle="Outputs" onPick={setActive}/>
            <div className="realtime-processing-detail" key={active}>
                <StageSection section={selected} playback={false}>{selected.content}</StageSection>
            </div>
        </div>
    </TrackerSettingsDialog>;
}
