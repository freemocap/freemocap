import {type KeyboardEvent, type PointerEvent, type ReactNode, type WheelEvent, useEffect, useMemo, useRef, useState} from 'react';
import type {ProcessingPlanState} from '@/hooks/useProcessingPlan';
import {displayGraph, type DisplayGraph, type DisplayNode, type DisplaySlot, type SettingsSectionName} from './graph-model';
import {computeLayout, NODE_HEADER, NODE_WIDTH, SLOT_ROW, type GraphLayout, type NodeBox} from './graph-layout';
import './processing-graph.css';

interface ProcessingGraphViewProps {
    planState: ProcessingPlanState;
    /** The real settings section, rendered in the inspector for the selected node. */
    sectionContent: (section: SettingsSectionName) => ReactNode;
}

interface ViewTransform {x: number; y: number; k: number}

const MIN_ZOOM = 0.2;
const MAX_ZOOM = 2;

const slotText = (slot: DisplaySlot): string => {
    if (slot.name === '@read_record') return 'reads record';
    if (slot.name === '@read_live') return 'reads live source';
    if (slot.name === '@write_disk') return 'writes to disk';
    if (slot.name === '@display') return 'shows result';
    return slot.name;
};
const kindText = (kind: string): string => kind.replace(/_/g, ' ');
const basename = (path: string): string => path.split(/[\\/]/).filter(Boolean).pop() ?? path;
/** Average advance of the 11.5px slot font; labels are cut to stay inside the node. */
const SLOT_CHARACTER_WIDTH = 6.4;
const SLOT_TEXT_WIDTH = NODE_WIDTH - 28;
const fitText = (text: string, room: number): string => {
    const limit = Math.floor(room / SLOT_CHARACTER_WIDTH);
    return text.length > limit ? `${text.slice(0, Math.max(0, limit - 1))}…` : text;
};

function fitTransform(layout: GraphLayout, width: number, height: number): ViewTransform {
    const k = Math.min(1, width / layout.width, height / layout.height);
    return {k, x: (width - layout.width * k) / 2, y: (height - layout.height * k) / 2};
}

function TerminalIcon({node}: {node: DisplayNode}) {
    if (node.effect === 'display') {
        return <g aria-hidden="true" className="graph-terminal-icon"><rect x={12} y={14} width={18} height={12} rx={2}/><path d="M17 30h8M21 26v4"/></g>;
    }
    if (node.effect === 'read_live') {
        return <g aria-hidden="true" className="graph-terminal-icon"><rect x={12} y={15} width={13} height={12} rx={2}/><path d="M25 19l6-3v10l-6-3"/></g>;
    }
    return <g aria-hidden="true" className="graph-terminal-icon"><ellipse cx={21} cy={15} rx={8} ry={3}/><path d="M13 15v13c0 1.7 3.6 3 8 3s8-1.3 8-3V15"/><path d="M13 21.5c0 1.7 3.6 3 8 3s8-1.3 8-3"/></g>;
}

function GraphNodeShape({node, box, selected, onSelect}: {node: DisplayNode; box: NodeBox; selected: boolean; onSelect: () => void}) {
    const onKeyDown = (event: KeyboardEvent<SVGGElement>): void => {
        if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            onSelect();
        }
    };
    const common = {transform: `translate(${box.x},${box.y})`, role: 'button', tabIndex: 0, 'aria-label': node.title,
        'aria-pressed': selected, onClick: onSelect, onKeyDown, onPointerDown: (event: PointerEvent) => event.stopPropagation()};
    if (node.role !== 'operation') {
        const verb = node.role === 'source' ? 'Reads' : node.effect === 'display' ? 'Shows' : 'Writes';
        return <g {...common} className={`graph-terminal graph-terminal-${node.role}${selected ? ' selected' : ''}`}>
            <rect width={box.w} height={box.h} rx={box.h / 2}/>
            <TerminalIcon node={node}/>
            <text x={40} y={18} className="graph-terminal-verb">{verb}</text>
            <text x={40} y={33} className="graph-terminal-title">{node.title.length > 22 ? `${node.title.slice(0, 21)}…` : node.title}</text>
            <circle cx={node.role === 'source' ? box.w : 0} cy={box.h / 2} r={3.5} className="graph-port"/>
        </g>;
    }
    const rows = [...node.inputs.map(slot => ({slot, side: 'in' as const})), ...node.outputs.map(slot => ({slot, side: 'out' as const}))];
    return <g {...common} className={`graph-node${selected ? ' selected' : ''}`}>
        <rect width={box.w} height={box.h} rx={6}/>
        <text x={12} y={17} className="graph-node-stage">{node.stageLabel}</text>
        <text x={12} y={35} className="graph-node-title">{node.title}</text>
        <line x1={0} x2={box.w} y1={NODE_HEADER - 4} y2={NODE_HEADER - 4} className="graph-node-divider"/>
        {rows.map(({slot, side}, row) => {
            const y = NODE_HEADER + row * SLOT_ROW + SLOT_ROW / 2;
            const effect = slot.name.startsWith('@');
            const name = slotText(slot);
            const kind = effect ? '' : fitText(kindText(slot.kind), SLOT_TEXT_WIDTH - (name.length + 2) * SLOT_CHARACTER_WIDTH);
            return <g key={`${side}:${slot.name}`}>
                <title>{effect ? name : `${slot.name}: ${kindText(slot.kind)}`}</title>
                <circle cx={side === 'in' ? 0 : box.w} cy={y} r={3.5} className={`graph-port${effect ? ' graph-port-effect' : ''}`}/>
                <text x={side === 'in' ? 12 : box.w - 12} y={y + 4} textAnchor={side === 'in' ? 'start' : 'end'}
                    className={effect ? 'graph-slot graph-slot-effect' : 'graph-slot'}>
                    {fitText(name, SLOT_TEXT_WIDTH)}{kind && <tspan className="graph-slot-kind">{`  ${kind}`}</tspan>}
                </text>
            </g>;
        })}
    </g>;
}

function Inspector({node, sectionContent, planId}: {node: DisplayNode | null; sectionContent: ProcessingGraphViewProps['sectionContent']; planId: string}) {
    if (!node) {
        return <aside className="graph-inspector" aria-label="Node details">
            <p className="settings-note">Select a node to see what it reads, writes and which settings control it.</p>
            <p className="settings-note">Plan <code>{planId.slice(0, 12)}</code></p>
        </aside>;
    }
    if (node.role !== 'operation') {
        return <aside className="graph-inspector" aria-label="Node details">
            <h3 className="graph-inspector-title">{node.title}</h3>
            <p className="settings-note">{node.role === 'source' ? 'Where data enters the plan.' : 'Where data leaves the plan.'}</p>
            {node.files.length > 0 && <ul className="graph-inspector-files">{node.files.map(file => <li key={file} title={file}><code>{basename(file)}</code></li>)}</ul>}
        </aside>;
    }
    return <aside className="graph-inspector" aria-label="Node details">
        <p className="graph-inspector-stage">{node.stageLabel}</p>
        <h3 className="graph-inspector-title">{node.title}</h3>
        <p className="settings-note"><code>{node.id}</code></p>
        {node.files.length > 0 && <>
            <p className="settings-note">Reads</p>
            <ul className="graph-inspector-files">{node.files.map(file => <li key={file} title={file}><code>{basename(file)}</code></li>)}</ul>
        </>}
        {node.section && <div className="graph-inspector-settings">
            <p className="graph-inspector-stage">Settings · {node.section}</p>
            {sectionContent(node.section)}
        </div>}
    </aside>;
}

/** The plan the server would run, drawn from sources to sinks, with the selected node's settings beside it. */
export default function ProcessingGraphView({planState, sectionContent}: ProcessingGraphViewProps) {
    const {preview, loading, failure} = planState;
    const built = useMemo((): {graph: DisplayGraph; layout: GraphLayout} | {error: string} | null => {
        if (!preview?.plan) return null;
        try {
            const graph = displayGraph(preview.plan);
            return {graph, layout: computeLayout(graph)};
        } catch (reason) {
            return {error: reason instanceof Error ? reason.message : String(reason)};
        }
    }, [preview]);
    const canvasRef = useRef<HTMLDivElement>(null);
    const [transform, setTransform] = useState<ViewTransform>({x: 0, y: 0, k: 1});
    const [selectedId, setSelectedId] = useState<string | null>(null);
    const drag = useRef<{x: number; y: number; start: ViewTransform} | null>(null);

    const layout = built && 'layout' in built ? built.layout : null;
    const fit = (): void => {
        const canvas = canvasRef.current;
        if (canvas && layout) setTransform(fitTransform(layout, canvas.clientWidth, canvas.clientHeight));
    };
    useEffect(fit, [layout]);
    useEffect(() => {
        if (built && 'graph' in built && selectedId && !built.graph.nodes.some(node => node.id === selectedId)) setSelectedId(null);
    }, [built, selectedId]);

    const onWheel = (event: WheelEvent<HTMLDivElement>): void => {
        const rect = event.currentTarget.getBoundingClientRect();
        const px = event.clientX - rect.left;
        const py = event.clientY - rect.top;
        setTransform(current => {
            const k = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, current.k * Math.exp(-event.deltaY * 0.0015)));
            return {k, x: px - (px - current.x) * (k / current.k), y: py - (py - current.y) * (k / current.k)};
        });
    };
    const onPointerDown = (event: PointerEvent<HTMLDivElement>): void => {
        event.currentTarget.setPointerCapture(event.pointerId);
        drag.current = {x: event.clientX, y: event.clientY, start: transform};
    };
    const onPointerMove = (event: PointerEvent<HTMLDivElement>): void => {
        const start = drag.current;
        if (start) setTransform({...start.start, x: start.start.x + event.clientX - start.x, y: start.start.y + event.clientY - start.y});
    };
    const onPointerUp = (): void => {
        drag.current = null;
    };

    let body: ReactNode;
    if (failure) body = <p role="alert" className="settings-note settings-note-error graph-message">Could not build the processing plan: {failure}</p>;
    else if (preview && preview.errors.length) {
        body = <div role="alert" className="graph-message">
            <p className="settings-note settings-note-error">Process cannot run with these settings:</p>
            <ul>{preview.errors.map(error => <li key={error} className="settings-note settings-note-error">{error}</li>)}</ul>
        </div>;
    } else if (built && 'error' in built) body = <p role="alert" className="settings-note settings-note-error graph-message">{built.error}</p>;
    else if (!built) body = <p role="status" className="settings-note graph-message">{loading ? 'Building the processing plan…' : 'Choose a recording and at least one stage to see the plan.'}</p>;
    else {
        const {graph} = built;
        body = <svg className="graph-svg" role="group" aria-label="Processing plan">
            <g transform={`translate(${transform.x},${transform.y}) scale(${transform.k})`}>
                {built.layout.paths.map(({edge, d}) => <path key={edge.id} d={d}
                    className={edge.sourceSlot.startsWith('@') || edge.targetSlot.startsWith('@') ? 'graph-edge graph-edge-effect' : 'graph-edge'}/>)}
                {graph.nodes.map(node => <GraphNodeShape key={node.id} node={node} box={built.layout.boxes.get(node.id)!}
                    selected={node.id === selectedId} onSelect={() => setSelectedId(node.id)}/>)}
            </g>
        </svg>;
    }
    const selected = built && 'graph' in built ? built.graph.nodes.find(node => node.id === selectedId) ?? null : null;

    return <div className="graph-view">
        <div className="graph-canvas-column">
            <div className="graph-toolbar">
                <span className="settings-note">{loading ? 'Updating plan…' : built && 'graph' in built ? `${built.graph.nodes.filter(node => node.role === 'operation').length} operations` : ''}</span>
                <span className="graph-toolbar-spacer"/>
                <span className="settings-note">{Math.round(transform.k * 100)}%</span>
                <button type="button" className="graph-toolbar-button" onClick={fit} disabled={!layout}>Fit</button>
            </div>
            <div ref={canvasRef} className="graph-canvas" onWheel={onWheel} onPointerDown={onPointerDown}
                onPointerMove={onPointerMove} onPointerUp={onPointerUp} onPointerCancel={onPointerUp}>
                {body}
            </div>
        </div>
        <Inspector node={selected} sectionContent={sectionContent} planId={preview?.plan?.plan_id ?? ''}/>
    </div>;
}
