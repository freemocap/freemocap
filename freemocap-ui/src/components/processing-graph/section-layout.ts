// Fixed positions for the five sections, arranged so no two wires cross: the videos and 2D keypoints wires run
// straight, calibration loops over SkellyTracker, and SkellyForge's outputs leave in the order Blender takes them.
// Heights come from fixed row sizes that the cards also use, so ports and wires line up with the drawn rows.
import {type SectionGraph, type SectionId, type SectionNode} from './section-graph';

export const ROWS = {head: 62, port: 30, heading: 26, setting: 24, settingsPad: 14, bar: 28, barsPad: 12, foot: 34};
const COLUMN: Record<SectionId, {x: number; w: number}> = {
    recording: {x: 40, w: 290}, tracker: {x: 420, w: 340}, forge: {x: 830, w: 420}, blender: {x: 1350, w: 340}, exports: {x: 1350, w: 340},
};
const TOP = 100;
const MARGIN = 48;

export interface Box {x: number; y: number; w: number; h: number}
export interface SectionLayout {
    boxes: Map<SectionId, Box>;
    wires: {id: string; d: string}[];
    width: number;
    height: number;
}

export function sectionHeight(node: SectionNode): number {
    const settings = node.groups.reduce((sum, group) => sum + (group.heading ? ROWS.heading : 0) + group.rows.length * ROWS.setting, 0);
    return ROWS.head + (node.inputs.length + node.outputs.length) * ROWS.port + ROWS.settingsPad + settings
        + (node.bars.length ? node.bars.length * ROWS.bar + ROWS.barsPad : 0) + ROWS.foot;
}

/** A port's height within its card: inputs first, then outputs, one row each. */
export function portOffset(node: SectionNode, direction: 'in' | 'out', data: string): number {
    const index = direction === 'in' ? node.inputs.indexOf(data as never) : node.inputs.length + node.outputs.indexOf(data as never);
    if (index < (direction === 'in' ? 0 : node.inputs.length)) throw new Error(`${node.title} has no ${direction}put "${data}"`);
    return ROWS.head + index * ROWS.port + ROWS.port / 2;
}

export function sectionLayout(graph: SectionGraph): SectionLayout {
    const node = (id: SectionId): SectionNode => graph.nodes.find(item => item.id === id)!;
    const box = (id: SectionId, y: number): Box => ({...COLUMN[id], y, h: sectionHeight(node(id))});
    const boxes = new Map<SectionId, Box>();
    boxes.set('tracker', box('tracker', TOP));
    boxes.set('forge', box('forge', TOP));
    boxes.set('recording', box('recording', TOP - ROWS.port));
    boxes.set('blender', box('blender', TOP - 20));
    const blender = boxes.get('blender')!;
    boxes.set('exports', box('exports', blender.y + blender.h + 42));
    const over = TOP - 36;
    const wires = graph.wires.map(wire => {
        const a = boxes.get(wire.source)!;
        const b = boxes.get(wire.target)!;
        const x1 = a.x + a.w;
        const y1 = a.y + portOffset(node(wire.source), 'out', wire.data);
        const x2 = b.x;
        const y2 = b.y + portOffset(node(wire.target), 'in', wire.data);
        if (wire.source === 'recording' && wire.target === 'forge') {
            return {id: wire.id, d: `M${x1},${y1} C${x1 + 50},${y1} ${x1 + 30},${over} ${x1 + 90},${over} L${x2 - 70},${over} C${x2 - 30},${over} ${x2 - 40},${y2} ${x2},${y2}`};
        }
        const k = Math.max(40, (x2 - x1) * 0.5);
        return {id: wire.id, d: `M${x1},${y1} C${x1 + k},${y1} ${x2 - k},${y2} ${x2},${y2}`};
    });
    const boxList = [...boxes.values()];
    return {boxes, wires, width: Math.max(...boxList.map(item => item.x + item.w)) + MARGIN,
        height: Math.max(...boxList.map(item => item.y + item.h)) + MARGIN};
}
