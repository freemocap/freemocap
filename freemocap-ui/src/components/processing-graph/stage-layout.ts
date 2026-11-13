// Two rows that read like lines of text: the graph's first four nodes, then the rest. For posthoc that is the
// recording and stages 1-3, then stages 4 and 5 with Blender and the exports; for realtime, the cameras and stages
// 1-3, then skeleton reconstruction with the streaming outputs. One wire wraps from stage 3 down to row two;
// calibration loops over stage 1; landmarks reach the last node under the node before it, and segments over it.
// Node heights are measured from the rendered cards; ports sit at fixed rows at their top.
import {type DataKey, type GraphNode, type GraphNodeId, type StageGraph} from './stage-graph';

export const NODE_WIDTH = 360;
export const ROWS = {head: 44, portsPad: 6, port: 26};
const GAP = 64;
const ROW_GAP = 76;
const MARGIN = 40;
/** How many of the graph's nodes make row one. */
const ROW_ONE_LENGTH = 4;

export interface Box {x: number; y: number; w: number; h: number}
export interface StageLayout {
    /** Each node's box, by node id. */
    boxes: Map<string, Box>;
    wires: {id: string; d: string}[];
    width: number;
    height: number;
}

/** A port's height within its card: outputs first, then inputs, one row each. */
export function portOffset(node: GraphNode, direction: 'in' | 'out', data: DataKey): number {
    const index = direction === 'out' ? node.outputs.indexOf(data) : node.outputs.length + node.inputs.indexOf(data);
    if ((direction === 'out' ? node.outputs : node.inputs).indexOf(data) < 0) throw new Error(`${node.id} has no ${direction}put "${data}"`);
    return ROWS.head + ROWS.portsPad + index * ROWS.port + ROWS.port / 2;
}

/**
 * Lays out a graph by its node order: its first four nodes in row one, the rest in row two. Both pipelines' graphs
 * fill row one and put at least two nodes in row two. `heights` are the measured card heights, by node id.
 */
export function stageLayout(graph: StageGraph, heights: Partial<Record<string, number>>): StageLayout {
    const node = (id: GraphNodeId): GraphNode => graph.nodes.find(item => item.id === id)!;
    const height = (id: GraphNodeId): number => heights[id] ?? ROWS.head + ROWS.portsPad * 2 + ROWS.port * (node(id).inputs.length + node(id).outputs.length);
    const row1 = graph.nodes.slice(0, ROW_ONE_LENGTH).map(item => item.id);
    const row2 = graph.nodes.slice(ROW_ONE_LENGTH).map(item => item.id);
    // The wires that do not run straight to a neighbour are told by where their ends sit in the rows, and by the two
    // stages they leave, filtering and reconstruction, which both pipelines have.
    const [first, second, third] = row1;
    const last = row2[row2.length - 1];
    const beforeLast = row2[row2.length - 2];
    const boxes = new Map<string, Box>();
    row1.forEach((id, i) => boxes.set(id, {x: MARGIN + i * (NODE_WIDTH + GAP), y: MARGIN, w: NODE_WIDTH, h: height(id)}));
    // The first node sits where the wire it shares with the second (the recording's videos, the cameras' frames) runs straight.
    const shared = node(second).inputs.find(data => node(first).outputs.includes(data));
    if (shared) boxes.get(first)!.y = MARGIN + portOffset(node(second), 'in', shared) - portOffset(node(first), 'out', shared);
    const row1Bottom = Math.max(...row1.map(id => boxes.get(id)!.y + height(id)));
    const row2Top = row1Bottom + ROW_GAP;
    row2.forEach((id, i) => boxes.set(id, {x: MARGIN + i * (NODE_WIDTH + GAP), y: row2Top, w: NODE_WIDTH, h: height(id)}));
    // Posthoc's stage 4 sits lower so its body dimensions wire runs straight into stage 5, under the wrap's drop.
    const fit = boxes.get('scale_fit');
    if (fit) fit.y = row2Top + portOffset(node('reconstruction'), 'in', 'dimensions') - portOffset(node('scale_fit'), 'out', 'dimensions');
    const mid = row1Bottom + ROW_GAP / 2;
    const port = (id: GraphNodeId, direction: 'in' | 'out', data: DataKey) => {
        const box = boxes.get(id)!;
        return {x: direction === 'out' ? box.x + box.w : box.x, y: box.y + portOffset(node(id), direction, data)};
    };
    const wires = graph.wires.map(wire => {
        const a = port(wire.source, 'out', wire.data);
        const b = port(wire.target, 'in', wire.data);
        let d: string;
        if (wire.source === first && wire.target === third) {
            const over = boxes.get(second)!.y - 24;
            d = `M${a.x},${a.y} C${a.x + 40},${a.y} ${a.x + 20},${over} ${a.x + 70},${over} L${b.x - 60},${over} C${b.x - 20},${over} ${b.x - 34},${b.y} ${b.x},${b.y}`;
        } else if (wire.source === 'filtering') {
            const drop = b.x - 30;
            d = `M${a.x},${a.y} C${a.x + 40},${a.y} ${a.x + 30},${mid} ${a.x - 10},${mid} L${drop + 20},${mid} C${drop - 10},${mid} ${drop - 16},${b.y} ${b.x},${b.y}`;
        } else if (wire.target === last && wire.source === 'reconstruction' && wire.data === 'segments') {
            // Segments leave above the landmarks socket, so they pass over the node before the last (Blender, VMC) while landmarks pass under it.
            const over = boxes.get(beforeLast)!.y - 20;
            d = `M${a.x},${a.y} C${a.x + 30},${a.y} ${a.x + 20},${over} ${a.x + 60},${over} L${b.x - 70},${over} C${b.x - 24},${over} ${b.x - 36},${b.y} ${b.x},${b.y}`;
        } else if (wire.target === last && wire.source === 'reconstruction') {
            const passed = boxes.get(beforeLast)!;
            const under = passed.y + passed.h + 26;
            d = `M${a.x},${a.y} C${a.x + 36},${a.y} ${a.x + 24},${under} ${a.x + 70},${under} L${b.x - 70},${under} C${b.x - 24},${under} ${b.x - 36},${b.y} ${b.x},${b.y}`;
        } else {
            const k = Math.max(36, (b.x - a.x) * 0.5);
            d = `M${a.x},${a.y} C${a.x + k},${a.y} ${b.x - k},${b.y} ${b.x},${b.y}`;
        }
        return {id: wire.id, d};
    });
    const list = [...boxes.values()];
    const under = boxes.get(beforeLast)!.y + boxes.get(beforeLast)!.h + 26;
    return {boxes, wires, width: Math.max(...list.map(box => box.x + box.w)) + MARGIN,
        height: Math.max(under, ...list.map(box => box.y + box.h)) + MARGIN};
}
