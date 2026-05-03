import React, {createContext, useContext, useMemo} from "react";
import {useServerOptional} from "@/services/server/server-context";

/**
 * Abstraction over "where do 3D keypoints come from". The Streaming panel
 * feeds the renderers from a live WebSocket (via useServer). The Playback
 * panel feeds them from a cached Float32 buffer driven by the playback slider.
 *
 * Renderers pull whichever source is active via `useKeypointsSource()`.
 * If no provider is mounted, the hook transparently falls back to `useServer()`
 * so existing Streaming code keeps working with zero changes at that layer.
 */

/**
 * A single frame of keypoint data in typed-array form.
 *
 * `interleaved` is a Float32Array laid out as:
 *   [x₀, y₀, z₀, vis₀,  x₁, y₁, z₁, vis₁, … ]
 * where `pointNames[i]` names the point at stride `i * 4`.
 * Missing / untriangulated points have NaN coords and visibility = 0.
 *
 * The array is dense and schema-ordered when the binary websocket path is
 * active; it may be sparse (only present points) when falling back to JSON.
 */
export interface KeypointsFrame {
    pointNames: readonly string[];
    interleaved: Float32Array;   // length === pointNames.length * 4
}

export type KeypointsCallback = (frame: KeypointsFrame) => void;

export interface KeypointsSource {
    subscribeToKeypointsRaw: (cb: KeypointsCallback) => () => void;
    subscribeToKeypointsFiltered: (cb: KeypointsCallback) => () => void;
    getLatestKeypointsRaw: () => KeypointsFrame | null;
}

const KeypointsSourceContext = createContext<KeypointsSource | null>(null);

export const KeypointsSourceProvider: React.FC<{
    source: KeypointsSource;
    children: React.ReactNode;
}> = ({source, children}) => (
    <KeypointsSourceContext.Provider value={source}>
        {children}
    </KeypointsSourceContext.Provider>
);

/**
 * Returns the active keypoints source. Falls back to the live server if no
 * provider is mounted above the consumer.
 */
export function useKeypointsSource(): KeypointsSource {
    const ctx = useContext(KeypointsSourceContext);
    // useServerOptional returns null when called outside ServerContextProvider
    // (e.g. inside a Web Worker where only WorkerDataStore provides keypoints).
    const server = useServerOptional();

    // Build the live adapter lazily so it doesn't allocate when a provider is present.
    const liveAdapter = useMemo<KeypointsSource | null>(() => {
        if (!server) return null;
        return {
            subscribeToKeypointsRaw: server.subscribeToKeypointsRaw,
            subscribeToKeypointsFiltered: server.subscribeToKeypointsFiltered,
            getLatestKeypointsRaw: server.getLatestKeypointsRaw,
        };
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [
        server?.subscribeToKeypointsRaw,
        server?.subscribeToKeypointsFiltered,
        server?.getLatestKeypointsRaw,
    ]);

    const source = ctx ?? liveAdapter;
    if (!source) throw new Error("No KeypointsSource: mount KeypointsSourceProvider or ServerContextProvider");
    return source;
}

// ---------------------------------------------------------------------------
// Utilities shared by multiple producers / consumers
// ---------------------------------------------------------------------------

/** Build a KeypointsFrame from a sparse `Record<string, {x,y,z}>` dict.
 * Used by the JSON fallback path and by renderers that still receive dict data.
 * Allocates one Float32Array; visibility is 1 for every point in the dict.
 */
export function pointDictToFrame(dict: Record<string, {x:number; y:number; z:number}>): KeypointsFrame {
    const pointNames = Object.keys(dict);
    const interleaved = new Float32Array(pointNames.length * 4);
    for (let i = 0; i < pointNames.length; i++) {
        const p = dict[pointNames[i]];
        const off = i * 4;
        interleaved[off]     = p.x;
        interleaved[off + 1] = p.y;
        interleaved[off + 2] = p.z;
        interleaved[off + 3] = 1.0;
    }
    return { pointNames, interleaved };
}

/** Build a `Map<string, {x,y,z}>` from a frame. Used by renderers that need
 * name-keyed lookup (ConnectionRenderer, FaceRenderer). Allocates one object
 * per visible point; only called when those renderers receive a new frame.
 */
export function frameToPointMap(frame: KeypointsFrame): Map<string, {x:number; y:number; z:number}> {
    const m = new Map<string, {x:number; y:number; z:number}>();
    const { pointNames, interleaved } = frame;
    for (let i = 0; i < pointNames.length; i++) {
        const off = i * 4;
        if (!interleaved[off + 3]) continue;  // vis === 0 → skip
        const x = interleaved[off];
        const y = interleaved[off + 1];
        const z = interleaved[off + 2];
        if (Number.isFinite(x) && Number.isFinite(y) && Number.isFinite(z)) {
            m.set(pointNames[i], { x, y, z });
        }
    }
    return m;
}
