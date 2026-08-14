import React, {createContext, useContext, useMemo} from "react";
import {useServerOptional} from "@/services/server/server-context";
import type { RotationsFrame, RollingChannelName, StreamSchema } from '@/services/server/transport/types';

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
 * `interleaved` is a Float32Array whose layout depends on which stream produced
 * it. The keypoints stream is a 4-column interleave of `x, y, z` plus a
 * visibility flag; the skeleton stream (consumed by the rigid-body renderer) is
 * a 3-column `x, y, z` interleave, i.e.:
 *
 *   keypoints: [x₀, y₀, z₀, vis₀,  x₁, y₁, z₁, vis₁, … ]   stride 4
 *   skeleton:  [x₀, y₀, z₀,  x₁, y₁, z₁, … ]               stride 3
 *
 * Missing / untriangulated points have NaN coords and visibility = 0.
 *
 * The array is dense and schema-ordered when the binary websocket path is
 * active; it may be sparse (only present points) when falling back to JSON.
 */
export interface KeypointsFrame {
    pointNames: readonly string[];
    interleaved: Float32Array;   // length = pointNames.length * 4 (keypoints) or * 3 (skeleton)
}

export type KeypointsCallback = (frame: KeypointsFrame) => void;

export interface KeypointsSource {
    subscribeToKeypoints: (cb: KeypointsCallback) => () => void;
    subscribeToSkeleton: (cb: KeypointsCallback) => () => void;
    getLatestKeypoints: () => KeypointsFrame | null;
    getLatestSkeleton: () => KeypointsFrame | null;
    // Standard-stream (F3) additions — optional, for renderers (F4) to consume.
    subscribeToRotations?: (cb: (frame: RotationsFrame) => void) => () => void;
    getLatestRotations?: () => RotationsFrame | null;
    getRollingWindow?: (channelName: RollingChannelName) => unknown[];
    // Standard-stream schema access (F4 — the rigid-body renderer's name→index map).
    subscribeToSchema?: (cb: (schema: StreamSchema) => void) => () => void;
    getStreamSchema?: () => StreamSchema | null;
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
            subscribeToRotations: server.subscribeToRotations,
            getLatestRotations: server.getLatestRotations,
            getRollingWindow: server.getRollingWindow,
            subscribeToSchema: server.subscribeToSchema,
            getStreamSchema: server.getStreamSchema,
        };
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [
        server?.subscribeToKeypoints,
        server?.subscribeToSkeleton,
        server?.getLatestKeypoints,
        server?.getLatestSkeleton,
        server?.subscribeToRotations,
        server?.getLatestRotations,
        server?.getRollingWindow,
        server?.subscribeToSchema,
        server?.getStreamSchema,
    ]);

    const source = ctx ?? liveAdapter;
    if (!source) throw new Error("No KeypointsSource: mount KeypointsSourceProvider or ServerContextProvider");
    return source;
}
