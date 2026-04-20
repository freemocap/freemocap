import React, {createContext, useContext, useMemo} from "react";
import {Point3d} from "./helpers/viewport3d-types";
import {useServer} from "@/services";

/**
 * Abstraction over "where do 3D keypoints come from". The Streaming panel
 * feeds the renderers from a live WebSocket (via useServer). The Playback
 * panel feeds them from a cached Float32 buffer driven by the playback slider.
 *
 * Renderers pull whichever source is active via `useKeypointsSource()`.
 * If no provider is mounted, the hook transparently falls back to `useServer()`
 * so existing Streaming code keeps working with zero changes at that layer.
 */
export type KeypointsCallback = (points: Record<string, Point3d>) => void;

export interface KeypointsSource {
    subscribeToKeypointsRaw: (cb: KeypointsCallback) => () => void;
    subscribeToKeypointsFiltered: (cb: KeypointsCallback) => () => void;
    getLatestKeypointsRaw: () => Record<string, Point3d>;
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
    const server = useServer();

    // Build the live adapter lazily so it doesn't allocate when a provider is present.
    const liveAdapter = useMemo<KeypointsSource>(() => ({
        subscribeToKeypointsRaw: server.subscribeToKeypointsRaw,
        subscribeToKeypointsFiltered: server.subscribeToKeypointsFiltered,
        getLatestKeypointsRaw: server.getLatestKeypointsRaw,
    }), [
        server.subscribeToKeypointsRaw,
        server.subscribeToKeypointsFiltered,
        server.getLatestKeypointsRaw,
    ]);

    return ctx ?? liveAdapter;
}
