// The Mocap processing window's graph view (design canvas boards 14-17): the sections as nodes in two rows,
// each node carrying its stage switch, its data sockets, its real settings, its progress and its saved files.
// The magnifier zooms onto one node; the info button zooms onto it, covers the graph and points at each part.
import {type PointerEvent, type ReactNode, type WheelEvent, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState} from 'react';
import {useExplainScope, useExplainTarget, type ExplainEntry} from '@/components/common/settings-layout/explain-registry';
import {electronIpc} from '@/services/electron-ipc/electron-ipc';
import {BlenderToggle, ExportsToggle, StageToggle} from '@/components/mocap-setup/processing-run-controls';
import type {ProcessingSection} from '@/components/mocap-setup/processing-sections';
import {basename} from './graph-model';
import {DATA, type DataKey, type GraphNode, type NodeBar, type NodeId, type NodeState, type StageGraph} from './stage-graph';
import {type Box, NODE_WIDTH, portOffset, ROWS, type StageLayout, stageLayout} from './stage-layout';
import {DATA_TEXT, SAVE_TEXT, STAGE_TEXT} from './explain-copy';
import './processing-graph.css';

/** The node the graph is zoomed onto, and whether its parts are being explained. */
export interface GraphFocus {id: NodeId; explain: boolean}

interface ProcessingGraphViewProps {
    graph: StageGraph | {error: string};
    sections: ProcessingSection[];
    /** Run-wide notices: the plan cannot be built, or the server rejects these settings. */
    notice: ReactNode;
    locked: boolean;
    focus: GraphFocus | null;
    onFocus: (focus: GraphFocus | null) => void;
}

interface Camera {x: number; y: number; z: number}

const MIN_ZOOM = 0.2;
const MAX_ZOOM = 2.2;
const FIT_MARGIN = 24;
const colour = (data: DataKey): string => DATA[data].colour;
const stateClass = (state: NodeState): string => state.replace(' ', '-');
const quiet = (state: NodeState): boolean => state === 'not run' || state === 'off';

function Bars({bars}: {bars: NodeBar[]}) {
    return <div className="pg-bars">{bars.map(bar => <div key={bar.label} className={`pg-bar ${stateClass(bar.state)}`}>
        <span className="pg-bar-label">{bar.label}</span>
        <span className="pg-bar-track" role="progressbar" aria-label={bar.label} aria-valuemin={0} aria-valuemax={100}
            aria-valuenow={bar.fraction === null ? undefined : Math.round(bar.fraction * 100)}><i style={{width: `${100 * (bar.fraction ?? 0)}%`}}/></span>
        <span className="pg-bar-text">{bar.text}</span>
    </div>)}</div>;
}

const openFolder = (path: string): void => {
    if (!electronIpc) return;
    void electronIpc.fileSystem.openFolder.mutate({path: path.replace(/[\\/][^\\/]+$/, '')});
};

function Port({data, direction}: {data: DataKey; direction: 'in' | 'out'}) {
    const explain = useExplainTarget(`${direction}:${data}`, `${DATA[data].name}${DATA[data].detail ? `, ${DATA[data].detail}` : ''}`,
        DATA_TEXT[data], direction === 'in' ? 'left' : 'right');
    return <div ref={explain} className={`pg-port ${direction}`} style={{height: ROWS.port}}>
        <i className="pg-socket" style={{background: colour(data)}}/>
        <span className="pg-port-name" style={direction === 'out' ? {color: colour(data)} : undefined}>
            {DATA[data].name}{DATA[data].detail && <small> {DATA[data].detail}</small>}</span>
    </div>;
}

function Disk({node, section}: {node: GraphNode; section: ProcessingSection}) {
    const files = node.id === 'recording' ? node.reads : node.writes.length ? node.writes : node.saves;
    const explain = useExplainTarget('disk', 'Saved data', node.id === 'recording' ? 'The files this run reads from the recording folder.' : SAVE_TEXT, 'left');
    if (!files.length) return null;
    const verb = node.id === 'recording' ? 'reads' : node.writes.length ? 'saved' : 'saves';
    return <div ref={explain} className={`pg-disk ${node.id === 'recording' ? 'read' : 'write'}`} aria-label={`${section.title} files`}>
        <svg viewBox="0 0 16 13" aria-hidden="true"><path d="M1 3a2 2 0 0 1 2-2h3l2 2h5a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2z"/></svg>
        <span>{verb}</span>
        {(node.id === 'recording' && files.length > 2 ? [files[0]] : files).map(path => <button key={path} type="button" className="pg-file" title={path}
            onClick={() => openFolder(path)}>{basename(path)}</button>)}
        {node.id === 'recording' && files.length > 2 && <span>+{files.length - 1}</span>}
    </div>;
}

function Node({node, section, box, focused, explaining, locked, onMeasure, onFocus, onEntries}: {
    node: GraphNode; section: ProcessingSection; box: Box; focused: boolean; explaining: boolean; locked: boolean;
    onMeasure: (id: NodeId, height: number) => void; onFocus: (focus: GraphFocus | null) => void;
    onEntries: (id: NodeId, entries: () => ExplainEntry[]) => void;
}) {
    const {entries, Scope} = useExplainScope();
    useEffect(() => onEntries(node.id, entries), [node.id, entries, onEntries]);
    const element = useRef<HTMLDivElement>(null);
    useLayoutEffect(() => {
        const current = element.current;
        if (!current) return;
        const observer = new ResizeObserver(() => onMeasure(node.id, current.offsetHeight));
        observer.observe(current);
        return () => observer.disconnect();
    }, [node.id, onMeasure]);
    return <div ref={element} role="group" aria-label={section.title}
        className={`pg-node ${stateClass(node.state)}${quiet(node.state) ? ' quiet' : ''}${focused ? ' focused' : ''}${explaining ? ' explaining' : ''}`}
        style={{left: box.x, top: box.y, width: NODE_WIDTH}}>
        <Scope>
            <Header node={node} section={section} focused={focused} explaining={explaining} onFocus={onFocus}/>
            <div className="pg-ports" style={{paddingTop: ROWS.portsPad, paddingBottom: ROWS.portsPad}}>
                {node.outputs.map(data => <Port key={`out:${data}`} data={data} direction="out"/>)}
                {node.inputs.map(data => <Port key={`in:${data}`} data={data} direction="in"/>)}
            </div>
            {section.content !== null && <div className={`pg-node-settings settings-layout${locked ? ' locked' : ''}`} inert={locked}>{section.content}</div>}
            {node.bars.length > 0 && <Bars bars={node.bars}/>}
            <Disk node={node} section={section}/>
        </Scope>
    </div>;
}

function Header({node, section, focused, explaining, onFocus}: {
    node: GraphNode; section: ProcessingSection; focused: boolean; explaining: boolean; onFocus: (focus: GraphFocus | null) => void;
}) {
    const explain = useExplainTarget('stage', section.number ? `${section.number} · ${section.title}` : section.title, STAGE_TEXT[node.id], 'left');
    const kind = node.id === 'recording' ? 'source' : node.id === 'blender' || node.id === 'exports' ? 'sink' : 'stage';
    return <div ref={explain} className={`pg-node-head ${kind}`} style={{height: ROWS.head}}>
        {section.stage && <StageToggle stage={section.stage} title={section.title}/>}
        {node.id === 'blender' && <BlenderToggle/>}
        {node.id === 'exports' && <ExportsToggle/>}
        <span className="pg-node-title">{section.number !== null && <small>{section.number}</small>}{section.title}</span>
        {(node.provenance || !['will run', 'waiting'].includes(node.state)) &&
            <span className={`pg-pill ${stateClass(node.state)}`}>{node.provenance ?? node.state}</span>}
        <button type="button" className={`pg-head-button${explaining ? ' on' : ''}`} aria-label={`Explain ${section.title}`} aria-pressed={explaining}
            onClick={() => onFocus(explaining ? null : {id: node.id, explain: true})}>
            <svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="6.2"/><path d="M8 7.2v4M8 4.8v.2"/></svg></button>
        <button type="button" className={`pg-head-button${focused && !explaining ? ' on' : ''}`} aria-label={`Zoom to ${section.title}`}
            aria-pressed={focused && !explaining} onClick={() => onFocus(focused && !explaining ? null : {id: node.id, explain: false})}>
            <svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="7" cy="7" r="4.6"/><path d="M10.5 10.5L14 14"/></svg></button>
    </div>;
}

interface Callout {key: string; title: string; text: ReactNode; side: 'left' | 'right'; tx: number; ty: number}

const CALLOUT_WIDTH = 340;
const CALLOUT_GAP = 14;

/** Callouts in two columns beside the node, stacked in the order of what they point at so no arrows cross. */
function placeCallouts(callouts: Callout[], heights: Map<string, number>, node: DOMRect, canvas: {w: number; h: number}) {
    const placed: {callout: Callout; x: number; y: number; h: number}[] = [];
    for (const side of ['left', 'right'] as const) {
        const column = callouts.filter(item => item.side === side).sort((a, b) => a.ty - b.ty);
        const x = side === 'left' ? Math.max(12, node.left - 64 - CALLOUT_WIDTH) : Math.min(canvas.w - 12 - CALLOUT_WIDTH, node.right + 64);
        let floor = 12;
        const items = column.map(callout => {
            const h = heights.get(callout.key) ?? 96;
            const y = Math.max(callout.ty - h / 2, floor);
            floor = y + h + CALLOUT_GAP;
            return {callout, x, y, h};
        });
        const overflow = items.length ? items[items.length - 1].y + items[items.length - 1].h - (canvas.h - 12) : 0;
        if (overflow > 0) {
            items.forEach(item => item.y -= overflow);
            items.forEach((item, i) => item.y = Math.max(item.y, i ? items[i - 1].y + items[i - 1].h + CALLOUT_GAP : 12));
        }
        placed.push(...items);
    }
    return placed;
}

function Explain({entries, nodeElement, canvasElement, size, onClose}: {
    entries: ExplainEntry[]; nodeElement: HTMLElement; canvasElement: HTMLElement; size: {w: number; h: number}; onClose: () => void;
}) {
    const [heights, setHeights] = useState(new Map<string, number>());
    const origin = canvasElement.getBoundingClientRect();
    const nodeRect = nodeElement.getBoundingClientRect();
    const node = new DOMRect(nodeRect.left - origin.left, nodeRect.top - origin.top, nodeRect.width, nodeRect.height);
    const targets = entries.filter(entry => nodeElement.contains(entry.element)).map(entry => ({entry, rect: entry.element.getBoundingClientRect()}));
    const callout = (entry: ExplainEntry, rect: DOMRect, side: 'left' | 'right'): Callout => ({key: entry.key, title: entry.title, text: entry.text, side,
        tx: side === 'left' ? rect.left - origin.left - (entry.key.startsWith('in:') ? 0 : 2) : rect.right - origin.left + (entry.key.startsWith('out:') ? 0 : 2),
        ty: rect.top - origin.top + Math.min(rect.height, 40) / 2});
    const fixed = targets.filter(({entry}) => !entry.key.startsWith('setting:')).map(({entry, rect}) => callout(entry, rect, entry.side));
    const settings = targets.filter(({entry}) => entry.key.startsWith('setting:')).sort((a, b) => a.rect.top - b.rect.top);
    // Settings fill the right column from the top and the left column below that, split where the two columns come out closest in height.
    const height = (key: string): number => (heights.get(key) ?? 96) + CALLOUT_GAP;
    const columnHeight = (side: 'left' | 'right', items: Callout[]): number => items.filter(item => item.side === side).reduce((sum, item) => sum + height(item.key), 0);
    let best: Callout[] = [];
    let bestHeight = Infinity;
    for (let split = 0; split <= settings.length; split++) {
        const items = [...fixed, ...settings.map(({entry, rect}, index) => callout(entry, rect, index < split ? 'right' : 'left'))];
        const tallest = Math.max(columnHeight('left', items), columnHeight('right', items));
        if (tallest < bestHeight) {
            best = items;
            bestHeight = tallest;
        }
    }
    const callouts = best;
    const placed = placeCallouts(callouts, heights, node, size);
    const measure = useCallback((key: string) => (element: HTMLDivElement | null) => {
        if (!element) return;
        const h = element.offsetHeight;
        setHeights(previous => previous.get(key) === h ? previous : new Map(previous).set(key, h));
    }, []);
    return <div className="pg-explain" onPointerDown={event => {if (event.target === event.currentTarget) onClose();}}>
        <svg className="pg-leaders" width={size.w} height={size.h} aria-hidden="true">
            <defs><marker id="pg-arrow" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
                <path d="M0 0L10 5L0 10z"/></marker></defs>
            {placed.map(({callout, x, y, h}) => {
                const edge = callout.side === 'left' ? x + CALLOUT_WIDTH : x;
                const mid = y + h / 2;
                const dx = callout.tx - edge;
                const dy = callout.ty - mid;
                const length = Math.hypot(dx, dy) || 1;
                return <path key={callout.key} d={`M${edge},${mid} L${callout.tx - dx / length * 16},${callout.ty - dy / length * 16}`} markerEnd="url(#pg-arrow)"/>;
            })}
        </svg>
        {placed.map(({callout, x, y}) => <div key={callout.key} ref={measure(callout.key)} className="pg-callout" style={{left: x, top: y, width: CALLOUT_WIDTH}}>
            <b><i>i</i>{callout.title}</b>
            <div className="pg-callout-text">{callout.text}</div>
        </div>)}
    </div>;
}

export default function ProcessingGraphView({graph, sections, notice, locked, focus, onFocus}: ProcessingGraphViewProps) {
    const [heights, setHeights] = useState<Partial<Record<NodeId, number>>>({});
    const onMeasure = useCallback((id: NodeId, height: number) => setHeights(previous => previous[id] === height ? previous : {...previous, [id]: height}), []);
    const entryGetters = useRef(new Map<NodeId, () => ExplainEntry[]>());
    const onEntries = useCallback((id: NodeId, entries: () => ExplainEntry[]) => {entryGetters.current.set(id, entries);}, []);
    const layout: StageLayout | null = useMemo(() => 'error' in graph ? null : stageLayout(graph, heights), [graph, heights]);

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
    const [animate, setAnimate] = useState(false);
    const [dragging, setDragging] = useState(false);
    const drag = useRef<{x: number; y: number; camera: Camera} | null>(null);
    /** The camera that centres a box in the canvas, scaled to fill `share` of its width, never above `maxZoom`. */
    const fitBox = (box: {x: number; y: number; w: number; h: number}, share: number, maxZoom: number): Camera => {
        const z = Math.min(maxZoom, Math.max(MIN_ZOOM, Math.min((size.w * share - 2 * FIT_MARGIN) / box.w, (size.h - 2 * FIT_MARGIN) / box.h)));
        return {z, x: box.x + box.w / 2 - size.w / 2 / z, y: box.y + box.h / 2 - size.h / 2 / z};
    };
    const target: Camera = !layout || !size.w ? {x: 0, y: 0, z: 1}
        : focus ? fitBox(layout.boxes.get(focus.id)!, focus.explain ? 0.42 : 1, MAX_ZOOM)
            : fitBox({x: 0, y: 0, w: layout.width, h: layout.height}, 1, 1);
    // A focus change hands the camera back to the target and animates there; the reader's own panning and zooming is immediate.
    useEffect(() => {
        setCamera(null);
        setAnimate(true);
        const timer = setTimeout(() => setAnimate(false), 360);
        return () => clearTimeout(timer);
    }, [focus?.id, focus?.explain]);
    const cam = camera ?? target;
    const zoomAbout = (z: number, px: number, py: number): void => {
        const next = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, z));
        setCamera({z: next, x: cam.x + px / cam.z - px / next, y: cam.y + py / cam.z - py / next});
    };
    const onWheel = (event: WheelEvent<HTMLDivElement>): void => {
        if (focus?.explain) return;
        const rect = event.currentTarget.getBoundingClientRect();
        zoomAbout(cam.z * Math.exp(-event.deltaY * 0.0015), event.clientX - rect.left, event.clientY - rect.top);
    };
    const onPointerDown = (event: PointerEvent<HTMLDivElement>): void => {
        if ((event.target as Element).closest('.pg-node, .pg-zoom') || focus?.explain) return;
        event.currentTarget.setPointerCapture(event.pointerId);
        drag.current = {x: event.clientX, y: event.clientY, camera: cam};
        setDragging(false);
    };
    const onPointerMove = (event: PointerEvent<HTMLDivElement>): void => {
        const start = drag.current;
        if (!start) return;
        if (!dragging && Math.hypot(event.clientX - start.x, event.clientY - start.y) < 4) return;
        setDragging(true);
        setCamera({z: start.camera.z, x: start.camera.x - (event.clientX - start.x) / start.camera.z, y: start.camera.y - (event.clientY - start.y) / start.camera.z});
    };
    const onPointerUp = (): void => {
        // A click on empty canvas, not a drag, leaves the zoomed node.
        if (drag.current && !dragging && focus) onFocus(null);
        drag.current = null;
        setDragging(false);
    };

    const nodeElements = useRef(new Map<NodeId, HTMLElement>());
    const [explainReady, setExplainReady] = useState(false);
    useEffect(() => {
        setExplainReady(false);
        if (!focus?.explain) return;
        const timer = setTimeout(() => setExplainReady(true), 380);
        return () => clearTimeout(timer);
    }, [focus?.id, focus?.explain]);

    const byId = new Map(sections.map(section => [section.id, section]));
    return <div ref={canvasRef} className={`pg-canvas${dragging ? ' dragging' : ''}${focus?.explain ? ' explaining' : ''}`} onWheel={onWheel}
        onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={onPointerUp} onPointerCancel={onPointerUp}
        onKeyDown={event => {if (event.key === 'Escape' && focus) onFocus(null);}} aria-label="Processing graph. Drag to pan, scroll to zoom.">
        {'error' in graph && <p role="alert" className="pg-notice warn">{graph.error}</p>}
        {notice}
        {layout && 'nodes' in graph && size.w > 0 && <div className={`pg-world${animate ? ' animate' : ''}`}
            style={{width: layout.width, height: layout.height, transform: `scale(${cam.z}) translate(${-cam.x}px, ${-cam.y}px)`}}>
            <svg className="pg-wires" width={layout.width} height={layout.height} aria-hidden="true">
                {graph.wires.map(wire => <path key={wire.id} d={layout.wires.find(item => item.id === wire.id)!.d}
                    className={`pg-wire${wire.active ? '' : ' quiet'}${graph.nodes.find(node => node.id === wire.target)!.state === 'running' ? ' flow' : ''}`}
                    style={{stroke: colour(wire.data)}}/>)}
            </svg>
            {focus?.explain && <div className="pg-explain-cover"/>}
            {graph.nodes.map(node => <div key={node.id} ref={element => {if (element) nodeElements.current.set(node.id, element.firstElementChild as HTMLElement);}}>
                <Node node={node} section={byId.get(node.id)!} box={layout.boxes.get(node.id)!} focused={focus?.id === node.id}
                    explaining={focus?.id === node.id && focus.explain} locked={locked} onMeasure={onMeasure} onFocus={onFocus} onEntries={onEntries}/>
            </div>)}
        </div>}
        {focus?.explain && explainReady && canvasRef.current && nodeElements.current.get(focus.id) &&
            <Explain entries={entryGetters.current.get(focus.id)?.() ?? []} nodeElement={nodeElements.current.get(focus.id)!}
                canvasElement={canvasRef.current} size={size} onClose={() => onFocus(null)}/>}
        <div className="pg-zoom" role="toolbar" aria-label="Zoom">
            <button type="button" aria-label="Zoom out" onClick={() => zoomAbout(cam.z / 1.2, size.w / 2, size.h / 2)}>−</button>
            <span>{Math.round(cam.z * 100)}%</span>
            <button type="button" aria-label="Zoom in" onClick={() => zoomAbout(cam.z * 1.2, size.w / 2, size.h / 2)}>+</button>
            <button type="button" onClick={() => {onFocus(null); setCamera(null);}}>Fit all</button>
        </div>
    </div>;
}
