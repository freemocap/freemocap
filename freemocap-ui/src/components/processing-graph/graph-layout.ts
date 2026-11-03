// Node geometry ported from the Graph Lab viewer (experiments/executable_graph_lab/synthetic/viewer.html),
// and a straight-line layout: the main work runs in one line; loads and saves hang off it one step later.
// Geometry never depends on zoom: the view scales the whole drawing.
import type {DisplayEdge, DisplayGraph, DisplayNode} from './graph-model';

export type GraphDirection = 'right' | 'down';

export interface Point {x: number; y: number}

export interface NodeGeometry {
    /** Full footprint including the disk card. */
    w: number;
    h: number;
    /** The node card itself. */
    bw: number;
    bh: number;
    ports: Map<string, Point>;
    headTop: number;
    footTop: number;
    split: number;
    sourceY: number;
}

export interface NodeBox extends NodeGeometry {x: number; y: number}

export interface GraphLayout {
    boxes: Map<string, NodeBox>;
    paths: {edge: DisplayEdge; d: string}[];
    width: number;
    height: number;
}

export const LR_WIDTH = 264;
const LR_TOP = 56;
const LR_ROW = 26;
const TD_HEIGHT = 130;
/** Height of one per-video progress lane. */
export const LANE_ROW = 24;

/** A load card lists the files the plan reads; a save card has one line until the run reports what it wrote. */
export const diskFileRows = (node: DisplayNode): number => node.io === 'read' ? Math.max(node.files.length, 1) : 1;

export function nodeGeometry(node: DisplayNode, direction: GraphDirection): NodeGeometry {
    const ins = node.inputs;
    const outs = node.outputs;
    const ports = new Map<string, Point>();
    const io = node.io !== null;
    if (direction === 'right') {
        const inRows = Math.max(ins.length, 1);
        const rowY = (row: number): number => LR_TOP + row * LR_ROW + LR_ROW / 2;
        ins.forEach((slot, row) => ports.set(`in:${slot.name}`, {x: 0, y: rowY(row)}));
        outs.forEach((slot, row) => ports.set(`out:${slot.name}`, {x: LR_WIDTH, y: rowY(inRows + row)}));
        const base = LR_TOP + (inRows + outs.length) * LR_ROW + 6 + 28;
        const h = base + node.lanes.length * LANE_ROW + (node.lanes.length ? 6 : 0);
        const diskRows = diskFileRows(node);
        return {w: LR_WIDTH, h: h + (io ? 34 + Math.max(40, 30 + diskRows * 16) + 12 : 0), bw: LR_WIDTH, bh: h, ports,
            headTop: 0, footTop: base - 28, split: LR_TOP + inRows * LR_ROW, sourceY: rowY(0)};
    }
    const w = Math.max(240, Math.max(ins.length, outs.length) * 128);
    const bh = TD_HEIGHT + node.lanes.length * LANE_ROW;
    ins.forEach((slot, i) => ports.set(`in:${slot.name}`, {x: w * (i + 0.5) / ins.length, y: 0}));
    outs.forEach((slot, j) => ports.set(`out:${slot.name}`, {x: w * (j + 0.5) / outs.length, y: bh}));
    const diskRows = diskFileRows(node);
    return {w: w + (io ? 34 + 26 + 66 + 8 : 0), h: Math.max(bh, io ? 96 + diskRows * 16 : 0), bw: w, bh, ports,
        headTop: 26, footTop: 76, split: 0, sourceY: 0};
}

const MARGIN = 48;
const round = (value: number): number => Math.round(value * 10) / 10;

/** Main work: nodes that neither save nor annotate. */
const onLine = (node: DisplayNode): boolean => node.io !== 'write' && !node.annotation;

/**
 * The main work sits in one line in plan order, each node aligned so the wire from the node before it is straight.
 * Every other node hangs below (left to right) or beside (top down) the line, one step after the last node it reads from.
 */
export function computeLayout(graph: DisplayGraph, direction: GraphDirection): GraphLayout {
    const {nodes, edges} = graph;
    const side = direction === 'right';
    const mainGap = 56;
    const crossGap = side ? 28 : 40;
    const lineGap = side ? 44 : 56;
    const byId = new Map(nodes.map(node => [node.id, node]));
    for (const edge of edges) {
        if (!byId.has(edge.source) || !byId.has(edge.target)) throw new Error(`Edge ${edge.id} references an unknown node`);
    }
    const geometry = new Map(nodes.map(node => [node.id, nodeGeometry(node, direction)]));
    const sources = (id: string): string[] => [...new Set(edges.filter(edge => edge.target === id).map(edge => edge.source))];
    const column = new Map<string, number>();
    let lineColumn = -1;
    for (const node of nodes) {
        const after = sources(node.id).map(id => {
            const value = column.get(id);
            if (value === undefined) throw new Error(`"${node.id}" is drawn before its source "${id}"`);
            return value + 1;
        });
        const value = Math.max(0, ...after, onLine(node) ? lineColumn + 1 : 0);
        column.set(node.id, value);
        if (onLine(node)) lineColumn = value;
    }
    const mainSize = (id: string): number => side ? geometry.get(id)!.w : geometry.get(id)!.h;
    const crossSize = (id: string): number => side ? geometry.get(id)!.h : geometry.get(id)!.w;
    const columns = Math.max(...column.values()) + 1;
    const columnSize = Array.from({length: columns}, (_, c) => Math.max(0, ...nodes.filter(node => column.get(node.id) === c).map(node => mainSize(node.id))));
    const columnPos: number[] = [];
    let main = MARGIN;
    columnSize.forEach((size, c) => {
        columnPos[c] = main;
        main += size + mainGap;
    });
    const portCross = (id: string, key: string): number => {
        const port = geometry.get(id)!.ports.get(key);
        if (!port) throw new Error(`Missing declared slot ${key} on ${id}`);
        return side ? port.y : port.x;
    };
    // The line: each node lines up its input with the output of the line node before it.
    const cross = new Map<string, number>();
    const line = nodes.filter(onLine);
    line.forEach((node, index) => {
        if (index === 0) {
            cross.set(node.id, 0);
            return;
        }
        const previous = line[index - 1];
        const wire = edges.find(edge => edge.source === previous.id && edge.target === node.id);
        cross.set(node.id, wire
            ? cross.get(previous.id)! + portCross(previous.id, `out:${wire.sourceSlot}`) - portCross(node.id, `in:${wire.targetSlot}`)
            : cross.get(previous.id)!);
    });
    const lineTop = Math.min(0, ...line.map(node => cross.get(node.id)!));
    const lineEnd = Math.max(0, ...line.map(node => cross.get(node.id)! + crossSize(node.id)));
    // Hanging nodes stack away from the line within their column.
    const stack = new Map<number, number>();
    for (const node of nodes.filter(item => !onLine(item))) {
        const c = column.get(node.id)!;
        const at = stack.get(c) ?? lineEnd + lineGap;
        cross.set(node.id, at);
        stack.set(c, at + crossSize(node.id) + crossGap);
    }
    const shift = MARGIN - lineTop;
    const pt = (a: number, c: number): Point => side ? {x: a, y: c} : {x: c, y: a};
    const boxes = new Map<string, NodeBox>();
    for (const node of nodes) boxes.set(node.id, {...geometry.get(node.id)!, ...pt(columnPos[column.get(node.id)!], cross.get(node.id)! + shift)});
    const portAbs = (id: string, key: string): Point => {
        const box = boxes.get(id)!;
        const port = box.ports.get(key);
        if (!port) throw new Error(`Missing declared slot ${key} on ${id}`);
        return {x: box.x + port.x, y: box.y + port.y};
    };
    const curve = (p: Point, q: Point): string => {
        if (side) {
            const k = Math.max(28, (q.x - p.x) * 0.5);
            return `M${round(p.x)},${round(p.y)} C${round(p.x + k)},${round(p.y)} ${round(q.x - k)},${round(q.y)} ${round(q.x)},${round(q.y)}`;
        }
        const k = Math.max(28, (q.y - p.y) * 0.5);
        return `M${round(p.x)},${round(p.y)} C${round(p.x)},${round(p.y + k)} ${round(q.x)},${round(q.y - k)} ${round(q.x)},${round(q.y)}`;
    };
    const paths = edges.map(edge => ({edge, d: curve(portAbs(edge.source, `out:${edge.sourceSlot}`), portAbs(edge.target, `in:${edge.targetSlot}`))}));
    let hi = 0;
    for (const node of nodes) hi = Math.max(hi, cross.get(node.id)! + shift + crossSize(node.id));
    const totalMain = main - mainGap + MARGIN;
    const totalCross = hi + MARGIN;
    return {boxes, paths, width: side ? totalMain : totalCross, height: side ? totalCross : totalMain};
}
