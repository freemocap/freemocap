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
    subscribeToKeypoints: (cb: KeypointsCallback) => () => void;
    subscribeToSkeleton: (cb: KeypointsCallback) => () => void;
    getLatestKeypoints: () => KeypointsFrame | null;
    getLatestSkeleton: () => KeypointsFrame | null;
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
 * Returns true when a KeypointsSourceProvider is mounted above the consumer
 * (i.e. during playback mode), false when keypoints come from the live server.
 */
export function useHasKeypointsSourceProvider(): boolean {
    return useContext(KeypointsSourceContext) !== null;
}

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
            subscribeToKeypoints: server.subscribeToKeypoints,
            subscribeToSkeleton: server.subscribeToSkeleton,
            getLatestKeypoints: server.getLatestKeypoints,
            getLatestSkeleton: server.getLatestSkeleton,
        };
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [
        server?.subscribeToKeypoints,
        server?.subscribeToSkeleton,
        server?.getLatestKeypoints,
        server?.getLatestSkeleton,
    ]);

    const source = ctx ?? liveAdapter;
    if (!source) throw new Error("No KeypointsSource: mount KeypointsSourceProvider or ServerContextProvider");
    return source;
}
