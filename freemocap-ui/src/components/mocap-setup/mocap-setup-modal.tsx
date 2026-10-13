import React, {type ReactNode, useEffect, useMemo, useRef, useState} from "react";
import CaptureVolumeSettings from './capture-volume-settings';
import CameraGeometrySummary from './camera-geometry-summary';
import ModalWindowControls from '@/components/ui-components/ModalWindowControls';
import ButtonSm from "@/components/ui-components/ButtonSm";
import SubactionHeader from "@/components/ui-components/SubactionHeader";
import SettingRow from '@/components/common/settings-layout/setting-row';
import SettingSelectInput from '@/components/common/settings-layout/setting-select-input';
import SettingsSection from "@/components/common/settings-layout/settings-section";
import SettingsSummaryChip from "@/components/common/settings-layout/settings-summary-chip";

import ProcessingDirectorySettings from "@/components/mocap-setup/mocap-processing-directory";
import PosthocFilterSettings from "@/components/mocap-setup/mocap-postprocess-settings";
import MocapDetectorSettings from "@/components/mocap-setup/mocap-detector-settings";
import MocapBlenderSettings from "@/components/mocap-setup/mocap-blender-settings";
import MocapScientificSettings from './mocap-scientific-settings';
import TriangulationSettings from "@/components/mocap-setup/mocap-triangulation-settings";
import {useMocap} from "@/hooks/useMocap";
import {useAppSelector} from "@/store/hooks";
import {RTMPOSE_MODELS} from "@/store/slices/mocap";
import MocapStageSelection from './mocap-stage-selection';
import {PROCESSING_STAGES, type StageSelection} from '@/services/recording/posthoc-processing';
import {selectBlender} from '@/store/slices/blender';
import {useRecordingCalibrationDefault} from '@/hooks/useRecordingCalibrationDefault';

enum SetupSection {
    Directory = 'Recording directory',
    Stages = 'Processing stages',
    Detectors = 'Detectors',
    CameraGeometry = 'Camera geometry',
    Triangulation = 'Triangulation',
    PostProcessing = 'Post-processing',
    Exports = 'Exports',
    Blender = 'Blender',
}

type MocapMode = "recording" | "playback";

interface MocapSetupModalProps {
    onClose?: () => void;
    mode?: MocapMode;
}

const MocapSetupModal: React.FC<MocapSetupModalProps> = ({onClose, mode = "playback"}) => {
    useRecordingCalibrationDefault(mode === 'playback');
    const {
        canProcessMocapRecording,
        isLoading,
        isRecording,
        mocapRecordingPath,
        dispatchProcessMocapRecording,
        validateDirectory,
    } = useMocap();

    const config = useAppSelector(state => state.mocap.config);
    const blender = useAppSelector(selectBlender);
    const [pipelineImplementation, setPipelineImplementation] = useState<'current' | 'typed_dataflow'>('typed_dataflow');
    const [graphExecutionProvider, setGraphExecutionProvider] = useState<'auto' | 'cpu' | 'cuda'>('auto');
    const [stageSelection, setStageSelection] = useState<StageSelection | null>(null);

    useEffect(() => {
        if (mocapRecordingPath) validateDirectory(mocapRecordingPath);
    }, [mocapRecordingPath, validateDirectory]);

    const processBlockedReason = useMemo((): string | null => {
        if (canProcessMocapRecording) return null;
        if (isRecording) return "Stop recording before processing";
        if (isLoading) return "Processing already in progress";
        if (!mocapRecordingPath) return "Select a recording folder to process";
        return null;
    }, [canProcessMocapRecording, isRecording, isLoading, mocapRecordingPath]);

    const [activeSection, setActiveSection] = useState(SetupSection.Directory);
    const scrollContainerRef = useRef<HTMLDivElement>(null);
    const panels = useRef<Partial<Record<SetupSection, HTMLDivElement>>>({});

    /* Every summary states only what IS. A chip given nothing to say removes
       itself rather than reporting an absence. */
    const detectorSummary = (): ReactNode => {
        if (config.detectorType === "mediapipe") {
            return <SettingsSummaryChip>{`MediaPipe · ${config.mediapipeModelComplexity}`}</SettingsSummaryChip>;
        }
        const model = RTMPOSE_MODELS.find(entry => entry.value === config.rtmPoseModelName);
        return <SettingsSummaryChip>{['RTMPose', model?.label].filter(Boolean).join(' · ')}</SettingsSummaryChip>;
    };

    const recordingName = mocapRecordingPath?.split(/[\\/]/).filter(Boolean).pop() ?? '';

    const sections: {name: SetupSection; summary?: ReactNode; content: ReactNode}[] = [
        {
            name: SetupSection.Directory,
            summary: recordingName
                ? <SettingsSummaryChip tone="path" title={mocapRecordingPath ?? ''}>{recordingName}</SettingsSummaryChip>
                : undefined,
            content: <ProcessingDirectorySettings open onClose={() => {}}/>,
        },
        {
            name: SetupSection.Stages,
            summary: <SettingsSummaryChip>
                {stageSelection
                    ? `from ${PROCESSING_STAGES.find(([stage]) => stage === stageSelection.startStage)?.[1] ?? stageSelection.startStage}`
                    : ''}
            </SettingsSummaryChip>,
            content: <>
                <SettingRow label="Processing pipeline" info={{title: 'Processing pipeline',
                    text: 'Typed data flow graph V1 is the default. It starts at 2D tracking and uses your configured board detection settings. Choose Legacy post hoc pipeline to restart from saved intermediate stages.'}}
                    control={<SettingSelectInput label="Processing pipeline" value={pipelineImplementation}
                        onChange={setPipelineImplementation} options={[
                            {value: 'typed_dataflow', label: 'Typed data flow graph V1'},
                            {value: 'current', label: 'Legacy post hoc pipeline'},
                        ]}/>}/>
                {pipelineImplementation === 'typed_dataflow' && <SettingRow label="Tracking device"
                    info={{title: 'Tracking device', text: 'Automatic uses CUDA when available for RTMPose, otherwise CPU. MediaPipe uses CPU. Requires multiple videos and a calibration; saves annotated videos.'}}
                    control={<SettingSelectInput label="Tracking device" value={graphExecutionProvider}
                        onChange={setGraphExecutionProvider} options={[
                            {value: 'auto', label: 'Automatic'}, {value: 'cuda', label: 'CUDA GPU'}, {value: 'cpu', label: 'CPU'},
                        ]}/>}/>}
                <MocapStageSelection path={mocapRecordingPath} onChange={setStageSelection}/>
            </>,
        },
        {
            name: SetupSection.Detectors,
            summary: <>
                {detectorSummary()}
                <SettingsSummaryChip tone="quiet">{config.charucoTrackingEnabled ? '+ Charuco' : ''}</SettingsSummaryChip>
            </>,
            content: <MocapDetectorSettings/>,
        },
        {
            name: SetupSection.CameraGeometry,
            summary: <CameraGeometrySummary mode={mode}/>,
            content: <CaptureVolumeSettings mode={mode}/>,
        },
        {
            name: SetupSection.Triangulation,
            summary: <SettingsSummaryChip>
                {config.triangulation.use_outlier_rejection
                    ? `outlier rejection · ≥${config.triangulation.minimum_cameras_for_triangulation} cams`
                    : ''}
            </SettingsSummaryChip>,
            content: <TriangulationSettings/>,
        },
        {
            name: SetupSection.PostProcessing,
            summary: <SettingsSummaryChip>
                {config.posthoc_filter.enabled ? `Butterworth · ${config.posthoc_filter.cutoff} Hz · order ${config.posthoc_filter.order}` : 'Filtering off'}
            </SettingsSummaryChip>,
            content: <PosthocFilterSettings/>,
        },
        {
            name: SetupSection.Exports,
            summary: <SettingsSummaryChip>{config.scientificExportAfterProcessing && config.scientificExportFormats?.includes('wide_csv') ? 'Wide CSV after processing' : 'Scientific exports on request'}{config.exportTallCsv ? ' · Tall CSV on' : ''}</SettingsSummaryChip>,
            content: <MocapScientificSettings key={mocapRecordingPath} path={mocapRecordingPath} processing={isLoading || isRecording}/>,
        },
        {
            name: SetupSection.Blender,
            summary: <>
                <SettingsSummaryChip>{blender.exportToBlenderEnabled ? 'Export after processing' : 'Export off'}</SettingsSummaryChip>
                <SettingsSummaryChip tone="quiet">{blender.exportConfig.formats.map(format => format.toUpperCase()).join(' · ')}</SettingsSummaryChip>
            </>,
            content: <MocapBlenderSettings/>,
        },
    ];

    useEffect(() => {
        const observer = new IntersectionObserver(entries => {
            for (const entry of entries) {
                if (!entry.isIntersecting) continue;
                const section = Object.values(SetupSection).find(name => panels.current[name] === entry.target);
                if (section) setActiveSection(section);
            }
        }, {root: scrollContainerRef.current, rootMargin: '0px 0px -65% 0px', threshold: 0});
        Object.values(panels.current).forEach(panel => observer.observe(panel));
        return () => observer.disconnect();
    }, []);

    return <>
        <div className="pos-fixed inset-0 bg-surface-overlay z-10" onClick={onClose}/>
        <div role="dialog" aria-label="Mocap processing" aria-modal="true"
            className="mocap-settings-modal pos-fixed flex flex-col br-2">
            <ModalWindowControls title="Mocap processing"/>
            <div className="mocap-settings-layout flex flex-row flex-1">
                <nav aria-label="Mocap setup sections" className="mocap-settings-navigation flex flex-col">
                    <SubactionHeader text="Mocap setup" className="text-gray"/>
                    {sections.filter(section => mode === 'playback' || section.name !== SetupSection.Stages).map(section => <ButtonSm key={section.name} text={section.name}
                        buttonType={activeSection === section.name ? 'activated' : 'idle'}
                        className="full-width quaternary" textClass="mocap-section-link"
                        onClick={() => {
                            panels.current[section.name]?.scrollIntoView({behavior: 'smooth', block: 'start'});
                            setActiveSection(section.name);
                        }}/>)}
                </nav>
                <div ref={scrollContainerRef} className="mocap-settings-content settings-layout flex-1 overflow-y-auto">
                    {sections.filter(section => mode === 'playback' || section.name !== SetupSection.Stages).map(section => <div key={section.name}
                        ref={element => {
                            if (element) panels.current[section.name] = element;
                            else delete panels.current[section.name];
                        }}>
                        <SettingsSection title={section.name} summary={section.summary}>
                            {section.content}
                        </SettingsSection>
                    </div>)}
                </div>
            </div>
            <footer className="mocap-settings-footer flex flex-col align-end gap-2">
                <div className="mocap-settings-actions flex flex-row gap-2">
                    <ButtonSm text="Cancel" buttonType="quaternary" onClick={onClose}/>
                    {mode === "playback" ? (
                        <ButtonSm text="Process Mocap" textColor="text-white" iconClass="processmocap-icon"
                            buttonType="" className="primary accent"
                            onClick={() => {if (stageSelection) {dispatchProcessMocapRecording({...stageSelection, pipelineImplementation, graphExecutionProvider}); onClose?.();}}}
                            disabled={!canProcessMocapRecording || !stageSelection || (pipelineImplementation === 'typed_dataflow' && stageSelection.startStage !== 'observations')} tooltip tooltipPosition="pos-top"
                            tooltipText={processBlockedReason ?? (pipelineImplementation === 'typed_dataflow' && stageSelection?.startStage !== 'observations' ? "Typed data flow graph V1 starts at 2D tracking. Select Legacy post hoc pipeline to restart from saved stages." : stageSelection ? "Start mocap processing" : "Select a stage to process")}/>
                    ) : (
                        <ButtonSm text="Save" textColor="text-white" buttonType="" className="primary accent"
                            onClick={onClose} tooltip tooltipPosition="pos-top" tooltipText="Save mocap settings"/>
                    )}
                </div>
            </footer>
        </div>
    </>;
};

export default MocapSetupModal;
