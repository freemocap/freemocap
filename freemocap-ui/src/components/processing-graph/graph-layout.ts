// Layered layout ported from experiments/executable_graph_lab/production_view/layout.js (left to right).
// Geometry never depends on zoom: the view scales the whole drawing.
import type {DisplayEdge, DisplayGraph, DisplayNode} from './graph-model';

export const NODE_WIDTH = 248;
export const NODE_HEADER = 46;
export const SLOT_ROW = 24;
export const NODE_FOOT = 8;
export const TERMINAL_WIDTH = 184;
export const TERMINAL_HEIGHT = 44;

export interface Point {x: number; y: number}

export interface NodeGeometry {
    w: number;
    h: number;
    /** Slot positions relative to the node's top-left, keyed 'in:<slot>' or 'out:<slot>'. */
    ports: Map<string, Point>;
}

export interface NodeBox extends NodeGeometry {x: number; y: number}

export interface GraphLayout {
    boxes: Map<string, NodeBox>;
    paths: {edge: DisplayEdge; d: string}[];
    width: number;
    height: number;
}

export function nodeGeometry(node: DisplayNode): NodeGeometry {
    const ports = new Map<string, Point>();
    if (node.role !== 'operation') {
        node.inputs.forEach(slot => ports.set(`in:${slot.name}`, {x: 0, y: TERMINAL_HEIGHT / 2}));
        node.outputs.forEach(slot => ports.set(`out:${slot.name}`, {x: TERMINAL_WIDTH, y: TERMINAL_HEIGHT / 2}));
        return {w: TERMINAL_WIDTH, h: TERMINAL_HEIGHT, ports};
    }
    const rowY = (row: number): number => NODE_HEADER + row * SLOT_ROW + SLOT_ROW / 2;
    node.inputs.forEach((slot, row) => ports.set(`in:${slot.name}`, {x: 0, y: rowY(row)}));
    node.outputs.forEach((slot, row) => ports.set(`out:${slot.name}`, {x: NODE_WIDTH, y: rowY(node.inputs.length + row)}));
    return {w: NODE_WIDTH, h: NODE_HEADER + (node.inputs.length + node.outputs.length) * SLOT_ROW + NODE_FOOT, ports};
}

interface LayoutItem {id: string; rank: number; dummy: boolean; main: number; cross: number; order: number}
interface Link {a: string; b: string; aOff: number; bOff: number}
interface Neighbour {o: string; self: number; other: number}

const DUMMY = 8;
const MARGIN = 48;
const MAIN_GAP = 112;
const CROSS_GAP = 28;
const round = (value: number): number => Math.round(value * 10) / 10;

export function computeLayout(graph: DisplayGraph): GraphLayout {
    const {nodes, edges} = graph;
    const byId = new Map(nodes.map(node => [node.id, node]));
    const geometry = new Map(nodes.map(node => [node.id, nodeGeometry(node)]));
    const parents = new Map<string, string[]>(nodes.map(node => [node.id, []]));
    const children = new Map<string, string[]>(nodes.map(node => [node.id, []]));
    for (const edge of edges) {
        if (!byId.has(edge.source) || !byId.has(edge.target)) throw new Error(`Edge ${edge.id} references an unknown node`);
        children.get(edge.source)!.push(edge.target);
        parents.get(edge.target)!.push(edge.source);
    }
    const rank = new Map<string, number>();
    const visit = (id: string, stack: Set<string>): number => {
        const known = rank.get(id);
        if (known !== undefined) return known;
        if (stack.has(id)) throw new Error('The processing plan contains a cycle');
        const next = new Set(stack).add(id);
        const ps = parents.get(id)!;
        const value = ps.length ? 1 + Math.max(...ps.map(parent => visit(parent, next))) : 0;
        rank.set(id, value);
        return value;
    };
    nodes.forEach(node => visit(node.id, new Set()));
    // Pull producers forward so they sit beside their earliest consumer.
    for (const node of [...nodes].sort((a, b) => rank.get(b.id)! - rank.get(a.id)!)) {
        const kids = children.get(node.id)!;
        if (kids.length) rank.set(node.id, Math.min(...kids.map(kid => rank.get(kid)!)) - 1);
    }
    const portCross = (id: string, key: string): number => {
        const port = geometry.get(id)!.ports.get(key);
        if (!port) throw new Error(`Missing declared slot ${key} on ${id}`);
        return port.y;
    };
    const items = new Map<string, LayoutItem>();
    nodes.forEach((node, index) => {
        const g = geometry.get(node.id)!;
        items.set(node.id, {id: node.id, rank: rank.get(node.id)!, dummy: false, main: g.w, cross: g.h, order: index});
    });
    const chains: {edge: DisplayEdge; chain: string[]}[] = [];
    const links: Link[] = [];
    edges.forEach((edge, edgeIndex) => {
        const chain = [edge.source];
        for (let r = rank.get(edge.source)! + 1; r < rank.get(edge.target)!; r++) {
            const id = `~${edge.id}~${r}`;
            items.set(id, {id, rank: r, dummy: true, main: 0, cross: DUMMY, order: nodes.length + edgeIndex});
            chain.push(id);
        }
        chain.push(edge.target);
        chains.push({edge, chain});
        for (let i = 0; i < chain.length - 1; i++) {
            links.push({a: chain[i], b: chain[i + 1],
                aOff: i === 0 ? portCross(edge.source, `out:${edge.sourceSlot}`) : DUMMY / 2,
                bOff: i === chain.length - 2 ? portCross(edge.target, `in:${edge.targetSlot}`) : DUMMY / 2});
        }
    });
    const maxRank = Math.max(...[...items.values()].map(item => item.rank));
    let layers: string[][] = Array.from({length: maxRank + 1}, () => []);
    [...items.values()].sort((a, b) => a.order - b.order).forEach(item => layers[item.rank].push(item.id));
    const up = new Map<string, Neighbour[]>();
    const down = new Map<string, Neighbour[]>();
    const push = (map: Map<string, Neighbour[]>, key: string, value: Neighbour): void => {
        const list = map.get(key);
        if (list) list.push(value); else map.set(key, [value]);
    };
    for (const link of links) {
        push(down, link.a, {o: link.b, self: link.aOff, other: link.bOff});
        push(up, link.b, {o: link.a, self: link.bOff, other: link.aOff});
    }
    const pos = new Map<string, number>();
    const index = (): void => layers.forEach(layer => layer.forEach((id, i) => pos.set(id, i)));
    const frac = (id: string, offset: number): number => offset / items.get(id)!.cross;
    const sweep = (r: number, neighbours: Map<string, Neighbour[]>): void => {
        const layer = layers[r];
        const centre = new Map(layer.map(id => {
            const ns = neighbours.get(id) ?? [];
            return [id, ns.length ? ns.reduce((sum, nb) => sum + pos.get(nb.o)! + frac(nb.o, nb.other), 0) / ns.length : pos.get(id)! + 0.5];
        }));
        layer.sort((a, b) => centre.get(a)! - centre.get(b)!);
        layer.forEach((id, i) => pos.set(id, i));
    };
    const crossings = (): number => {
        let count = 0;
        for (let r = 0; r < maxRank; r++) {
            const segments = links.filter(link => items.get(link.a)!.rank === r)
                .map(link => [pos.get(link.a)! + frac(link.a, link.aOff), pos.get(link.b)! + frac(link.b, link.bOff)]);
            for (let i = 0; i < segments.length; i++) {
                for (let j = i + 1; j < segments.length; j++) {
                    if ((segments[i][0] - segments[j][0]) * (segments[i][1] - segments[j][1]) < 0) count++;
                }
            }
        }
        return count;
    };
    index();
    let best = layers.map(layer => [...layer]);
    let bestCrossings = crossings();
    for (let iteration = 0; iteration < 16 && bestCrossings > 0; iteration++) {
        if (iteration % 2 === 0) for (let r = 1; r <= maxRank; r++) sweep(r, up);
        else for (let r = maxRank - 1; r >= 0; r--) sweep(r, down);
        const count = crossings();
        if (count < bestCrossings) {
            bestCrossings = count;
            best = layers.map(layer => [...layer]);
        }
    }
    layers = best;
    index();
    // Cross-axis placement: pull each item toward its neighbours' ports while keeping order and gaps.
    const cross = new Map<string, number>();
    const size = (id: string): number => items.get(id)!.cross;
    const gap = (a: string, b: string): number => items.get(a)!.dummy && items.get(b)!.dummy ? 10
        : items.get(a)!.dummy || items.get(b)!.dummy ? 18 : CROSS_GAP;
    layers.forEach(layer => {
        let y = 0;
        const offsets = layer.map((id, i) => {
            const value = y;
            y += size(id) + (i < layer.length - 1 ? gap(id, layer[i + 1]) : 0);
            return value;
        });
        layer.forEach((id, i) => cross.set(id, offsets[i] - y / 2));
    });
    const place = (layer: string[], want: number[]): void => {
        const n = layer.length;
        const forward: number[] = [];
        const backward: number[] = [];
        const out: number[] = [];
        for (let i = 0; i < n; i++) forward[i] = i ? Math.max(want[i], forward[i - 1] + size(layer[i - 1]) + gap(layer[i - 1], layer[i])) : want[i];
        for (let i = n - 1; i >= 0; i--) backward[i] = i < n - 1 ? Math.min(want[i], backward[i + 1] - size(layer[i]) - gap(layer[i], layer[i + 1])) : want[i];
        for (let i = 0; i < n; i++) {
            const mid = (forward[i] + backward[i]) / 2;
            out[i] = i ? Math.max(mid, out[i - 1] + size(layer[i - 1]) + gap(layer[i - 1], layer[i])) : mid;
        }
        layer.forEach((id, i) => cross.set(id, out[i]));
    };
    const want = (id: string, maps: Map<string, Neighbour[]>[]): number => {
        let sum = 0;
        let count = 0;
        for (const map of maps) {
            for (const nb of map.get(id) ?? []) {
                sum += cross.get(nb.o)! + nb.other - nb.self;
                count++;
            }
        }
        return count ? sum / count : cross.get(id)!;
    };
    for (let iteration = 0; iteration < 28; iteration++) {
        const maps = iteration < 18 ? (iteration % 2 ? [down] : [up]) : [up, down];
        const order = iteration % 2 ? [...layers.keys()].reverse() : [...layers.keys()];
        for (const r of order) place(layers[r], layers[r].map(id => want(id, maps)));
    }
    const layerSize = layers.map(layer => Math.max(0, ...layer.map(id => items.get(id)!.main)));
    const layerPos: number[] = [];
    let main = MARGIN;
    layerSize.forEach((s, r) => {
        layerPos[r] = main;
        main += s + MAIN_GAP;
    });
    const totalMain = main - MAIN_GAP + MARGIN;
    let lo = Infinity;
    let hi = -Infinity;
    for (const [id, c] of cross) {
        lo = Math.min(lo, c);
        hi = Math.max(hi, c + size(id));
    }
    const shift = MARGIN - lo;
    const boxes = new Map<string, NodeBox>();
    for (const node of nodes) {
        const item = items.get(node.id)!;
        const g = geometry.get(node.id)!;
        // Terminals sit against the operation they serve rather than at the far edge of their layer.
        const x = node.role === 'source' ? layerPos[item.rank] + layerSize[item.rank] - g.w : layerPos[item.rank];
        boxes.set(node.id, {...g, x, y: cross.get(node.id)! + shift});
    }
    const portAbs = (id: string, key: string): Point => {
        const box = boxes.get(id)!;
        const port = box.ports.get(key);
        if (!port) throw new Error(`Missing declared slot ${key} on ${id}`);
        return {x: box.x + port.x, y: box.y + port.y};
    };
    const curve = (p: Point, q: Point): string => {
        const k = Math.max(28, (q.x - p.x) * 0.5);
        return ` C${round(p.x + k)},${round(p.y)} ${round(q.x - k)},${round(q.y)} ${round(q.x)},${round(q.y)}`;
    };
    const paths = chains.map(({edge, chain}) => {
        let current = portAbs(edge.source, `out:${edge.sourceSlot}`);
        let d = `M${round(current.x)},${round(current.y)}`;
        for (const id of chain.slice(1, -1)) {
            const r = items.get(id)!.rank;
            const c = cross.get(id)! + shift + DUMMY / 2;
            const entry = {x: layerPos[r], y: c};
            const exit = {x: layerPos[r] + layerSize[r], y: c};
            d += curve(current, entry);
            if (layerSize[r]) d += ` L${round(exit.x)},${round(exit.y)}`;
            current = exit;
        }
        d += curve(current, portAbs(edge.target, `in:${edge.targetSlot}`));
        return {edge, d};
    });
    return {boxes, paths, width: totalMain, height: hi - lo + 2 * MARGIN};
}
