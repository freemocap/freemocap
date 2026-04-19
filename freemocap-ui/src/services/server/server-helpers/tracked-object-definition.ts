/**
 * TrackedObjectDefinition — TS mirror of skellytracker's Pydantic model.
 *
 * Shipped over the `tracker_schemas` websocket handshake message, this is the
 * single source of truth for how the frontend renders a tracker's output:
 *   - `tracked_points` — ordered list of names; matches `observation.points.names`
 *   - `connections`    — name-pair edges to draw between points
 *   - `landmark_schema`/`tracker_type` — coarse descriptors used to gate
 *                         things like face-contour rendering
 *   - `color_hints`    — optional per-name (or per-prefix) color overrides;
 *                         when absent, the frontend falls back to its
 *                         name-pattern heuristic
 */
export interface TrackedObjectDefinition {
    name: string;
    tracker_type: string;
    landmark_schema: string;
    tracked_points: string[];
    connections: [string, string][];
    color_hints?: Record<string, string>;
}

/** Name-pair connections resolved to (start_idx, end_idx) into `tracked_points`. */
export function connectionIndices(def: TrackedObjectDefinition): [number, number][] {
    const idxOf = new Map<string, number>();
    def.tracked_points.forEach((name, i) => idxOf.set(name, i));
    const out: [number, number][] = [];
    for (const [a, b] of def.connections) {
        const ia = idxOf.get(a);
        const ib = idxOf.get(b);
        if (ia !== undefined && ib !== undefined) out.push([ia, ib]);
    }
    return out;
}
