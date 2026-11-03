// The processing plan drawn with the approved Graph Lab design (design canvas boards 2–6):
// typed slot colours, cut-corner disk cards, hover focus, legend, both orientations and the node inspector.
// A launched run is drawn from the plan it was admitted with, with each operation's state and progress.
import {type PointerEvent, type ReactNode, type WheelEvent, useEffect, useLayoutEffect, useMemo, useRef, useState} from 'react';
import type {ProcessingPlanState} from '@/hooks/useProcessingPlan';
import type {TaskOperation} from '@/services/server/transport/message-contract';
import {basename, displayGraph, type DiskFile, type DisplayGraph, type DisplayNode, type LaunchedRun, operationCount,
    type OperationState, runOperations, type SettingsSectionName} from './graph-model';
import {computeLayout, diskFileRows, type GraphDirection, type GraphLayout, type NodeBox} from './graph-layout';
import './processing-graph.css';

interface ProcessingGraphViewProps {
    /** The plan the current settings would run; drawn while no run is shown. */
    planState: ProcessingPlanState;
    /** The launched run to draw live, or null for the draft plan. */
    run: LaunchedRun | null;
    /** Leaves the launched run and returns to the draft plan. */
    onNewDraft: () => void;
    /** The real settings section, rendered in the inspector for the selected node. */
    sectionContent: (section: SettingsSectionName) => ReactNode;
}

/** Camera: the graph point at the canvas's top-left corner, and the zoom. */
interface Camera {x: number; y: number; z: number}

const TYPE_COLOURS = 14;
const BAND = {top: 64, bottom: 56, side: 24};
const READABLE_ZOOM = 0.75;
const MIN_ZOOM = 0.06;
const MAX_ZOOM = 2.5;
const LOW_DETAIL_ZOOM = 0.55;

const typeColour = (graph: DisplayGraph, kind: string): string => `var(--graph-type-${(graph.kinds.indexOf(kind) % TYPE_COLOURS) + 1})`;
const round = (value: number): number => Math.round(value * 10) / 10;
const middle = (text: string, max: number): string => {
    if (text.length <= max) return text;
    const keep = max - 1;
    const head = Math.ceil(keep * 0.45);
    return `${text.slice(0, head)}…${text.slice(text.length - (keep - head))}`;
};
const folderPath = (x: number, y: number, w: number, h: number): string =>
    `M${x} ${y + 6}a4 4 0 0 1 4-4h${w * 0.3}l5 5h${w * 0.7 - 13}a4 4 0 0 1 4 4v${h - 15}a4 4 0 0 1-4 4h${-(w - 8)}a4 4 0 0 1-4-4z`;
const chamfer = (x: number, y: number, w: number, h: number, c: number): string =>
    `M${x + c} ${y}H${x + w - c}L${x + w} ${y + c}V${y + h - c}L${x + w - c} ${y + h}H${x + c}L${x} ${y + h - c}V${y + c}Z`;
const TRACK_WIDTH = 36;
const STATE_LABEL: Record<OperationState, string> = {waiting: 'waiting', running: 'running', complete: 'complete', failed: 'failed', cancelled: 'cancelled'};

const asFiles = (paths: string[]): DiskFile[] => paths.map(path => ({name: basename(path), path}));
/** Files a node reads: what the run reports, or the plan's read paths before that. */
const readFiles = (node: DisplayNode, operation: TaskOperation | null): DiskFile[] =>
    operation?.files_read?.length ? asFiles(operation.files_read) : node.files;
/** Files a node wrote, as the run reports them. */
const writtenFiles = (operation: TaskOperation | null): DiskFile[] => asFiles(operation?.files_written ?? []);
/** Files a disk card names: a save card names what was written, a load card what is read. */
const diskFiles = (node: DisplayNode, operation: TaskOperation | null): DiskFile[] =>
    node.io === 'write' ? writtenFiles(operation) : readFiles(node, operation);

/** The disk card's file lines, kept to the rows the layout reserved so the drawing never moves. */
function fileLines(files: DiskFile[], rows: number, chars: number): {key: string; text: string; more: boolean}[] {
    if (files.length <= rows) return files.map(file => ({key: file.path, text: middle(file.name, chars), more: false}));
    const shown = files.slice(0, rows - 1).map(file => ({key: file.path, text: middle(file.name, chars), more: false}));
    return [...shown, {key: 'more', text: `+${files.length - shown.length} more`, more: true}];
}

function StateIcon({state}: {state: OperationState | null}) {
    switch (state) {
        case null:
        case 'waiting':
            return <circle className="pg-ring" r={5}><title>{state ?? 'will run'}</title></circle>;
        case 'running':
            return <><title>running</title><circle className="pg-st-run pg-st-pulse" r={5}/><circle className="pg-st-run" r={5}/></>;
        case 'complete':
            return <><title>complete</title><circle className="pg-st-okc" r={7}/><path className="pg-st-okm" d="M-3 0l2 2.2 4-4.4"/></>;
        case 'failed':
            return <><title>failed</title><circle className="pg-st-badc" r={7}/><path className="pg-st-badm" d="M-2.5-2.5l5 5M2.5-2.5l-5 5"/></>;
        case 'cancelled':
            return <><title>cancelled</title><circle className="pg-st-canc" r={7}/><path className="pg-st-canm" d="M-2.5-2.5l5 5M2.5-2.5l-5 5"/></>;
    }
}

function DiskCard({node, box, side, operation}: {node: DisplayNode; box: NodeBox; side: boolean; operation: TaskOperation | null}) {
    const W = box.bw;
    const H = box.bh;
    const into = node.io === 'write';
    const fx = side ? 14 : W + 34;
    const fy = side ? H + 34 : 8;
    const a = side ? {x: fx + 26, y: H} : {x: W, y: fy + 22};
    const b = side ? {x: fx + 26, y: fy} : {x: fx, y: fy + 22};
    const from = into ? a : b;
    const to = into ? b : a;
    const dx = Math.sign(to.x - from.x);
    const dy = Math.sign(to.y - from.y);
    const tip = {x: to.x - dx, y: to.y - dy};
    const base = {x: tip.x - dx * 13, y: tip.y - dy * 13};
    const px = dy * 9;
    const py = dx * 9;
    const gx = fx + 26;
    const gy = fy + 27;
    const tx = side ? fx + 64 : gx;
    const ty = side ? fy + 13 : fy + 56;
    const chars = side ? 27 : 16;
    const rail = `M${from.x} ${from.y}L${base.x} ${base.y}`;
    const lines = fileLines(diskFiles(node, operation), diskFileRows(node), chars);
    const pending = into
        ? operation === null || operation.status === 'waiting' || operation.status === 'running' ? 'path reported when saved' : 'no path reported'
        : 'no files listed';
    return <g className="pg-disk">
        <path className="pg-rail-out" d={rail}/>
        <path className="pg-rail-in" d={rail}/>
        <path className="pg-rail-head" d={`M${tip.x} ${tip.y}L${base.x + px} ${base.y + py}L${base.x - px} ${base.y - py}Z`}/>
        <path className="pg-folder" d={folderPath(fx, fy, 52, 40)}/>
        <path className="pg-folder-lip" d={`M${fx} ${fy + 13}H${fx + 52}`}/>
        <path className="pg-folder-arrow" d={into
            ? `M${gx} ${gy - 8}V${gy + 7}M${gx - 6} ${gy + 1}L${gx} ${gy + 7}L${gx + 6} ${gy + 1}`
            : `M${gx} ${gy + 7}V${gy - 8}M${gx - 6} ${gy - 2}L${gx} ${gy - 8}L${gx + 6} ${gy - 2}`}/>
        <text className="pg-disk-label" x={tx} y={ty} textAnchor={side ? 'start' : 'middle'}>
            {side ? (into ? 'SAVE TO DISK' : 'LOAD FROM DISK') : (into ? 'save' : 'load')}
        </text>
        {lines.map((line, i) => <text key={line.key} className={line.more ? 'pg-disk-file more' : 'pg-disk-file'} x={tx} y={ty + 18 + i * 16}
            textAnchor={side ? 'start' : 'middle'}>{line.text}</text>)}
        {lines.length === 0 && <text className="pg-disk-file pending" x={tx} y={ty + 18} textAnchor={side ? 'start' : 'middle'}>{pending}</text>}
    </g>;
}

function NodeCard({node, box, graph, side, classes, operation, onPick, onHover}: {
    node: DisplayNode; box: NodeBox; graph: DisplayGraph; side: boolean; classes: string; operation: TaskOperation | null;
    onPick: () => void; onHover: (on: boolean) => void;
}) {
    const W = box.bw;
    const H = box.bh;
    const ht = box.headTop;
    const io = node.io !== null;
    const titleChars = Math.floor((W - 28 - (io ? 66 : 26)) / 7.2);
    const title = node.title.length > titleChars ? `${node.title.slice(0, titleChars - 1)}…` : node.title;
    const meta = `${node.resource} · stage ${node.stageNumber}${node.camera !== null ? ` · camera ${node.camera + 1}` : ''}`;
    return <g className={classes} transform={`translate(${round(box.x)},${round(box.y)})`} role="button" tabIndex={0}
        aria-label={`Inspect ${node.title}`} onClick={onPick} onMouseEnter={() => onHover(true)} onMouseLeave={() => onHover(false)}
        onKeyDown={event => {
            if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                onPick();
            }
        }}>
        {io ? <>
            <DiskCard node={node} box={box} side={side} operation={operation}/>
            <path className="pg-halo" d={chamfer(-4, -4, W + 8, H + 8, 16)}/>
            <path className="pg-body" d={chamfer(0, 0, W, H, 13)}/>
        </> : <>
            <rect className="pg-halo" x={-4} y={-4} width={W + 8} height={H + 8} rx={13}/>
            <rect className="pg-body" width={W} height={H} rx={10}/>
        </>}
        <text className="pg-title" x={14} y={ht + 22}>{title}</text>
        <text className="pg-meta" x={14} y={ht + 39}>{meta}</text>
        <g className="pg-st" transform={`translate(${W - 20},${ht + 18})`}><StateIcon state={operation?.status ?? null}/></g>
        {io && <text className="pg-io-tag" x={W - 34} y={ht + 22} textAnchor="end">{node.io === 'write' ? 'SAVE' : 'LOAD'}</text>}
        <path className="pg-divider" d={side ? `M0 50H${W}M0 ${box.footTop}H${W}` : `M0 26H${W}M0 ${H - 26}H${W}`}/>
        {side && node.inputs.length > 0 && <path className="pg-divider soft" d={`M14 ${box.split}H${W - 14}`}/>}
        {node.inputs.length === 0 && <text className="pg-port-none" x={side ? 14 : W / 2} y={side ? box.sourceY + 4 : 17}
            textAnchor={side ? 'start' : 'middle'}>source · no inputs</text>}
        {node.inputs.map(slot => {
            const p = box.ports.get(`in:${slot.name}`)!;
            const colour = typeColour(graph, slot.kind);
            return <g key={`in:${slot.name}`}>
                <circle className="pg-socket" cx={p.x} cy={p.y} r={5} style={{fill: colour, stroke: colour}}/>
                <text className="pg-slot-text" x={side ? 14 : p.x} y={side ? p.y + 4 : 17} textAnchor={side ? 'start' : 'middle'}>
                    <tspan className="pg-port-name">{slot.name}</tspan>
                    {side && slot.kind !== slot.name && <tspan className="pg-port-type" style={{fill: colour}}>{` ${slot.kind}`}</tspan>}
                </text>
            </g>;
        })}
        {node.outputs.map(slot => {
            const p = box.ports.get(`out:${slot.name}`)!;
            const colour = typeColour(graph, slot.kind);
            return <g key={`out:${slot.name}`}>
                <circle className="pg-socket" cx={p.x} cy={p.y} r={5} style={{fill: colour, stroke: colour}}/>
                <text className="pg-slot-text" x={side ? W - 14 : p.x} y={side ? p.y + 4 : H - 9} textAnchor={side ? 'end' : 'middle'}>
                    <tspan className="pg-port-name">{`${slot.name} `}</tspan>
                    <tspan className="pg-port-type" style={{fill: colour}}>{slot.kind}</tspan>
                </text>
            </g>;
        })}
        <rect className="pg-track" x={14} y={box.footTop + 12} width={TRACK_WIDTH} height={4} rx={2}/>
        {operation && <rect className="pg-bar" x={14} y={box.footTop + 12} height={4} rx={2}
            width={operation.status === 'complete' ? TRACK_WIDTH : TRACK_WIDTH * (operation.progress_fraction ?? 0)}/>}
        {operation && <text className="pg-count" x={W - 14} y={box.footTop + 17} textAnchor="end">{operationCount(operation)}</text>}
    </g>;
}

function ProgressBlock({operation}: {operation: TaskOperation}) {
    const counted = operation.completed !== null && operation.total !== null;
    const fraction = operation.status === 'complete' ? 1 : operation.progress_fraction;
    return <div className="pg-progress-block">
        <div className="pg-big">{counted
            ? <>{operation.completed} <small>/ {operation.total}{operation.unit ? ` ${operation.unit}` : ''}</small></>
            : <small>{operation.status === 'running' ? 'Progress not counted for this operation' : STATE_LABEL[operation.status]}</small>}</div>
        {fraction !== null && <div className={`pg-pbar ${operation.status}`}><i style={{width: `${100 * fraction}%`}}/></div>}
        <div className="pg-counts">
            {operation.detail && <span>{operation.detail}</span>}
            {operation.elapsed_seconds !== null && <span>elapsed <b>{operation.elapsed_seconds.toFixed(1)} s</b></span>}
            {operation.seconds_per_motion_frame !== null && <span><b>{operation.seconds_per_motion_frame.toFixed(4)} s</b> per motion frame</span>}
        </div>
    </div>;
}

function Inspector({node, graph, operation, live, sectionContent}: {
    node: DisplayNode | null; graph: DisplayGraph | null; operation: TaskOperation | null; live: boolean;
    sectionContent: ProcessingGraphViewProps['sectionContent'];
}) {
    if (!node || !graph) return <aside className="pg-inspector" aria-label="Node inspector"><div className="pg-empty">Select a node in the graph.</div></aside>;
    const titleOf = (id: string): string => graph.nodes.find(item => item.id === id)?.title ?? id;
    const consumers = graph.edges.filter(edge => edge.source === node.id).map(edge => `${titleOf(edge.target)}.${edge.targetSlot}`);
    const output = node.outputs[0];
    return <aside className="pg-inspector" aria-label="Node inspector">
        <div className="pg-eyebrow">
            {node.io && <><b className={`pg-eyebrow-io io-${node.io}`}>{node.io === 'write' ? 'SAVE TO DISK' : 'LOAD FROM DISK'}</b> · </>}
            stage {node.stageNumber} · {node.stageLabel}{node.camera !== null ? ` · camera ${node.camera + 1}` : ''}
        </div>
        <div className="pg-insp-head"><h2>{node.title}</h2>
            <span className={`pg-state-pill${operation ? ` ${operation.status}` : ''}`}>{operation ? STATE_LABEL[operation.status] : live ? 'waiting' : 'will run'}</span></div>
        {operation && <ProgressBlock operation={operation}/>}
        {operation?.status === 'waiting' && (operation.waiting_for ?? []).length > 0 && <>
            <h3>Waiting for <span>{operation.waiting_for!.length}</span></h3>
            <div className="pg-reads">{operation.waiting_for!.map(id => <code key={id}>{titleOf(id)}</code>)}</div>
        </>}

        <h3>Settings it reads</h3>
        <div className="pg-reads">{node.settings.map(key => <code key={key}>{key}</code>)}</div>
        {live
            ? <p className="pg-help">This run keeps the settings it started with. Choose New draft to change settings for the next run.</p>
            : <div className="settings-layout pg-settings">{sectionContent(node.section)}</div>}

        <h3>Inputs <span>{node.inputs.length}</span></h3>
        {node.inputs.map(slot => <div key={slot.name} className="pg-slot-row">
            <i className="pg-dot" style={{background: typeColour(graph, slot.kind), borderColor: typeColour(graph, slot.kind)}}/>
            <div><div className="pg-slot-title"><b>{slot.name}</b><code style={{color: typeColour(graph, slot.kind)}}>{slot.kind}</code></div>
                <div className="pg-slot-sub">from <code>{slot.from ? `${titleOf(slot.from)}.result` : 'unbound'}</code></div></div>
        </div>)}
        {node.inputs.length === 0 && <p className="pg-help">Source operation: no inputs.</p>}
        <h3>Outputs <span>{node.outputs.length}</span></h3>
        {output && <div className="pg-slot-row">
            <i className="pg-dot" style={{background: typeColour(graph, output.kind), borderColor: typeColour(graph, output.kind)}}/>
            <div><div className="pg-slot-title"><b>{output.name}</b><code style={{color: typeColour(graph, output.kind)}}>{output.kind}</code></div>
                <div className="pg-slot-sub">{consumers.length ? `to ${consumers.join(', ')}` : 'No consumers in this graph.'}</div></div>
        </div>}
        {readFiles(node, operation).length > 0 && <>
            <h3>Reads from disk <span>{readFiles(node, operation).length}</span></h3>
            {readFiles(node, operation).map(file => <div key={file.path} className="pg-disk-row io-read" title={file.path}><div className="pg-dr-name">{middle(file.name, 36)}</div><code className="pg-help pg-path">{file.path}</code></div>)}
        </>}
        {node.io === 'write' && <>
            <h3>Saves to disk <span>{writtenFiles(operation).length || ''}</span></h3>
            {writtenFiles(operation).map(file => <div key={file.path} className="pg-disk-row io-write" title={file.path}><div className="pg-dr-name">{middle(file.name, 36)}</div><code className="pg-help pg-path">{file.path}</code></div>)}
            {writtenFiles(operation).length === 0 && <p className="pg-help">{operation && !['waiting', 'running'].includes(operation.status) ? 'The run reported no saved paths.' : 'Paths are reported when the files are saved.'}</p>}
        </>}
        <h3>Execution</h3>
        <dl className="pg-kv">
            {operation && <><dt>Operation</dt><dd>{operation.label}</dd></>}
            <dt>Resource</dt><dd>{node.resource}</dd>
            <dt>Effects</dt><dd>{node.definition.effects.join(', ') || 'none'}</dd>
            <dt>Identity</dt><dd>{node.id}</dd>
        </dl>
        <details><summary className="pg-help">Graph definition (GraphNode)</summary><pre>{JSON.stringify(node.definition, null, 2)}</pre></details>
    </aside>;
}

/** The draft plan for the current settings, or a launched run drawn live, in the approved Graph Lab design. */
export default function ProcessingGraphView({planState, run, onNewDraft, sectionContent}: ProcessingGraphViewProps) {
    const {preview, loading, failure} = run ? {preview: null, loading: false, failure: null} : planState;
    const plan = run ? run.plan : preview?.plan ?? null;
    const [direction, setDirection] = useState<GraphDirection>('right');
    const built = useMemo((): {graph: DisplayGraph; layout: GraphLayout} | {error: string} | null => {
        if (!plan) return null;
        try {
            const graph = displayGraph(plan);
            return {graph, layout: computeLayout(graph, direction)};
        } catch (reason) {
            return {error: reason instanceof Error ? reason.message : String(reason)};
        }
    }, [plan, direction]);
    const operations = useMemo((): Map<string, TaskOperation> | {error: string} => {
        if (!run) return new Map();
        try {
            return runOperations(run);
        } catch (reason) {
            return {error: reason instanceof Error ? reason.message : String(reason)};
        }
    }, [run]);
    const operationOf = (id: string): TaskOperation | null => operations instanceof Map ? operations.get(id) ?? null : null;
    const graph = built && 'graph' in built ? built.graph : null;
    const layout = built && 'layout' in built ? built.layout : null;
    const side = direction === 'right';

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
    const [selected, setSelected] = useState<string | null>(null);
    const [hovered, setHovered] = useState<string | null>(null);
    const [legendOpen, setLegendOpen] = useState(false);
    const [dragging, setDragging] = useState(false);
    const drag = useRef<{x: number; y: number; camera: Camera} | null>(null);

    const vw = size.w;
    const vh = size.h;
    const fitZoom = layout ? Math.min((vw - 2 * BAND.side) / layout.width, (vh - BAND.top - BAND.bottom) / layout.height) : 1;
    const fitCamera = (): Camera => {
        const z = Math.min(1, Math.max(MIN_ZOOM, fitZoom));
        const yc = (BAND.top + vh - BAND.bottom) / 2;
        return {z, x: (layout!.width - vw / z) / 2, y: layout!.height / 2 - yc / z};
    };
    const initialCamera = (): Camera => {
        if (fitZoom >= READABLE_ZOOM) return fitCamera();
        const z = READABLE_ZOOM;
        const yc = (BAND.top + vh - BAND.bottom) / 2;
        return side ? {z, x: -BAND.side / z, y: layout!.height / 2 - yc / z} : {z, x: (layout!.width - vw / z) / 2, y: -BAND.top / z};
    };
    // A new plan or orientation keeps the reader's place only while the drawing is unchanged in size.
    useEffect(() => setCamera(null), [direction, layout?.width, layout?.height]);
    useEffect(() => {
        if (graph && selected && !graph.nodes.some(node => node.id === selected)) setSelected(null);
    }, [graph, selected]);

    const cam = camera ?? (layout && vw ? initialCamera() : {x: 0, y: 0, z: 1});
    const zoomAbout = (z: number, px: number, py: number): void => {
        const next = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, z));
        setCamera({z: next, x: cam.x + px / cam.z - px / next, y: cam.y + py / cam.z - py / next});
    };
    const onWheel = (event: WheelEvent<HTMLDivElement>): void => {
        const rect = event.currentTarget.getBoundingClientRect();
        zoomAbout(cam.z * Math.exp(-event.deltaY * 0.0015), event.clientX - rect.left, event.clientY - rect.top);
    };
    const onPointerDown = (event: PointerEvent<HTMLDivElement>): void => {
        if ((event.target as Element).closest('.pg-node')) return;
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

    const focus = hovered ?? selected;
    const lit = new Set<string>(focus ? [focus] : []);
    const edgeViews = layout && graph ? layout.paths.map(({edge, d}) => {
        const on = Boolean(focus) && (edge.source === focus || edge.target === focus);
        if (on) {
            lit.add(edge.source);
            lit.add(edge.target);
        }
        return {edge, d, on, flow: operationOf(edge.target)?.status === 'running'};
    }) : [];

    let canvasBody: ReactNode = null;
    if (!(operations instanceof Map)) canvasBody = <p role="alert" className="pg-notice warn">{operations.error}</p>;
    else if (failure) canvasBody = <p role="alert" className="pg-notice warn">Could not build the processing plan: {failure}</p>;
    else if (preview && preview.errors.length) canvasBody = <div role="alert" className="pg-notice warn">Process cannot run with these settings: {preview.errors.join(' · ')}</div>;
    else if (built && 'error' in built) canvasBody = <p role="alert" className="pg-notice warn">{built.error}</p>;
    else if (!built) canvasBody = <p role="status" className="pg-notice">{loading ? 'Building the processing plan…' : 'Choose a recording and at least one stage to see the plan.'}</p>;

    const selectedNode = graph?.nodes.find(node => node.id === selected) ?? null;
    const nodeCount = graph?.nodes.length ?? 0;
    const completeCount = run ? run.operations.filter(operation => operation.status === 'complete').length : 0;

    return <div className="pg-shell">
        <section className="pg-canvas">
            <div ref={canvasRef} className={`pg-scroll${dragging ? ' dragging' : ''}`} onWheel={onWheel} onPointerDown={onPointerDown}
                onPointerMove={onPointerMove} onPointerUp={onPointerUp} onPointerCancel={onPointerUp} aria-label="Graph canvas. Drag to pan.">
                {graph && layout && vw > 0 && <svg className={`${hovered ? 'focusing ' : ''}${cam.z < LOW_DETAIL_ZOOM ? 'lod-low' : ''}`}
                    width={vw} height={vh} viewBox={`${round(cam.x)} ${round(cam.y)} ${round(vw / cam.z)} ${round(vh / cam.z)}`} aria-label="Processing graph">
                    <g>{edgeViews.map(({edge, d, on, flow}) => <path key={edge.id} d={d} style={{stroke: typeColour(graph, edge.kind)}}
                        className={`pg-edge${edge.annotation ? ' annotation' : ''}${on ? ' lit' : ''}${flow ? ' flow' : ''}`}/>)}</g>
                    <g>{graph.nodes.map(node => <NodeCard key={node.id} node={node} box={layout.boxes.get(node.id)!} graph={graph} side={side}
                        operation={operationOf(node.id)}
                        classes={`pg-node${node.annotation ? ' annotation' : ''}${node.io ? ` io io-${node.io}` : ''}${operationOf(node.id) ? ` ${operationOf(node.id)!.status}` : ''}${selected === node.id ? ' selected' : ''}${lit.has(node.id) ? ' near' : ''}`}
                        onPick={() => setSelected(node.id)} onHover={on => setHovered(on ? node.id : null)}/>)}</g>
                </svg>}
                {canvasBody}
            </div>

            <div className="pg-overlay pg-toolbar" role="toolbar" aria-label="Graph view">
                <div className="pg-tool-group">
                    <span className={`pg-status-pill ${run ? run.status : 'draft'}`}><i/>{run ? run.status : 'draft'}</span>
                    {run && <button type="button" className="pg-btn" onClick={onNewDraft}>New draft</button>}
                </div>
                <div className="pg-tool-group"><div className="pg-seg">
                    <button type="button" className={side ? 'pg-btn pressed' : 'pg-btn'} onClick={() => setDirection('right')}>→ Left to right</button>
                    <button type="button" className={side ? 'pg-btn' : 'pg-btn pressed'} onClick={() => setDirection('down')}>↓ Top down</button>
                </div></div>
                <div className="pg-tool-group">
                    <button type="button" className="pg-btn icon" aria-label="Zoom out" onClick={() => zoomAbout(cam.z / 1.2, vw / 2, vh / 2)}>−</button>
                    <span className="pg-zoom-level">{Math.round(cam.z * 100)}%</span>
                    <button type="button" className="pg-btn icon" aria-label="Zoom in" onClick={() => zoomAbout(cam.z * 1.2, vw / 2, vh / 2)}>+</button>
                    <button type="button" className="pg-btn" disabled={!layout} onClick={() => setCamera(fitCamera())}>Fit all</button>
                    <button type="button" className="pg-btn" onClick={() => zoomAbout(1, vw / 2, vh / 2)}>100%</button>
                    <button type="button" className="pg-btn" disabled={!layout || !graph} onClick={() => {
                        const id = selected && layout?.boxes.has(selected) ? selected : graph!.nodes[0].id;
                        const box = layout!.boxes.get(id)!;
                        setCamera({z: 1, x: box.x + box.w / 2 - vw / 2, y: box.y + box.h / 2 - vh / 2});
                    }}>Focus node</button>
                </div>
                <span className="pg-graph-meta">{run
                    ? `${completeCount}/${nodeCount} operations complete`
                    : `${loading ? 'Updating plan… · ' : ''}${nodeCount} operations · ${graph?.edges.length ?? 0} bindings`}</span>
            </div>

            {graph && <div className="pg-overlay pg-legend">
                <button type="button" className="pg-legend-head" onClick={() => setLegendOpen(open => !open)}>
                    <span className={legendOpen ? 'pg-chev open' : 'pg-chev'}/>Legend</button>
                {legendOpen && <div className="pg-legend-body">
                    <div className="pg-legend-row"><b>Wires</b>
                        <span className="pg-key"><svg width="26" height="8" aria-hidden="true"><path className="pg-key-line" d="M1 4h24"/></svg>data</span>
                        <span className="pg-key"><svg width="26" height="8" aria-hidden="true"><path className="pg-key-line dashed" d="M1 4h24"/></svg>annotation</span>
                    </div>
                    <div className="pg-legend-row"><b>Disk</b>
                        <span className="pg-key io-read">load from disk</span>
                        <span className="pg-key io-write">save to disk</span>
                        <span className="pg-key">Cut-corner cards touch disk.</span>
                    </div>
                    <div className="pg-legend-row"><b>Types</b>
                        {graph.kinds.map(kind => <span key={kind} className="pg-type-chip"><i style={{background: typeColour(graph, kind)}}/>{kind}</span>)}
                    </div>
                </div>}
            </div>}
        </section>
        <Inspector node={selectedNode} graph={graph} operation={selectedNode ? operationOf(selectedNode.id) : null} live={run !== null}
            sectionContent={sectionContent}/>
    </div>;
}


/** A message in place of the graph, drawn on the graph canvas. */
export function GraphNotice({children, warn}: {children: ReactNode; warn: boolean}) {
    return <div className="pg-shell"><section className="pg-canvas"><div className="pg-scroll">
        <p role={warn ? 'alert' : 'status'} className={warn ? 'pg-notice warn' : 'pg-notice'}>{children}</p>
    </div></section></div>;
}
