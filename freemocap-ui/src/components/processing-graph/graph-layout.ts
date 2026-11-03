// Layered layout and node geometry ported from the Graph Lab viewer
// (experiments/executable_graph_lab/synthetic/viewer.html) as used on the approved design canvas.
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
        const h = LR_TOP + (inRows + outs.length) * LR_ROW + 6 + 28;
        const diskRows = diskFileRows(node);
        return {w: LR_WIDTH, h: h + (io ? 34 + Math.max(40, 30 + diskRows * 16) + 12 : 0), bw: LR_WIDTH, bh: h, ports,
            headTop: 0, footTop: h - 28, split: LR_TOP + inRows * LR_ROW, sourceY: rowY(0)};
    }
    const w = Math.max(240, Math.max(ins.length, outs.length) * 128);
    ins.forEach((slot, i) => ports.set(`in:${slot.name}`, {x: w * (i + 0.5) / ins.length, y: 0}));
    outs.forEach((slot, j) => ports.set(`out:${slot.name}`, {x: w * (j + 0.5) / outs.length, y: TD_HEIGHT}));
    const diskRows = diskFileRows(node);
    return {w: w + (io ? 34 + 26 + 66 + 8 : 0), h: Math.max(TD_HEIGHT, io ? 96 + diskRows * 16 : 0), bw: w, bh: TD_HEIGHT, ports,
        headTop: 26, footTop: 76, split: 0, sourceY: 0};
}

interface LayoutItem {id: string; rank: number; dummy: boolean; main: number; cross: number; order: number}
interface Link {a: string; b: string; aOff: number; bOff: number}
interface Neighbour {o: string; self: number; other: number}

const DUMMY = 8;
const MARGIN = 48;
const round = (value: number): number => Math.round(value * 10) / 10;

export function computeLayout(graph: DisplayGraph, direction: GraphDirection): GraphLayout {
    const {nodes, edges} = graph;
    const side = direction === 'right';
    const mainGap = side ? 128 : 100;
    const crossGap = side ? 28 : 40;
    const byId = new Map(nodes.map(node => [node.id, node]));
    const geometry = new Map(nodes.map(node => [node.id, nodeGeometry(node, direction)]));
    const parents = new Map<string, string[]>(nodes.map(node => [node.id, []]));
    const children = new Map<string, string[]>(nodes.map(node => [node.id, []]));
    for (const edge of edges) {
        if (!byId.has(edge.source) || !byId.has(edge.target)) throw new Error(`Edge ${edge.id} references an unknown node`);
        parents.get(edge.target)!.push(edge.source);
        children.get(edge.source)!.push(edge.target);
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
        return side ? port.y : port.x;
    };
    const items = new Map<string, LayoutItem>();
    nodes.forEach((node, index) => {
        const g = geometry.get(node.id)!;
        items.set(node.id, {id: node.id, rank: rank.get(node.id)!, dummy: false, main: side ? g.w : g.h, cross: side ? g.h : g.w,
            order: (node.camera ?? -1) * 1000 + index});
    });
    const chains: {edge: DisplayEdge; chain: string[]}[] = [];
    const links: Link[] = [];
    edges.forEach((edge, edgeIndex) => {
        const chain = [edge.source];
        for (let r = rank.get(edge.source)! + 1; r < rank.get(edge.target)!; r++) {
            const id = `~${edge.id}~${r}`;
            items.set(id, {id, rank: r, dummy: true, main: 0, cross: DUMMY,
                order: (byId.get(edge.target)!.camera ?? -1) * 1000 + nodes.length + edgeIndex});
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
        : items.get(a)!.dummy || items.get(b)!.dummy ? 18 : crossGap;
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
        main += s + mainGap;
    });
    const totalMain = main - mainGap + MARGIN;
    let lo = Infinity;
    let hi = -Infinity;
    for (const [id, c] of cross) {
        lo = Math.min(lo, c);
        hi = Math.max(hi, c + size(id));
    }
    const shift = MARGIN - lo;
    const totalCross = hi - lo + 2 * MARGIN;
    const pt = (a: number, c: number): Point => side ? {x: a, y: c} : {x: c, y: a};
    const boxes = new Map<string, NodeBox>();
    for (const node of nodes) {
        const item = items.get(node.id)!;
        boxes.set(node.id, {...geometry.get(node.id)!, ...pt(layerPos[item.rank], cross.get(node.id)! + shift)});
    }
    const portAbs = (id: string, key: string): Point => {
        const box = boxes.get(id)!;
        const port = box.ports.get(key);
        if (!port) throw new Error(`Missing declared slot ${key} on ${id}`);
        return {x: box.x + port.x, y: box.y + port.y};
    };
    const curve = (p: Point, q: Point): string => {
        if (side) {
            const k = Math.max(28, (q.x - p.x) * 0.5);
            return ` C${round(p.x + k)},${round(p.y)} ${round(q.x - k)},${round(q.y)} ${round(q.x)},${round(q.y)}`;
        }
        const k = Math.max(28, (q.y - p.y) * 0.5);
        return ` C${round(p.x)},${round(p.y + k)} ${round(q.x)},${round(q.y - k)} ${round(q.x)},${round(q.y)}`;
    };
    const paths = chains.map(({edge, chain}) => {
        let current = portAbs(edge.source, `out:${edge.sourceSlot}`);
        let d = `M${round(current.x)},${round(current.y)}`;
        for (const id of chain.slice(1, -1)) {
            const r = items.get(id)!.rank;
            const c = cross.get(id)! + shift + DUMMY / 2;
            const entry = pt(layerPos[r], c);
            const exit = pt(layerPos[r] + layerSize[r], c);
            d += curve(current, entry);
            if (layerSize[r]) d += ` L${round(exit.x)},${round(exit.y)}`;
            current = exit;
        }
        d += curve(current, portAbs(edge.target, `in:${edge.targetSlot}`));
        return {edge, d};
    });
    return {boxes, paths, width: side ? totalMain : totalCross, height: side ? totalCross : totalMain};
}
