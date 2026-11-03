import React, {useEffect, useMemo, useRef, useState} from "react";
import ButtonSm from "@/components/ui-components/ButtonSm";
import {useMocap} from "@/hooks/useMocap";
import {useBlender} from "@/hooks/useBlender";
import {useAppSelector} from "@/store/hooks";
import {selectStageChoice, selectStageRows, selectStageSelection} from '@/store/slices/processing-stages';
import {PROCESSING_STAGES, type ResumeStage} from '@/services/recording/posthoc-processing';
import {useSavedStageInventory} from '@/hooks/useSavedStageInventory';
import {useProcessingPlan} from '@/hooks/useProcessingPlan';
import {useRecordingCalibrationDefault} from '@/hooks/useRecordingCalibrationDefault';
import ProcessingGraphView, {type GraphFocus} from '@/components/processing-graph/ProcessingGraphView';
import type {LaunchedRun} from '@/components/processing-graph/graph-model';
import {type DraftStage, type NodeId, stageGraph, type StageGraph} from '@/components/processing-graph/stage-graph';
import ProcessingPipelineSelect from './processing-pipeline-select';
import ProcessingOutline from './processing-outline';
import StageSection from './stage-section';
import {SaveResultsSelect, StageInventoryStatus, StartFromSelect} from './processing-run-controls';
import {type SectionId, useProcessingSections} from './processing-sections';
import './mocap-processing.css';

type MocapMode = "recording" | "playback";

interface MocapSetupModalProps {
    onClose?: () => void;
    mode?: MocapMode;
}

const RUN_STATUS: Record<LaunchedRun['status'], string> = {queued: 'Queued', running: 'Running', complete: 'Complete', failed: 'Failed', cancelled: 'Cancelled'};

/** The Mocap processing window: the outline on the left, the list or the graph beside it, and Process at the top. */
const MocapSetupModal: React.FC<MocapSetupModalProps> = ({onClose, mode = "playback"}) => {
    useRecordingCalibrationDefault(mode === 'playback');
    const playback = mode === 'playback';
    const {canProcessMocapRecording, isLoading, isRecording, mocapRecordingPath, dispatchProcessMocapRecording, validateDirectory} = useMocap();
    const {exportToBlenderEnabled, effectiveBlenderExePath} = useBlender();
    const config = useAppSelector(state => state.mocap.config);
    const stageSelection = useAppSelector(selectStageSelection);
    const stageRows = useAppSelector(selectStageRows);
    const stageChoice = useAppSelector(selectStageChoice);
    const processSelection = useMemo(() => stageSelection ? {...stageSelection, pipelineImplementation: 'typed_dataflow' as const} : null, [stageSelection]);
    const sections = useProcessingSections(mode);
    const [view, setView] = useState<'list' | 'graph'>('graph');
    const graphView = playback && view === 'graph';
    const [focus, setFocus] = useState<GraphFocus | null>(null);
    useSavedStageInventory(playback ? mocapRecordingPath : null);

    const [launchedTaskId, setLaunchedTaskId] = useState<string | null>(null);
    const [launching, setLaunching] = useState(false);
    const pipelines = useAppSelector(state => state.pipelines.activePipelines);
    const launched = launchedTaskId ? pipelines[launchedTaskId] ?? null : null;
    const run = useMemo((): LaunchedRun | null => launched?.plan && launched.taskStatus
        ? {taskId: launched.basePipelineId, status: launched.taskStatus, plan: launched.plan, operations: launched.operations ?? [],
            cameras: Object.values(pipelines)
                .filter(pipeline => pipeline.basePipelineId === launched.basePipelineId && pipeline.cameraId !== null)
                .sort((a, b) => a.cameraId!.localeCompare(b.cameraId!, undefined, {numeric: true}))
                .map(pipeline => ({cameraId: pipeline.cameraId!, fraction: pipeline.progress === null ? null : pipeline.progress / 100, detail: pipeline.detail}))}
        : null, [launched, pipelines]);
    const active = run !== null && ['queued', 'running'].includes(run.status);
    const planState = useProcessingPlan(graphView && !launchedTaskId ? mocapRecordingPath : null, processSelection);

    const graph = useMemo((): StageGraph | {error: string} => {
        const stages = Object.fromEntries(PROCESSING_STAGES.map(([stage], index): [ResumeStage, DraftStage] => {
            const row = stageRows[index];
            return [stage, {runs: row.runs, reusedFrom: !row.runs && row.outcome === 'Reuse saved' ? `from Run ${stageChoice?.run_id ?? 0}` : null}];
        })) as Record<ResumeStage, DraftStage>;
        try {
            return stageGraph({stages, blenderOn: exportToBlenderEnabled, blenderFound: Boolean(effectiveBlenderExePath),
                exportsOn: config.exportAfterProcessing, exportChannels: config.exportChannels, plan: run ? null : planState.preview?.plan ?? null, run});
        } catch (reason) {
            return {error: reason instanceof Error ? reason.message : String(reason)};
        }
    }, [stageRows, stageChoice, exportToBlenderEnabled, effectiveBlenderExePath, config.exportAfterProcessing, config.exportChannels, planState.preview, run]);

    const launchProcessing = async (selection: NonNullable<typeof processSelection>): Promise<void> => {
        setLaunching(true);
        setFocus(null);
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
        if (canProcessMocapRecording) return stageSelection ? null : 'Select a stage to process';
        if (isRecording) return "Stop recording before processing";
        if (isLoading) return "Processing already in progress";
        if (!mocapRecordingPath) return "Select a recording folder to process";
        return null;
    }, [canProcessMocapRecording, isRecording, isLoading, mocapRecordingPath, stageSelection]);

    const [activeSection, setActiveSection] = useState<SectionId>('recording');
    const listRef = useRef<HTMLDivElement>(null);
    const panels = useRef<Partial<Record<SectionId, HTMLDivElement>>>({});
    useEffect(() => {
        if (graphView) return;
        const observer = new IntersectionObserver(entries => {
            for (const entry of entries) {
                if (!entry.isIntersecting) continue;
                const id = (Object.keys(panels.current) as SectionId[]).find(key => panels.current[key] === entry.target);
                if (id) setActiveSection(id);
            }
        }, {root: listRef.current, rootMargin: '0px 0px -65% 0px', threshold: 0});
        Object.values(panels.current).forEach(panel => panel && observer.observe(panel));
        return () => observer.disconnect();
    }, [graphView]);

    const pick = (id: SectionId): void => {
        setActiveSection(id);
        if (graphView) setFocus({id: id as NodeId, explain: false});
        else panels.current[id]?.scrollIntoView({behavior: 'smooth', block: 'start'});
    };
    const runStates = run && 'nodes' in graph ? Object.fromEntries(graph.nodes.map(node => [node.id, node.state])) as Partial<Record<SectionId, string>> : null;
    const notice = launching ? <p role="status" className="pg-notice">Starting the run…</p>
        : launchedTaskId && !launched ? <p role="status" className="pg-notice">Waiting for the server to report the run…</p>
            : launchedTaskId && !run ? <p role="alert" className="pg-notice warn">The server reported the run without its processing plan.</p>
                : planState.failure ? <p role="alert" className="pg-notice warn">Could not build the processing plan: {planState.failure}</p>
                    : planState.preview?.errors.length ? <p role="alert" className="pg-notice warn">Process cannot run with these settings: {planState.preview.errors.join(' · ')}</p>
                        : null;
    const recordingName = mocapRecordingPath?.split(/[\\/]/).filter(Boolean).pop() ?? '';
    const done = 'nodes' in graph ? graph.nodes.filter(node => node.state === 'complete').length : 0;
    const steps = 'nodes' in graph ? graph.nodes.filter(node => !['not run', 'off', 'skipped', 'reused'].includes(node.state)).length : 0;

    return <>
        <div className="pos-fixed inset-0 bg-surface-overlay z-10" onClick={onClose}/>
        <div role="dialog" aria-label="Mocap processing" aria-modal="true" className="mocap-processing pos-fixed flex flex-col"
            onKeyDown={event => {if (event.key === 'Escape' && !focus) onClose?.();}}>
            <header className="mp-title">
                <h1>Mocap processing</h1>
                {recordingName && <span className="mp-recording" title={mocapRecordingPath ?? ''}>{recordingName}</span>}
                <button type="button" className="mp-close" aria-label="Close Mocap processing" onClick={onClose}>
                    <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M4 4l8 8M12 4l-8 8"/></svg></button>
            </header>
            <div className="mp-head">
                {playback && <div role="group" aria-label="View" className="mp-seg">
                    {(['list', 'graph'] as const).map(option => <button key={option} type="button" aria-pressed={view === option}
                        className={view === option ? 'on' : ''} onClick={() => {setView(option); setFocus(null);}}>{option === 'list' ? 'List' : 'Graph'}</button>)}
                </div>}
                {playback && <span className={`mp-status ${run ? run.status : 'draft'}`}><i/>{run ? `${RUN_STATUS[run.status]} · ${done} of ${steps} done` : 'Draft'}</span>}
                {run && !active && <button type="button" className="mp-small-button" onClick={() => setLaunchedTaskId(null)}>New draft</button>}
                {playback && <><StartFromSelect/><SaveResultsSelect/><ProcessingPipelineSelect/><StageInventoryStatus/></>}
                {playback
                    ? <ButtonSm text={active ? 'Processing…' : 'Process Mocap'} textColor="text-white" iconClass="processmocap-icon" buttonType=""
                        className="primary accent mp-process" disabled={!canProcessMocapRecording || !processSelection || launching || active}
                        onClick={() => {if (processSelection) void launchProcessing(processSelection);}}
                        tooltip tooltipPosition="pos-bottom" tooltipText={processBlockedReason ?? 'Start mocap processing'}/>
                    : <ButtonSm text="Done" textColor="text-white" buttonType="" className="primary accent mp-process" onClick={onClose}/>}
            </div>
            <div className="mp-body">
                <ProcessingOutline sections={sections} active={graphView ? focus?.id ?? null : activeSection} playback={playback} states={runStates} onPick={pick}/>
                <main className="mp-main">
                    {graphView
                        ? <ProcessingGraphView graph={graph} sections={sections} notice={notice} locked={active} focus={focus} onFocus={setFocus}/>
                        : <div ref={listRef} className="mp-list settings-layout">
                            {sections.map(section => <div key={section.id} ref={element => {
                                if (element) panels.current[section.id] = element;
                                else delete panels.current[section.id];
                            }}><StageSection section={section} playback={playback}>{section.content}</StageSection></div>)}
                        </div>}
                </main>
            </div>
        </div>
    </>;
};

export default MocapSetupModal;
