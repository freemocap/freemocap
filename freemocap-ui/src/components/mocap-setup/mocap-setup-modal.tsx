import React, {type ReactNode, useEffect, useMemo, useRef, useState} from "react";
import CaptureVolumeSettings from './capture-volume-settings';
import CameraGeometrySummary from './camera-geometry-summary';
import ModalWindowControls from '@/components/ui-components/ModalWindowControls';
import ButtonSm from "@/components/ui-components/ButtonSm";
import SubactionHeader from "@/components/ui-components/SubactionHeader";
import SettingRow from '@/components/common/settings-layout/setting-row';
import ProcessingPipelineSelect from './processing-pipeline-select';
import SettingsSection from "@/components/common/settings-layout/settings-section";
import SettingsSummaryChip from "@/components/common/settings-layout/settings-summary-chip";

import ProcessingDirectorySettings from "@/components/mocap-setup/mocap-processing-directory";
import PosthocFilterSettings from "@/components/mocap-setup/mocap-postprocess-settings";
import MocapDetectorSettings from "@/components/mocap-setup/mocap-detector-settings";
import MocapBlenderSettings from "@/components/mocap-setup/mocap-blender-settings";
import MocapExportSettings from './mocap-export-settings';
import TriangulationSettings from "@/components/mocap-setup/mocap-triangulation-settings";
import {useMocap} from "@/hooks/useMocap";
import {useAppSelector} from "@/store/hooks";
import {RTMPOSE_MODELS} from "@/store/slices/mocap";
import MocapStageSelection from './mocap-stage-selection';
import {PROCESSING_STAGES} from '@/services/recording/posthoc-processing';
import {selectSourceRunId, selectStageSelection} from '@/store/slices/processing-stages';
import {useSavedStageInventory} from '@/hooks/useSavedStageInventory';
import {useProcessingPlan} from '@/hooks/useProcessingPlan';
import ProcessingGraphView, {GraphNotice} from '@/components/processing-graph/ProcessingGraphView';
import type {LaunchedRun, SettingsSectionName} from '@/components/processing-graph/graph-model';
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
    const sourceRunId = useAppSelector(selectSourceRunId);
    const stageSelection = useAppSelector(selectStageSelection);
    const processSelection = useMemo(() => stageSelection ? {...stageSelection, pipelineImplementation: 'typed_dataflow' as const} : null, [stageSelection]);
    const [view, setView] = useState<'list' | 'graph'>('list');
    const graphView = mode === 'playback' && view === 'graph';
    useSavedStageInventory(mode === 'playback' ? mocapRecordingPath : null);
    const [launchedTaskId, setLaunchedTaskId] = useState<string | null>(null);
    const [launching, setLaunching] = useState(false);
    const launched = useAppSelector(state => launchedTaskId ? state.pipelines.activePipelines[launchedTaskId] ?? null : null);
    const run = useMemo((): LaunchedRun | null => launched?.plan && launched.taskStatus
        ? {taskId: launched.basePipelineId, status: launched.taskStatus, plan: launched.plan, operations: launched.operations ?? []}
        : null, [launched]);
    const planState = useProcessingPlan(graphView && !launchedTaskId ? mocapRecordingPath : null, processSelection);
    const launchProcessing = async (selection: NonNullable<typeof processSelection>): Promise<void> => {
        setLaunching(true);
        setView('graph');
        try {
            const accepted = await dispatchProcessMocapRecording(selection).unwrap();
            if (!accepted.pipeline_id) throw new Error('The server accepted processing without a task id');
            setLaunchedTaskId(accepted.pipeline_id);
        } finally {
            setLaunching(false);
        }
    };


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
        if (config.detectorType === "dlc") return <SettingsSummaryChip>DLC · 2D keypoints</SettingsSummaryChip>;
        if (config.detectorType === "mediapipe") {
            return <SettingsSummaryChip>{`MediaPipe · ${config.mediapipeModelComplexity}`}</SettingsSummaryChip>;
        }
        const model = RTMPOSE_MODELS.find(entry => entry.value === config.rtmPoseModelName);
        return <SettingsSummaryChip>{[config.detectorType === 'rtmw_mediapipe_hands' ? 'RTMW + MediaPipe hands' : 'RTMW', model?.label].filter(Boolean).join(' · ')}</SettingsSummaryChip>;
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
                    text: 'Typed data flow graph V1 is the default. Select the stages to run. Start from videos, saved 2D tracking, saved 3D points, or saved skeleton fits.'}}
                    control={<ProcessingPipelineSelect/>}/>
                <MocapStageSelection path={mocapRecordingPath}/>

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
            summary: <SettingsSummaryChip>{config.exportAfterProcessing && config.exportFormats?.includes('wide_csv') ? 'Wide CSV after processing' : 'Exports on request'}{config.exportTallCsv ? ' · Tall CSV on' : ''}</SettingsSummaryChip>,
            content: <MocapExportSettings sourceRunId={sourceRunId} key={mocapRecordingPath} path={mocapRecordingPath} processing={isLoading || isRecording}/>,
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
                    {mode === 'playback' && <div role="group" aria-label="View" className="mocap-view-switch">
                        {(['list', 'graph'] as const).map(option => <button key={option} type="button" aria-pressed={view === option}
                            className={`mocap-view-switch-option${view === option ? ' selected' : ''}`} onClick={() => setView(option)}>
                            {option === 'list' ? 'List' : 'Graph'}</button>)}
                    </div>}
                    {!graphView && <SubactionHeader text="Mocap setup" className="text-gray"/>}
                    {!graphView && sections.filter(section => mode === 'playback' || section.name !== SetupSection.Stages).map(section => <ButtonSm key={section.name} text={section.name}
                        buttonType={activeSection === section.name ? 'activated' : 'idle'}
                        className="full-width quaternary" textClass="mocap-section-link"
                        onClick={() => {
                            panels.current[section.name]?.scrollIntoView({behavior: 'smooth', block: 'start'});
                            setActiveSection(section.name);
                        }}/>)}
                </nav>
                {graphView && <div className="mocap-settings-content flex-1">
                    {launching ? <GraphNotice warn={false}>Starting the run…</GraphNotice>
                        : launchedTaskId && !launched ? <GraphNotice warn={false}>Waiting for the server to report run {launchedTaskId}…</GraphNotice>
                        : launchedTaskId && !run ? <GraphNotice warn>The server reported run {launchedTaskId} without its processing plan.</GraphNotice>
                        : <ProcessingGraphView planState={planState} run={run} onNewDraft={() => setLaunchedTaskId(null)}
                            sectionContent={(name: SettingsSectionName) =>
                                <div className="settings-layout">{sections.find(section => section.name === name)?.content}</div>}/>}
                </div>}
                <div ref={scrollContainerRef} style={graphView ? {display: 'none'} : undefined} className="mocap-settings-content settings-layout flex-1 overflow-y-auto">
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
                    <ButtonSm text={launchedTaskId ? 'Close' : 'Cancel'} buttonType="quaternary" onClick={onClose}/>
                    {mode === "playback" ? (
                        <ButtonSm text="Process Mocap" textColor="text-white" iconClass="processmocap-icon"
                            buttonType="" className="primary accent"
                            onClick={() => {if (processSelection) void launchProcessing(processSelection);}}
                            disabled={!canProcessMocapRecording || !stageSelection || launching} tooltip tooltipPosition="pos-top"
                            tooltipText={processBlockedReason ?? (stageSelection ? "Start mocap processing" : "Select a stage to process")}/>
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
