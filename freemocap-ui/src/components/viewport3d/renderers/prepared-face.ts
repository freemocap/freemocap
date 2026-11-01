import type {ModelDefinition} from '@/services/server/transport/message-contract';
import {finitePoint} from './prepared-models';

export interface PreparedFace {points: Int32Array; edges: Int32Array}
const isFace = (name: string) => /^face[._]/.test(name);

/** Static layout preparation only; Tracker owns topology. */
export function prepareFace(names: readonly string[], models: Iterable<ModelDefinition>): PreparedFace {
    const indices = new Map(names.map((name, row) => [name, row]));
    const edges: number[] = [], seen = new Set<string>();
    for (const model of models) for (const [a, b] of model.tracker_connections ?? []) {
        if (!isFace(a) || !isFace(b)) continue;
        const start = indices.get(a), end = indices.get(b);
        if (start === undefined || end === undefined) continue;
        const key = start < end ? `${start}:${end}` : `${end}:${start}`;
        if (seen.has(key)) continue;
        seen.add(key); edges.push(start, end);
    }
    return {points: Int32Array.from(names.flatMap((name, row) => isFace(name) ? [row] : [])), edges: Int32Array.from(edges)};
}

/** Compact valid primitives into reusable output; never retain source buffers. */
export function writeFace(data: Float32Array, rows: Int32Array, output: Float32Array, edge: boolean): number {
    const step = edge ? 2 : 1;
    let count = 0;
    for (let i = 0; i < rows.length; i += step) {
        const a = rows[i] * 3, b = edge ? rows[i + 1] * 3 : a;
        if (!finitePoint(data, a) || !finitePoint(data, b)) continue;
        const base = count * step * 3;
        output[base] = data[a]; output[base + 1] = data[a + 1]; output[base + 2] = data[a + 2];
        if (edge) {output[base + 3] = data[b]; output[base + 4] = data[b + 1]; output[base + 5] = data[b + 2];}
        count++;
    }
    return count;
}
