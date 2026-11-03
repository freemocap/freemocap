// The Mocap panel's sections as a node graph (design canvas board 12): Recording → SkellyTracker → SkellyForge →
// Blender add-on and Exports. Each card shows its section's settings, its progress bars and what it reads or saves;
// clicking a card opens the real settings sections beside the graph.
import {type PointerEvent, type ReactNode, type WheelEvent, useEffect, useLayoutEffect, useMemo, useRef, useState} from 'react';
import type {ProcessingPlanState} from '@/hooks/useProcessingPlan';
import {useAppDispatch, useAppSelector} from '@/store/hooks';
import {selectStageChoice, selectStageRows, stageToggled} from '@/store/slices/processing-stages';
import type {LaunchedRun} from './graph-model';
import {DATA, type PanelSection, type SectionBar, type SectionGraph, sectionGraph, type SectionId, type SectionNode,
    type SectionSettings, type SectionState} from './section-graph';
import {type Box, portOffset, ROWS, sectionLayout} from './section-layout';
import './processing-graph.css';

interface ProcessingGraphViewProps {
    /** The plan the current settings would run; drawn while no run is shown. */
    planState: ProcessingPlanState;
    /** The launched run to draw live, or null for the draft. */
    run: LaunchedRun | null;
    settings: SectionSettings;
    /** Leaves the launched run and returns to the draft. */
    onNewDraft: () => void;
    /** The real settings section of the Mocap panel with this name. */
    sectionContent: (section: PanelSection) => ReactNode;
}

/** Camera: the graph point at the canvas's top-left corner, and the zoom. */
interface Camera {x: number; y: number; z: number}

const MIN_ZOOM = 0.2;
const MAX_ZOOM = 2;
const SIDE = 24;
const RUN_STATUS: Record<LaunchedRun['status'], string> = {queued: 'Queued', running: 'Running', complete: 'Complete', failed: 'Failed', cancelled: 'Cancelled'};
const colour = (data: keyof typeof DATA): string => `var(--graph-type-${DATA[data].colour})`;
const quiet = (state: SectionState | null): boolean => state === 'not run' || state === 'off';
const stateClass = (state: SectionState | null): string => state ? state.replace(' ', '-') : '';

function StatePill({state}: {state: SectionState | null}) {
    if (!state) return null;
    return <span className={`pg-pill ${stateClass(state)}`}>{state}</span>;
}

function Bars({bars}: {bars: SectionBar[]}) {
    return <>{bars.map(bar => <span key={bar.label} className={`pg-bar-row ${stateClass(bar.state)}`} style={{height: ROWS.bar}}>
        <span className="pg-bar-label">{bar.label}</span>
        <span className="pg-bar-track" role="progressbar" aria-label={bar.label} aria-valuemin={0} aria-valuemax={100}
            aria-valuenow={bar.fraction === null ? undefined : Math.round(bar.fraction * 100)}>
            <i style={{width: `${100 * (bar.fraction ?? 0)}%`}}/></span>
        <span className="pg-bar-text">{bar.text}</span>
    </span>)}</>;
}

function Card({node, box, selected, onPick}: {node: SectionNode; box: Box; selected: boolean; onPick: () => void}) {
    const ports = [...node.inputs.map(data => ({data, direction: 'in' as const})), ...node.outputs.map(data => ({data, direction: 'out' as const}))];
    return <button type="button" aria-label={`${node.title} details`} onClick={onPick}
        className={`pg-card ${stateClass(node.state)}${selected ? ' selected' : ''}${quiet(node.state) ? ' quiet' : ''}`}
        style={{left: box.x, top: box.y, width: box.w, height: box.h}}>
        <span className="pg-card-head" style={{height: ROWS.head}}>
            <span className="pg-card-titles">
                <span className="pg-card-title">{node.title}</span>
                <span className="pg-card-sections">{node.panelSections.join(' · ')}</span>
            </span>
            <StatePill state={node.state}/>
        </span>
        <span className="pg-ports" style={{height: ports.length * ROWS.port}}>
            {ports.map(({data, direction}) => {
                const y = portOffset(node, direction, data) - ROWS.head;
                return <span key={`${direction}:${data}`} className={`pg-port ${direction}`} style={{top: y - ROWS.port / 2, height: ROWS.port}}>
                    <i className="pg-socket" style={{background: colour(data)}}/>
                    {direction === 'in'
                        ? <span className="pg-port-name">{DATA[data].name}</span>
                        : <span className="pg-port-name out" style={{color: colour(data)}}>{DATA[data].name}
                            {DATA[data].detail && <small> {DATA[data].detail}</small>}</span>}
                </span>;
            })}
        </span>
        <span className="pg-settings" style={{paddingTop: ROWS.settingsPad / 2, paddingBottom: ROWS.settingsPad / 2}}>
            {node.groups.map((group, index) => <span key={group.heading ?? index} className="pg-group">
                {group.heading && <span className="pg-group-heading" style={{height: ROWS.heading}}>{group.heading}</span>}
                {group.rows.map(row => <span key={row.label} className="pg-setting" style={{height: ROWS.setting}}>
                    <span>{row.label}</span><b>{row.value}</b></span>)}
            </span>)}
        </span>
        {node.bars.length > 0 && <span className="pg-bars" style={{paddingTop: ROWS.barsPad / 2, paddingBottom: ROWS.barsPad / 2}}><Bars bars={node.bars}/></span>}
        <span className={`pg-disk ${node.disk.direction}`} style={{height: ROWS.foot}}>
            <svg width="16" height="13" viewBox="0 0 16 13" aria-hidden="true"><path d="M1 3a2 2 0 0 1 2-2h3l2 2h5a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2z"/></svg>
            <span>{node.disk.text}</span>
        </span>
    </button>;
}

function Details({node, live, sectionContent, onClose}: {node: SectionNode; live: boolean; sectionContent: ProcessingGraphViewProps['sectionContent']; onClose: () => void}) {
    return <aside className="pg-details" aria-label={`${node.title} settings`}>
        <div className="pg-details-head">
            <h2>{node.title}</h2>
            <StatePill state={node.state}/>
            <button type="button" className="pg-btn icon" aria-label="Close details" onClick={onClose}>×</button>
        </div>
        {node.bars.length > 0 && <div className="pg-details-bars"><Bars bars={node.bars}/></div>}
        {node.reads.length > 0 && <><h3>Reads</h3>{node.reads.map(path => <code key={path} className="pg-path read">{path}</code>)}</>}
        {node.writes.length > 0 && <><h3>Saved</h3>{node.writes.map(path => <code key={path} className="pg-path write">{path}</code>)}</>}
        {live && <p className="pg-help">This run keeps the settings it started with. Choose New draft to change settings for the next run.</p>}
        {!live && node.panelSections.map(section => <section key={section} className="pg-details-section">
            <h3>{section}</h3>
            <div className="settings-layout">{sectionContent(section)}</div>
        </section>)}
    </aside>;
}

/** The Processing stages checkboxes in one row, using the same store actions as the list view. */
function StageStrip({locked}: {locked: boolean}) {
    const dispatch = useAppDispatch();
    const rows = useAppSelector(selectStageRows);
    return <div className="pg-stages" role="group" aria-label="Processing stages">
        <span className="pg-stages-heading">Processing stages</span>
        {rows.map((row, index) => <label key={row.stage} className={`pg-stage${row.runs ? ' runs' : ''}`}>
            <input type="checkbox" checked={row.runs} disabled={locked || !row.canSelect}
                onChange={event => dispatch(stageToggled({index, checked: event.target.checked}))}/>
            {row.label}
        </label>)}
    </div>;
}

/** The saved run the stages start from and where results go; opens the full Processing stages section. */
function RunSource({onOpen}: {onOpen: () => void}) {
    const choice = useAppSelector(selectStageChoice);
    const saveMode = useAppSelector(state => state.processingStages.saveMode);
    const runId = choice?.run_id ?? 0;
    return <button type="button" className="pg-stages-save" onClick={onOpen}>
        Start from <b>Run {runId}</b> · Save results: <b>{saveMode === 'new_run' ? 'New run' : `Overwrite Run ${runId}`}</b>
    </button>;
}

/** The Mocap panel's sections as a graph, drawing the draft plan or a launched run. */
export default function ProcessingGraphView({planState, run, settings, onNewDraft, sectionContent}: ProcessingGraphViewProps) {
    const {preview, loading, failure} = run ? {preview: null, loading: false, failure: null} : planState;
    const built = useMemo((): {graph: SectionGraph; layout: ReturnType<typeof sectionLayout>} | {error: string} => {
        try {
            const graph = sectionGraph(settings, run ? null : preview?.plan ?? null, run);
            return {graph, layout: sectionLayout(graph)};
        } catch (reason) {
            return {error: reason instanceof Error ? reason.message : String(reason)};
        }
    }, [settings, preview, run]);
    const graph = 'graph' in built ? built.graph : null;
    const layout = 'layout' in built ? built.layout : null;

    const canvasRef = useRef<HTMLDivElement>(null);
    const [size, setSize] = useState({w: 0, h: 0});
    useLayoutEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;
        const observer = new ResizeObserver(() => setSize({w: canvas.clientWidth, h: canvas.clientHeight}));
        observer.observe(canvas);
        return () => observer.disconnect();
    }, []);
    const [camera, setCamera] = useState<Camera | null>(null);
    const [selected, setSelected] = useState<SectionId | 'stages' | null>(null);
    const [dragging, setDragging] = useState(false);
    const drag = useRef<{x: number; y: number; camera: Camera} | null>(null);
    const fit = (): Camera => {
        if (!layout || !size.w) return {x: 0, y: 0, z: 1};
        const z = Math.min(1, Math.max(MIN_ZOOM, Math.min((size.w - 2 * SIDE) / layout.width, (size.h - 2 * SIDE) / layout.height)));
        return {z, x: (layout.width - size.w / z) / 2, y: (layout.height - size.h / z) / 2};
    };
    useEffect(() => setCamera(null), [layout?.width, layout?.height]);
    const cam = camera ?? fit();
    const zoomAbout = (z: number, px: number, py: number): void => {
        const next = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, z));
        setCamera({z: next, x: cam.x + px / cam.z - px / next, y: cam.y + py / cam.z - py / next});
    };
    const onWheel = (event: WheelEvent<HTMLDivElement>): void => {
        const rect = event.currentTarget.getBoundingClientRect();
        zoomAbout(cam.z * Math.exp(-event.deltaY * 0.0015), event.clientX - rect.left, event.clientY - rect.top);
    };
    const onPointerDown = (event: PointerEvent<HTMLDivElement>): void => {
        if ((event.target as Element).closest('.pg-card')) return;
        event.currentTarget.setPointerCapture(event.pointerId);
        drag.current = {x: event.clientX, y: event.clientY, camera: cam};
        setDragging(true);
    };
    const onPointerMove = (event: PointerEvent<HTMLDivElement>): void => {
        const start = drag.current;
        if (start) setCamera({z: start.camera.z, x: start.camera.x - (event.clientX - start.x) / start.camera.z, y: start.camera.y - (event.clientY - start.y) / start.camera.z});
    };
    const onPointerUp = (): void => {
        drag.current = null;
        setDragging(false);
    };

    const notice: ReactNode = 'error' in built ? <p role="alert" className="pg-notice warn">{built.error}</p>
        : failure ? <p role="alert" className="pg-notice warn">Could not build the processing plan: {failure}</p>
            : preview && preview.errors.length ? <p role="alert" className="pg-notice warn">Process cannot run with these settings: {preview.errors.join(' · ')}</p>
                : !run && loading && !preview ? <p role="status" className="pg-notice">Building the processing plan…</p> : null;
    const done = graph ? graph.nodes.filter(node => node.state === 'complete').length : 0;
    const active = graph ? graph.nodes.filter(node => !quiet(node.state)).length : 0;
    const selectedNode = graph && selected && selected !== 'stages' ? graph.nodes.find(node => node.id === selected)! : null;

    return <div className="pg-shell" onKeyDown={event => {
        if (event.key === 'Escape' && selected) setSelected(null);
    }}>
        <div className="pg-toolbar" role="toolbar" aria-label="Graph view">
            <span className={`pg-status ${run ? run.status : 'draft'}`}><i/>{run ? `${RUN_STATUS[run.status]} · ${done} of ${active} done` : loading ? 'Draft · updating plan' : 'Draft'}</span>
            {run && <button type="button" className="pg-btn" onClick={onNewDraft}>New draft</button>}
            <RunSource onOpen={() => setSelected('stages')}/>
            <span className="pg-zoom">
                <button type="button" className="pg-btn icon" aria-label="Zoom out" onClick={() => zoomAbout(cam.z / 1.2, size.w / 2, size.h / 2)}>−</button>
                <span className="pg-zoom-level">{Math.round(cam.z * 100)}%</span>
                <button type="button" className="pg-btn icon" aria-label="Zoom in" onClick={() => zoomAbout(cam.z * 1.2, size.w / 2, size.h / 2)}>+</button>
                <button type="button" className="pg-btn" onClick={() => setCamera(null)}>Fit all</button>
            </span>
        </div>
        <StageStrip locked={run !== null}/>
        <div className="pg-body">
            <div ref={canvasRef} className={`pg-canvas${dragging ? ' dragging' : ''}`} onWheel={onWheel} onPointerDown={onPointerDown}
                onPointerMove={onPointerMove} onPointerUp={onPointerUp} onPointerCancel={onPointerUp} aria-label="Graph canvas. Drag to pan.">
                {graph && layout && size.w > 0 && <div className="pg-world"
                    style={{width: layout.width, height: layout.height, transform: `scale(${cam.z}) translate(${-cam.x}px, ${-cam.y}px)`}}>
                    <svg className="pg-wires" width={layout.width} height={layout.height} aria-hidden="true">
                        {graph.wires.map(wire => <path key={wire.id} d={layout.wires.find(item => item.id === wire.id)!.d}
                            className={`pg-wire${wire.active ? '' : ' quiet'}${graph.nodes.find(node => node.id === wire.target)!.state === 'running' ? ' flow' : ''}`}
                            style={{stroke: colour(wire.data)}}/>)}
                    </svg>
                    {graph.nodes.map(node => <Card key={node.id} node={node} box={layout.boxes.get(node.id)!} selected={selected === node.id}
                        onPick={() => setSelected(node.id)}/>)}
                </div>}
                {notice}
            </div>
            {selectedNode && <Details node={selectedNode} live={run !== null} sectionContent={sectionContent} onClose={() => setSelected(null)}/>}
            {selected === 'stages' && <aside className="pg-details" aria-label="Processing stages settings">
                <div className="pg-details-head"><h2>Processing stages</h2>
                    <button type="button" className="pg-btn icon" aria-label="Close details" onClick={() => setSelected(null)}>×</button></div>
                <div className="settings-layout">{sectionContent('Processing stages')}</div>
            </aside>}
        </div>
    </div>;
}

/** A message in place of the graph. */
export function GraphNotice({children, warn}: {children: ReactNode; warn: boolean}) {
    return <div className="pg-shell"><div className="pg-body"><div className="pg-canvas">
        <p role={warn ? 'alert' : 'status'} className={warn ? 'pg-notice warn' : 'pg-notice'}>{children}</p>
    </div></div></div>;
}
