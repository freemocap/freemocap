// Two rows that read like lines of text: the recording and stages 1-3, then stages 4 and 5 with Blender and the
// exports. One wire wraps from stage 3 down to stages 4 and 5; calibration loops over stage 1; landmarks reach the
// exports under Blender, and segments over it. Node heights are measured from the rendered cards; ports sit at fixed rows at their top.
import {type DataKey, type GraphNode, type NodeId, type StageGraph} from './stage-graph';

export const NODE_WIDTH = 360;
export const ROWS = {head: 44, portsPad: 6, port: 26};
const GAP = 64;
const ROW_GAP = 76;
const MARGIN = 40;
const ROW1: NodeId[] = ['recording', 'observations', 'triangulation', 'filtering'];
const ROW2: NodeId[] = ['scale_fit', 'reconstruction', 'blender', 'exports'];

export interface Box {x: number; y: number; w: number; h: number}
export interface StageLayout {
    boxes: Map<NodeId, Box>;
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

export function stageLayout(graph: StageGraph, heights: Partial<Record<NodeId, number>>): StageLayout {
    const node = (id: NodeId): GraphNode => graph.nodes.find(item => item.id === id)!;
    const height = (id: NodeId): number => heights[id] ?? ROWS.head + ROWS.portsPad * 2 + ROWS.port * (node(id).inputs.length + node(id).outputs.length);
    const boxes = new Map<NodeId, Box>();
    ROW1.forEach((id, i) => boxes.set(id, {x: MARGIN + i * (NODE_WIDTH + GAP), y: MARGIN, w: NODE_WIDTH, h: height(id)}));
    // The recording sits lower so its videos wire runs straight into stage 1.
    boxes.get('recording')!.y = MARGIN + portOffset(node('observations'), 'in', 'videos') - portOffset(node('recording'), 'out', 'videos');
    const row1Bottom = Math.max(...ROW1.map(id => boxes.get(id)!.y + height(id)));
    const row2Top = row1Bottom + ROW_GAP;
    ROW2.forEach((id, i) => boxes.set(id, {x: MARGIN + i * (NODE_WIDTH + GAP), y: row2Top, w: NODE_WIDTH, h: height(id)}));
    // Stage 4 sits lower so its body dimensions wire runs straight into stage 5, under the wrap's drop.
    const fit = boxes.get('scale_fit')!;
    fit.y = row2Top + portOffset(node('reconstruction'), 'in', 'dimensions') - portOffset(node('scale_fit'), 'out', 'dimensions');
    const mid = row1Bottom + ROW_GAP / 2;
    const port = (id: NodeId, direction: 'in' | 'out', data: DataKey) => {
        const box = boxes.get(id)!;
        return {x: direction === 'out' ? box.x + box.w : box.x, y: box.y + portOffset(node(id), direction, data)};
    };
    const wires = graph.wires.map(wire => {
        const a = port(wire.source, 'out', wire.data);
        const b = port(wire.target, 'in', wire.data);
        let d: string;
        if (wire.source === 'recording' && wire.target === 'triangulation') {
            const over = boxes.get('observations')!.y - 24;
            d = `M${a.x},${a.y} C${a.x + 40},${a.y} ${a.x + 20},${over} ${a.x + 70},${over} L${b.x - 60},${over} C${b.x - 20},${over} ${b.x - 34},${b.y} ${b.x},${b.y}`;
        } else if (wire.source === 'filtering') {
            const drop = b.x - 30;
            d = `M${a.x},${a.y} C${a.x + 40},${a.y} ${a.x + 30},${mid} ${a.x - 10},${mid} L${drop + 20},${mid} C${drop - 10},${mid} ${drop - 16},${b.y} ${b.x},${b.y}`;
        } else if (wire.target === 'exports' && wire.source === 'reconstruction' && wire.data === 'segments') {
            // Segments leave above the landmarks socket, so they pass over Blender while landmarks pass under it.
            const over = boxes.get('blender')!.y - 20;
            d = `M${a.x},${a.y} C${a.x + 30},${a.y} ${a.x + 20},${over} ${a.x + 60},${over} L${b.x - 70},${over} C${b.x - 24},${over} ${b.x - 36},${b.y} ${b.x},${b.y}`;
        } else if (wire.target === 'exports' && wire.source === 'reconstruction') {
            const blender = boxes.get('blender')!;
            const under = blender.y + blender.h + 26;
            d = `M${a.x},${a.y} C${a.x + 36},${a.y} ${a.x + 24},${under} ${a.x + 70},${under} L${b.x - 70},${under} C${b.x - 24},${under} ${b.x - 36},${b.y} ${b.x},${b.y}`;
        } else {
            const k = Math.max(36, (b.x - a.x) * 0.5);
            d = `M${a.x},${a.y} C${a.x + k},${a.y} ${b.x - k},${b.y} ${b.x},${b.y}`;
        }
        return {id: wire.id, d};
    });
    const list = [...boxes.values()];
    const under = boxes.get('blender')!.y + boxes.get('blender')!.h + 26;
    return {boxes, wires, width: Math.max(...list.map(box => box.x + box.w)) + MARGIN,
        height: Math.max(under, ...list.map(box => box.y + box.h)) + MARGIN};
}
